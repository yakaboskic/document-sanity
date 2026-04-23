#!/usr/bin/env python3
"""
CLI entry point for document-sanity v2.

Commands:
  init           Initialize a new project
  build          Build a version (src/ -> out/)
  new-version    Create a new version from an existing one
  import         Import an existing LaTeX project into src/ format
  convert        Convert a single markdown file to LaTeX (or vice versa)
"""

import argparse
import sys
from pathlib import Path


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new project."""
    from .init import init_project

    target = Path(args.target).resolve() if args.target else Path.cwd()
    try:
        init_project(
            name=args.name,
            target_dir=target,
            template=args.template,
            strategy=args.strategy,
        )
        return 0
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return 1


def cmd_build(args: argparse.Namespace) -> int:
    """Build a version."""
    from .build import ManuscriptBuilder, find_latest_version

    root_dir = Path(args.root).resolve()

    try:
        version = args.version
        if version is None:
            version = find_latest_version(root_dir)
            print(f"  Auto-detected version: {version}")

        builder = ManuscriptBuilder(
            root_dir=root_dir,
            version=version,
            placeholder=args.placeholder,
            strict=args.strict,
            verbose=args.verbose,
            compile_pdf=args.compile,
            compiler=args.compiler,
        )
        success = builder.build()
        return 0 if success else 1

    except Exception as e:
        print(f"\n  Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_new_version(args: argparse.Namespace) -> int:
    """Create a new version."""
    from .make_version import make_new_version
    from .build import find_latest_version

    root_dir = Path(args.root).resolve()

    source = args.source
    if source is None:
        try:
            source = find_latest_version(root_dir)
            print(f"  Auto-detected source: {source}")
        except ValueError as e:
            print(f"  Error: {e}", file=sys.stderr)
            return 1

    result = make_new_version(
        root_dir=root_dir,
        source_version=source,
        strategy=args.strategy,
        n_words=args.words,
        version_override=args.name,
        dry_run=args.dry_run,
    )
    return 0 if result else 1


def cmd_import(args: argparse.Namespace) -> int:
    """Import an existing LaTeX project."""
    from .latex2md import convert_latex_project
    from .manifest import Manifest, VariableEntry, FigureEntry, TableEntry
    from .version import make_version_name

    source_dir = Path(args.source).resolve()
    target_dir = Path(args.target).resolve() if args.target else Path.cwd()

    if not source_dir.exists():
        print(f"  Error: Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    # Determine version name for the import
    version_name = args.name or make_version_name(args.strategy)
    output_dir = target_dir / "src" / version_name

    print(f"  Importing LaTeX project")
    print(f"  Source: {source_dir}")
    print(f"  Target: {output_dir}")

    if args.manuscript:
        manuscript = args.manuscript
    else:
        # Try to auto-detect
        versions_dir = source_dir / "versions"
        if versions_dir.exists():
            manuscripts = [d.name for d in versions_dir.iterdir() if d.is_dir()]
            if len(manuscripts) == 1:
                manuscript = manuscripts[0]
            elif len(manuscripts) > 1:
                print(f"  Error: Multiple manuscripts found: {manuscripts}", file=sys.stderr)
                print(f"  Specify with --manuscript", file=sys.stderr)
                return 1
            else:
                manuscript = None
        else:
            manuscript = None

    if args.version:
        src_version = args.version
    else:
        # Auto-detect latest
        if manuscript:
            from .version import find_latest_version
            try:
                _, src_version = find_latest_version(source_dir / "versions", manuscript)
            except ValueError:
                src_version = None
        else:
            src_version = None

    if not manuscript or not src_version:
        print(f"  Error: Could not auto-detect manuscript/version.", file=sys.stderr)
        print(f"  Specify with --manuscript and --version", file=sys.stderr)
        return 1

    print(f"  Manuscript: {manuscript}")
    print(f"  Source version: {src_version}")
    print(f"  Target version: {version_name}")

    try:
        result = convert_latex_project(
            root_dir=source_dir,
            manuscript=manuscript,
            version=src_version,
            output_dir=output_dir,
            preserve_comments=True,
        )

        # Build manifest.yaml from the extracted data
        manifest = Manifest.__new__(Manifest)
        manifest.path = output_dir / "manifest.yaml"
        manifest.raw = {}

        # Metadata
        from .manifest import Metadata, AuthorInfo
        meta_raw = result.get('metadata', {})
        manifest.metadata = Metadata(
            title=meta_raw.get('title'),
            abstract=meta_raw.get('abstract'),
            keywords=meta_raw.get('keywords', []),
            document_class=meta_raw.get('document_class'),
            template='article',
        )

        # Sections
        manifest.sections = result.get('sections', [])

        # Variables
        manifest.variables = {}
        for name, value in result.get('variables', {}).items():
            manifest.variables[name] = VariableEntry(name=name, value=value)

        # Figures
        manifest.figures = {}
        for fig_id, spec in result.get('figures', {}).items():
            manifest.figures[fig_id] = FigureEntry(
                id=fig_id,
                source=spec.get('source'),
            )

        # Tables
        manifest.tables = {}
        for tbl_id, spec in result.get('tables', {}).items():
            manifest.tables[tbl_id] = TableEntry(
                id=tbl_id,
                source=spec.get('source'),
                format=spec.get('format', 'latex'),
            )

        # Save manifest
        manifest.save()

        n_sections = len(manifest.sections)
        n_vars = len(manifest.variables)
        n_figs = len(manifest.figures)
        n_tables = len(manifest.tables)

        print(f"\n  Import complete!")
        print(f"  Sections:  {n_sections}")
        print(f"  Variables: {n_vars}")
        print(f"  Figures:   {n_figs}")
        print(f"  Tables:    {n_tables}")
        print(f"  Output:    {output_dir}")
        print(f"\n  Next: document-sanity build --root {target_dir} --version {version_name}")

        return 0

    except Exception as e:
        print(f"  Error during import: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_html(args: argparse.Namespace) -> int:
    """Emit a single-file interactive HTML viewer."""
    from .html_builder import build_html
    from .build import find_latest_version

    root_dir = Path(args.root).resolve()
    version = args.version
    if version is None:
        try:
            version = find_latest_version(root_dir)
            print(f'  Auto-detected version: {version}')
        except ValueError as e:
            print(f'  Error: {e}', file=sys.stderr)
            return 1
    ok = build_html(
        root_dir=root_dir,
        version=version,
        open_browser=args.open,
        verbose=args.verbose,
    )
    return 0 if ok else 1


def cmd_preview(args: argparse.Namespace) -> int:
    """Generate/check markdown-preview blocks next to LaTeX pass-through blocks."""
    from .preview import run
    from .build import find_latest_version

    root_dir = Path(args.root).resolve()
    version = args.version
    if version is None:
        try:
            version = find_latest_version(root_dir)
            print(f'  Auto-detected version: {version}')
        except ValueError as e:
            print(f'  Error: {e}', file=sys.stderr)
            return 1

    return run(
        root_dir=root_dir,
        version=version,
        check=args.check,
        verbose=args.verbose,
        expand_macros=not args.no_expand_macros,
    )


def cmd_word(args: argparse.Namespace) -> int:
    """Build a Word (.docx) output, or extract styles from a template."""
    from .docx_builder import WordBuilder, find_latest_version

    root_dir = Path(args.root).resolve()
    template = Path(args.template).resolve() if args.template else None
    styles = Path(args.styles).resolve() if args.styles else None

    if args.extract_styles:
        # Just produce a styles.json from the template; no manifest needed if
        # the user passed an explicit template.
        if not template:
            # Need a manifest to locate the template.
            try:
                version = args.version or find_latest_version(root_dir)
            except ValueError as e:
                print(f"  Error: {e}", file=sys.stderr)
                return 1
            builder = WordBuilder(
                root_dir=root_dir,
                version=version,
                template_override=None,
                styles_override=None,
                verbose=args.verbose,
            )
            dest = Path(args.output) if args.output else (
                root_dir / "out" / version / "word" / "styles.json"
            )
            result = builder.extract_styles_to(dest)
        else:
            from .docx_extract import extract_styles
            from .docx_styles import save_styles

            dest = Path(args.output) if args.output else template.with_suffix(".styles.json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            save_styles(dest, extract_styles(template))
            result = dest
        print(f"  Styles extracted -> {result}")
        return 0

    version = args.version
    if version is None:
        try:
            version = find_latest_version(root_dir)
            print(f"  Auto-detected version: {version}")
        except ValueError as e:
            print(f"  Error: {e}", file=sys.stderr)
            return 1

    try:
        builder = WordBuilder(
            root_dir=root_dir,
            version=version,
            template_override=template,
            styles_override=styles,
            placeholder=args.placeholder,
            strict=args.strict,
            verbose=args.verbose,
        )
        ok = builder.build()
        return 0 if ok else 1
    except Exception as e:
        print(f"\n  Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_convert(args: argparse.Namespace) -> int:
    """Convert a single file."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"  Error: File not found: {input_path}", file=sys.stderr)
        return 1

    if args.direction == 'md2tex':
        from .md2latex import convert_md_file
        output_path = Path(args.output) if args.output else input_path.with_suffix('.tex')
        meta = convert_md_file(input_path, output_path, escape_text=not args.no_escape)
        print(f"  Converted: {input_path} -> {output_path}")
    elif args.direction == 'tex2md':
        from .latex2md import convert_latex_file
        output_path = Path(args.output) if args.output else input_path.with_suffix('.md')
        convert_latex_file(input_path, output_path, preserve_comments=args.preserve_comments)
        print(f"  Converted: {input_path} -> {output_path}")
    else:
        # Auto-detect from extension
        if input_path.suffix == '.md':
            from .md2latex import convert_md_file
            output_path = Path(args.output) if args.output else input_path.with_suffix('.tex')
            convert_md_file(input_path, output_path, escape_text=not args.no_escape)
            print(f"  Converted: {input_path} -> {output_path}")
        elif input_path.suffix == '.tex':
            from .latex2md import convert_latex_file
            output_path = Path(args.output) if args.output else input_path.with_suffix('.md')
            convert_latex_file(input_path, output_path, preserve_comments=True)
            print(f"  Converted: {input_path} -> {output_path}")
        else:
            print(f"  Error: Cannot determine conversion direction for {input_path.suffix}")
            return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="document-sanity",
        description="Build LaTeX documents from Markdown source with variable substitution, provenance tracking, and versioned builds.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- init ---
    init_p = subparsers.add_parser("init", help="Initialize a new project")
    init_p.add_argument('name', help='Project name')
    init_p.add_argument('--target', '-t', help='Parent directory (default: cwd)')
    init_p.add_argument('--template', default='article', help='Starting template (default: article)')
    init_p.add_argument('--strategy', '-s', default='both', choices=['date', 'fun', 'both'],
                        help='Version naming strategy (default: both)')

    # --- build ---
    build_p = subparsers.add_parser("build", help="Build a version (src/ -> out/)")
    build_p.add_argument('--version', '-V', help='Version to build (default: auto-detect latest)')
    build_p.add_argument('--root', '-r', default='.', help='Project root directory')
    build_p.add_argument('--placeholder', default='XXXX', help='Placeholder for undefined variables')
    build_p.add_argument('--strict', action='store_true', help='Fail on undefined variables')
    build_p.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    build_p.add_argument('--compile', '-c', action='store_true', help='Compile to PDF')
    build_p.add_argument('--compiler', default='pdflatex',
                        choices=['pdflatex', 'xelatex', 'lualatex', 'latexmk'],
                        help='LaTeX compiler')

    # --- new-version ---
    nv_p = subparsers.add_parser("new-version", help="Create a new version from an existing one")
    nv_p.add_argument('--source', help='Source version (default: auto-detect latest)')
    nv_p.add_argument('--root', '-r', default='.', help='Project root directory')
    nv_p.add_argument('--strategy', '-s', default='both', choices=['date', 'fun', 'both'],
                      help='Version naming strategy')
    nv_p.add_argument('--words', '-w', type=int, default=3, help='Fun name word count')
    nv_p.add_argument('--name', '-n', help='Explicit version name')
    nv_p.add_argument('--dry-run', action='store_true', help='Preview without writing')

    # --- import ---
    imp_p = subparsers.add_parser("import", help="Import an existing LaTeX project")
    imp_p.add_argument('--source', required=True, help='Source LaTeX project directory')
    imp_p.add_argument('--target', '-t', help='Target project directory (default: cwd)')
    imp_p.add_argument('--manuscript', '-m', help='Manuscript name')
    imp_p.add_argument('--version', '-V', help='Source version to import')
    imp_p.add_argument('--name', '-n', help='Name for the imported version')
    imp_p.add_argument('--strategy', '-s', default='both', choices=['date', 'fun', 'both'],
                      help='Version naming strategy for import')

    # --- html ---
    html_p = subparsers.add_parser(
        'html',
        help='Generate an interactive static HTML viewer for the paper '
             '(variables with provenance popovers, KaTeX math, TOC sidebar)'
    )
    html_p.add_argument('--version', '-V', help='Version to render (default: auto-detect latest)')
    html_p.add_argument('--root', '-r', default='.', help='Project root directory')
    html_p.add_argument('--open', action='store_true', help='Open the generated page in a browser')
    html_p.add_argument('--verbose', '-v', action='store_true', help='Per-section output')

    # --- preview ---
    prev_p = subparsers.add_parser(
        'preview',
        help='Generate markdown-preview blocks next to ```latex blocks '
             '(figures/equations/tables) so GitHub and other md viewers render them'
    )
    prev_p.add_argument('--version', '-V', help='Version to preview (default: auto-detect latest)')
    prev_p.add_argument('--root', '-r', default='.', help='Project root directory')
    prev_p.add_argument('--check', action='store_true',
                        help='Report missing/stale preview blocks without writing (CI-friendly)')
    prev_p.add_argument('--verbose', '-v', action='store_true', help='Per-file output')
    prev_p.add_argument('--no-expand-macros', action='store_true',
                        help='Skip expanding \\newcommand macros from the template '
                             '(leaves \\prob etc. unresolved in md math)')

    # --- word ---
    word_p = subparsers.add_parser(
        "word",
        help="Build a Word (.docx) output from the same markdown sources as `build`.",
    )
    word_p.add_argument('--version', '-V', help='Version to build (default: auto-detect latest)')
    word_p.add_argument('--root', '-r', default='.', help='Project root directory')
    word_p.add_argument('--template', '-t', help='Path to a .docx template (overrides manifest)')
    word_p.add_argument('--styles', '-s', help='Styles JSON to apply (default: extract from template)')
    word_p.add_argument('--output', '-o', help='Output path (for --extract-styles)')
    word_p.add_argument('--extract-styles', action='store_true',
                        help='Write the extracted styles.json instead of building a .docx')
    word_p.add_argument('--placeholder', default='XXXX', help='Placeholder for undefined variables')
    word_p.add_argument('--strict', action='store_true', help='Fail on undefined variables')
    word_p.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    # --- convert ---
    conv_p = subparsers.add_parser("convert", help="Convert a single file (md<->tex)")
    conv_p.add_argument('input', help='Input file')
    conv_p.add_argument('-o', '--output', help='Output file')
    conv_p.add_argument('--direction', choices=['md2tex', 'tex2md'],
                       help='Conversion direction (default: auto-detect from extension)')
    conv_p.add_argument('--no-escape', action='store_true', help='Skip LaTeX escaping (md2tex)')
    conv_p.add_argument('--preserve-comments', action='store_true',
                       help='Keep LaTeX comments as HTML comments (tex2md)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    handlers = {
        'init': cmd_init,
        'build': cmd_build,
        'new-version': cmd_new_version,
        'import': cmd_import,
        'preview': cmd_preview,
        'html': cmd_html,
        'word': cmd_word,
        'convert': cmd_convert,
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
