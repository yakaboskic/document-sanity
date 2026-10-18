#!/usr/bin/env python3
"""
CLI entry point for document-sanity.

Every folder under src/ with a manifest.yaml is a document (`--version`
names one; most commands default to the latest):

  build          LaTeX tree (src/ -> out/<doc>/latex/), --compile for the PDF
  html           Interactive HTML viewer
  word           Word (.docx)
  preview        Markdown-preview blocks next to ```latex blocks (--check: CI)
  new-version    Copy a document into a new version folder
  import         Import an existing LaTeX project into src/ format
  convert        Convert a single markdown file to LaTeX (or vice versa)
  drawio         Sync/compose draw.io figures with re-importable source assets

Starting, checking and publishing a project:

  init           A new project from the template (no git needed)
  skills         Install or refresh the agent skill
  check          Build every target of every document; one command before sharing
  site           Build every document and gather them into site/ with an index
  pages init     Write the GitHub Pages workflow
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from . import __version__


def _ask(prompt: str, default: str) -> str:
    try:
        answer = input(f"  {prompt} [{default}]: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def cmd_init(args: argparse.Namespace) -> int:
    """A new project from the template, in a folder with no .git."""
    from . import init_project as ip

    dest = Path(args.dir).expanduser()
    starters = ",".join(args.starter) if args.starter else None
    given = {
        "slug": args.name, "title": args.title, "author": args.author,
        "email": args.email, "description": args.description, "starters": starters,
    }
    interactive = not args.yes and sys.stdin.isatty()
    try:
        source = None
        if args.in_place and args.source:
            raise ip.InitError("--in-place initializes the template copy in DIR; drop --from")
        if args.source:
            owner, repo, ref = ip.parse_gh_spec(args.source)
            print(f"  downloading {owner}/{repo}{'@' + ref if ref else ''} …")
            source = ip.fetch_github(owner, repo, ref)
        if interactive:
            print("  Setting up a new project. Defaults in [brackets]; Enter accepts.\n")
        answers = ip.gather_answers(dest, given, ask=_ask if interactive else None)
        if args.in_place:
            result = ip.init_in_place(dest, answers, skills=not args.no_skills, force=args.force)
        else:
            result = ip.create_project(
                dest, answers, source=source, skills=not args.no_skills,
                force=args.force, git=args.git,
            )
    except ip.InitError as e:
        print(f"  error: {e}", file=sys.stderr)
        return 1

    a = result.answers
    print(f"\n  → {result.dest}  ({a.slug}, from {result.source})")
    counts = [f"{len(result.written)} files written"]
    if result.overwritten:
        counts.append(f"{len(result.overwritten)} {'rewritten' if args.in_place else 'overwritten'}")
    if result.removed:
        counts.append("removed " + ", ".join(result.removed))
    print("    " + "; ".join(counts))
    print("    documents: " + ", ".join(f"src/{d}/" for d in result.documents))
    if not args.no_skills:
        print(
            f"    agent skill: {ip.SKILL_DIRS[0]}/{ip.SKILL_NAME}/ (Claude Code: "
            f"/{ip.SKILL_NAME}) and {ip.SKILL_DIRS[1]}/{ip.SKILL_NAME}/"
        )
    if result.git:
        print(f"    git: {result.git}")
    first = result.documents[0] if result.documents else "manuscript"
    print("\n  next:")
    if result.dest.resolve() != Path.cwd().resolve():
        print(f"    cd {result.dest}")
    print(ip.commented([
        ("uv sync", "document-sanity, pinned"),
        (f"make html VERSION={first}", f"→ out/{first}/html/index.html"),
        (f"make word VERSION={first}", f"→ out/{first}/word/main.docx"),
        (f"make pdf VERSION={first}", "needs TeX (pdflatex, bibtex)"),
        ("uv run document-sanity check", "every target, before you share"),
    ], indent="    "))
    return 0


def cmd_skills(args: argparse.Namespace) -> int:
    """Install (or refresh) the agent skill in an existing project."""
    from . import init_project as ip
    from .project import find_project_root

    root = find_project_root(Path(args.root)) or Path(args.root).resolve()
    try:
        plan = ip.install_skill(root, force=args.force)
    except ip.InitError as e:
        print(f"  error: {e}", file=sys.stderr)
        return 1
    changed = len(plan.create) + len(plan.conflicts)
    for base in ip.SKILL_DIRS:
        print(f"  → {base}/{ip.SKILL_NAME}/")
    print(f"    v{__version__}: {changed} file(s) written, {len(plan.unchanged)} already current")
    return 0


def _project(args: argparse.Namespace, command: str, *, here_only: bool = True):
    """(root, chosen docs) for the project-wide commands, or an exit code.

    With no documents named, `here_only` narrows to the document the start
    folder sits in (as `check` does); otherwise it's every document.
    """
    from .project import find_project_root, select_documents

    start = Path(args.root)
    root = find_project_root(start)
    if root is None:
        print(
            f"  error: `{command}` works in a project — a folder whose src/ holds "
            "<doc>/manifest.yaml (see `document-sanity init`)",
            file=sys.stderr,
        )
        return None, 1
    wanted = list(args.docs or []) + list(getattr(args, "version", None) or [])
    try:
        return (root, select_documents(root, wanted, start if here_only else None)), 0
    except ValueError as e:
        print(f"  error: {e}", file=sys.stderr)
        return None, 1


_MARKS = {"ok": "✓", "error": "✗", "warn": "!", "skip": "-"}


def _print_result(result, verbose: bool) -> None:
    print(f"\n  {result.doc}")
    for step in result.steps:
        print(f"    {_MARKS[step.status]} {step.name:<8} {step.detail}")
        if step.status in ("error", "warn") or verbose:
            for note in step.notes[:20]:
                print(f"        {note}")
            if len(step.notes) > 20:
                print(f"        … and {len(step.notes) - 20} more")


def cmd_check(args: argparse.Namespace) -> int:
    """Build every target of the chosen documents and run preview --check."""
    from .check import build_document

    found, code = _project(args, "check")
    if found is None:
        return code
    root, docs = found
    print(f"  checking {len(docs)} document{'s' * (len(docs) != 1)} in {root}: {', '.join(docs)}")
    errors = warnings = 0
    for doc in docs:
        result = build_document(
            root, doc, pdf=not args.no_pdf, compiler=args.compiler, verbose=args.verbose,
        )
        _print_result(result, args.verbose)
        errors += len(result.errors)
        warnings += len(result.warnings)
    print()
    if errors:
        print(f"  {errors} error{'s' * (errors != 1)}, {warnings} warning{'s' * (warnings != 1)}")
        return 1
    print("  ok: every target builds" + (" (see warnings)" if warnings else "")
          + f"; outputs in {os.path.relpath(root / 'out')}/")
    return 0


def cmd_site(args: argparse.Namespace) -> int:
    """Build the chosen documents and gather them into a static site."""
    import yaml

    from .site import SiteError, build_site

    found, code = _project(args, "site", here_only=False)
    if found is None:
        return code
    root, docs = found
    out = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    print(f"  building {len(docs)} document{'s' * (len(docs) != 1)}: {', '.join(docs)}")
    try:
        report = build_site(
            root, docs, out, pdf=not args.no_pdf, allow_notice=args.allow_notice,
            compiler=args.compiler, verbose=args.verbose,
        )
    except (SiteError, yaml.YAMLError, OSError, ValueError) as e:
        print(f"  error: {e}", file=sys.stderr)
        return 1
    for result in report.results:
        _print_result(result, args.verbose)
    if report.failed:
        names = ", ".join(r.doc for r in report.failed)
        print(f"\n  error: {names} didn't build; nothing was written to {os.path.relpath(out)}/", file=sys.stderr)
        return 1
    print(f"\n  → {os.path.relpath(out)}/index.html  ({len(report.published)} documents)")
    print(f"    serve it: python3 -m http.server --directory {os.path.relpath(out)} 8000")
    return 0


def cmd_pages_init(args: argparse.Namespace) -> int:
    """Write the GitHub Pages workflow into a project, once the user agrees it's public."""
    import yaml

    from . import pages

    found, code = _project(args, "pages init", here_only=False)
    if found is None:
        return code
    root, _ = found
    warning = (
        "  A GitHub Pages site is PUBLIC: anyone with the link can read it, even when\n"
        "  the repository is private. Every published document goes up as an HTML\n"
        "  viewer (numbers and their provenance included), a PDF and a Word file."
    )
    if not args.yes:
        if not sys.stdin.isatty():
            print(warning, file=sys.stderr)
            print(
                "\n  error: confirm with the person who owns these documents, then rerun "
                "with --yes", file=sys.stderr,
            )
            return 1
        print(warning)
        if _ask("Publish them publicly? (yes/no)", "no").lower() not in ("y", "yes"):
            print("  nothing written")
            return 1
    try:
        report = pages.pages_init(
            root, branch=args.branch, only_repo=args.only_repo, docs=args.docs or None,
            pdf=not args.no_pdf, allow_notice=args.allow_notice, force=args.force,
        )
    except (pages.PagesError, yaml.YAMLError, OSError) as e:
        print(f"  error: {e}", file=sys.stderr)
        return 1

    print(f"  → {os.path.relpath(report.path)}")
    print(f"    publishes: {', '.join(report.docs) if args.docs else 'every document under src/'}"
          + (" (HTML + Word; no PDF)" if args.no_pdf else " (HTML, PDF, Word)"))
    for note in report.notes:
        print(f"  ! {note}")
    remote = pages.github_remote(root)
    slug = "/".join(remote) if remote else "OWNER/REPO"
    url = f"https://{remote[0]}.github.io/{remote[1]}/" if remote else "https://OWNER.github.io/REPO/"
    print("\n  next:")
    print("    0. try it: uv run document-sanity site   (→ site/, what the workflow uploads)")
    print("    1. Settings → Pages → Source: GitHub Actions, or")
    print(f"       gh api -X POST repos/{slug}/pages -f build_type=workflow   (PUT if Pages is already on)")
    print(f"    2. commit {pages.WORKFLOW_PATH} and uv.lock, and push to {args.branch}")
    print(f"    3. the site appears at {url}")
    return 0


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
            layout=not args.no_layout,
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


def _resolve_drawio_target(target: str, root: str,
                           version: Optional[str]) -> Optional[Path]:
    """Resolve a `drawio` subcommand target: a .drawio path or a figure id."""
    p = Path(target)
    if p.suffix == '.drawio' or p.exists():
        if not p.exists():
            print(f"  Error: File not found: {p}", file=sys.stderr)
            return None
        return p.resolve()

    from .build import find_latest_version

    root_dir = Path(root).resolve()
    if version is None:
        try:
            version = find_latest_version(root_dir)
            print(f"  Auto-detected version: {version}")
        except ValueError as e:
            print(f"  Error: {e}", file=sys.stderr)
            return None
    candidate = root_dir / "src" / version / "figures" / target / f"{target}.drawio"
    if not candidate.exists():
        print(f"  Error: No .drawio file for figure '{target}': {candidate}",
              file=sys.stderr)
        return None
    return candidate


def cmd_drawio(args: argparse.Namespace) -> int:
    """Sync/compose draw.io figures with re-importable source assets."""
    from . import drawio_fig

    if args.drawio_command == 'sync':
        drawio_path = _resolve_drawio_target(args.target, args.root, args.version)
        if drawio_path is None:
            return 1

        try:
            results = drawio_fig.sync_file(drawio_path, force=args.force)
        except ValueError as e:
            print(f"  Error: {e}", file=sys.stderr)
            return 1
        if not results:
            print("  No managed assets found (add ds-source attributes via "
                  "Edit Data, or use `drawio add-asset`)")
        failed = False
        for r in results:
            print(f"  [{r.action}] {r.asset_id}")
            for w in r.warnings:
                print(f"    ! {w}")
            if r.action in ('missing-source', 'error'):
                failed = True

        png_path = drawio_path.with_suffix('.png')
        if args.no_export:
            if not png_path.exists():
                print(f"  Note: no exported {png_path.name} exists yet — builds "
                      f"will not pick up this figure until you export")
        else:
            if drawio_fig.export_png(drawio_path, png_path, app=args.app):
                print(f"  Exported: {png_path}")
            else:
                failed = True
        return 1 if failed else 0

    if args.drawio_command == 'add-asset':
        drawio_path = Path(args.drawio_path).resolve()
        if not drawio_path.exists():
            print(f"  Error: File not found: {drawio_path}", file=sys.stderr)
            return 1
        src_path = drawio_fig.resolve_source(args.source, drawio_path)
        if src_path is None:
            print(f"  Error: Source image not found: {args.source}", file=sys.stderr)
            return 1

        crop = None
        if args.crop:
            try:
                crop = tuple(int(v) for v in args.crop.split(','))
                if len(crop) != 4:
                    raise ValueError
            except ValueError:
                print(f"  Error: --crop must be 'x,y,w,h' integers", file=sys.stderr)
                return 1
        at = (40.0, 40.0)
        if args.at:
            try:
                x, y = (float(v) for v in args.at.split(','))
                at = (x, y)
            except ValueError:
                print(f"  Error: --at must be 'x,y'", file=sys.stderr)
                return 1

        try:
            root = drawio_fig.load_mxfile(drawio_path.read_text(encoding='utf-8'))
            asset = drawio_fig.add_asset(
                root, args.source, src_path,
                crop=crop, at=at, width=args.width, page_index=args.page,
            )
            drawio_path.write_text(drawio_fig.serialize_mxfile(root), encoding='utf-8')
        except (ValueError, RuntimeError) as e:
            print(f"  Error: {e}", file=sys.stderr)
            return 1
        print(f"  Added asset '{asset.cell_id}' ({args.source}) to {drawio_path.name}")
        print(f"  Next: massage layout in draw.io, then `document-sanity drawio sync`")
        return 0

    if args.drawio_command == 'status':
        drawio_path = _resolve_drawio_target(args.target, args.root, args.version)
        if drawio_path is None:
            return 1
        try:
            root = drawio_fig.load_mxfile(drawio_path.read_text(encoding='utf-8'))
            assets = drawio_fig.find_assets(root)
        except ValueError as e:
            print(f"  Error: {e}", file=sys.stderr)
            return 1
        if not assets:
            print("  No managed assets found")
            return 0
        stale = False
        for asset in assets:
            status = drawio_fig.asset_status(asset, drawio_path)
            print(f"  [{status}] {asset.cell_id} <- {asset.source}")
            if status != 'fresh':
                stale = True
        png_path = drawio_path.with_suffix('.png')
        if not png_path.exists():
            print(f"  [missing] exported {png_path.name}")
            stale = True
        elif png_path.stat().st_mtime < drawio_path.stat().st_mtime:
            print(f"  [stale] exported {png_path.name} is older than the .drawio")
            stale = True
        return 1 if stale else 0

    print("  Error: specify a drawio subcommand (sync, add-asset, status)",
          file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="document-sanity",
        description="Build PDF (LaTeX), an interactive HTML viewer and Word from Markdown "
                    "and one manifest.yaml per document, with variables that carry provenance.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- init ---
    init_p = subparsers.add_parser(
        "init",
        help="Start a new project from the template in DIR (no git needed)",
        description=(
            "Copy the document-sanity-template snapshot that ships with this release "
            "into DIR, name it, and install the agent skill. DIR may be new, empty, or "
            "an existing folder to knit into: existing files are never overwritten "
            "without --force, and a folder that already has documents under src/ is "
            "refused. Unset answers are prompted for (or defaulted with --yes)."
        ),
    )
    init_p.add_argument('dir', nargs='?', default='.', metavar='DIR', help='Default: the current folder')
    init_p.add_argument('--from', dest='source', default=None, metavar='gh:OWNER/REPO[@REF]',
                        help="Start from a GitHub repo (e.g. your lab's fork of the template) instead")
    init_p.add_argument('--name', default=None, help="Project name (kebab-case; default: DIR's name)")
    init_p.add_argument('--title', default=None, help='Document title (every starter you keep)')
    init_p.add_argument('--author', default=None, help='Author name (default: git config user.name)')
    init_p.add_argument('--email', default=None, help='Author email (default: git config user.email)')
    init_p.add_argument('--description', default=None, help='One-line description')
    init_p.add_argument('--starter', action='append', default=None, metavar='NAME',
                        help="Starter documents to keep: manuscript, proposal, or both "
                             "(default: both; repeat or comma-separate)")
    init_p.add_argument('-y', '--yes', action='store_true', help="Don't prompt; use defaults")
    init_p.add_argument('--git', action='store_true', help='git init and make a first commit')
    init_p.add_argument('--force', action='store_true', help='Overwrite files that already exist')
    init_p.add_argument('--no-skills', action='store_true', help="Don't install the agent skill")
    init_p.add_argument('--in-place', action='store_true',
                        help="Initialize a template copy where it stands (what the template's init.py runs)")

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
    word_p.add_argument('--no-layout', action='store_true',
                        help="Skip the layout pass (table rows, headings and figures kept "
                             "together on a page; equations at the body font size)")
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

    # --- drawio ---
    drawio_p = subparsers.add_parser(
        "drawio", help="Sync/compose draw.io figures with re-importable source assets")
    drawio_sub = drawio_p.add_subparsers(dest="drawio_command")

    sync_p = drawio_sub.add_parser(
        "sync", help="Re-import source assets from current .drawio state and export PNG")
    sync_p.add_argument('target', help='Path to a .drawio file, or a figure id')
    sync_p.add_argument('--root', '-r', default='.', help='Project root directory')
    sync_p.add_argument('--version', '-V', help='Version (default: auto-detect latest)')
    sync_p.add_argument('--no-export', action='store_true',
                        help='Skip the draw.io PNG export step')
    sync_p.add_argument('--force', action='store_true',
                        help='Re-embed assets even when the source hash is unchanged')
    sync_p.add_argument('--app', help='Path to the draw.io binary (or set $DRAWIO_APP)')

    addp_p = drawio_sub.add_parser(
        "add-asset", help="Import a source image as a managed, re-syncable asset")
    addp_p.add_argument('drawio_path', help='Path to the .drawio file')
    addp_p.add_argument('--source', required=True,
                        help='Source image path (stored as ds-source, resolved '
                             'relative to the .drawio file)')
    addp_p.add_argument('--crop', help="Crop rect 'x,y,w,h' in source pixel coords")
    addp_p.add_argument('--at', help="Position 'x,y' in diagram coords (default 40,40)")
    addp_p.add_argument('--width', type=float,
                        help='Display width in diagram units (height from aspect)')
    addp_p.add_argument('--page', type=int, default=0, help='Page index (default 0)')

    status_p = drawio_sub.add_parser(
        "status", help="Check asset/export freshness (exit 1 if anything stale)")
    status_p.add_argument('target', help='Path to a .drawio file, or a figure id')
    status_p.add_argument('--root', '-r', default='.', help='Project root directory')
    status_p.add_argument('--version', '-V', help='Version (default: auto-detect latest)')

    # --- skills ---
    skills_p = subparsers.add_parser(
        "skills", help="Install or refresh the agent skill in .claude/skills/ and .agents/skills/")
    skills_p.add_argument('--root', '-r', default='.', help='Project root (default: found from cwd)')
    skills_p.add_argument('--force', action='store_true', help="Overwrite a skill you've edited")

    # --- check / site: shared options ---
    docs_help = ("Documents (folders under src/). Default: all of them, or the one "
                 "you're inside.")

    def project_wide(p: argparse.ArgumentParser) -> None:
        p.add_argument('docs', nargs='*', metavar='DOC', help=docs_help)
        p.add_argument('--version', '-V', action='append', default=None, metavar='DOC',
                       help='Same as DOC (repeatable), for symmetry with the other commands')
        p.add_argument('--root', '-r', default='.', help='Where to start (the project root is found by walking up)')
        p.add_argument('--no-pdf', action='store_true', help='Skip the PDF (no TeX needed); the LaTeX tree still builds')
        p.add_argument('--compiler', default='pdflatex',
                       choices=['pdflatex', 'xelatex', 'lualatex', 'latexmk'], help='LaTeX compiler')
        p.add_argument('--verbose', '-v', action='store_true', help="Show every builder's output")

    check_p = subparsers.add_parser(
        "check",
        help="Build every target (PDF, HTML, Word) and run preview --check: one command before sharing",
    )
    project_wide(check_p)

    site_p = subparsers.add_parser(
        "site",
        help="Build every document and gather HTML, PDF and Word into site/ with an index page",
    )
    project_wide(site_p)
    site_p.add_argument('--out', '-o', default='site',
                        help='Output folder, relative to the project root (default: site/)')
    site_p.add_argument('--allow-notice', action='store_true',
                        help="Publish documents whose manifest sets metadata.notice "
                             "(only with the owner's explicit OK)")

    # --- pages ---
    pages_p = subparsers.add_parser("pages", help="Publish on GitHub Pages")
    pages_sub = pages_p.add_subparsers(dest="pages_command", required=True)
    pages_init_p = pages_sub.add_parser(
        "init",
        help="Write .github/workflows/pages.yml (builds every document's HTML, PDF and Word)",
        description=(
            "Write the GitHub Pages workflow. A Pages site is public even from a private "
            "repository, so this asks first (--yes once the owner has agreed), and refuses "
            "documents whose manifest sets metadata.notice unless --allow-notice."
        ),
    )
    pages_init_p.add_argument('docs', nargs='*', metavar='DOC',
                              help='Publish only these documents (default: every document under src/)')
    pages_init_p.add_argument('--root', '-r', default='.', help='Where to start (the project root is found by walking up)')
    pages_init_p.add_argument('--yes', '-y', action='store_true',
                              help='The owner has agreed the site is public; skip the prompt')
    pages_init_p.add_argument('--no-pdf', action='store_true',
                              help='Publish HTML and Word only; the runner skips installing TeX')
    pages_init_p.add_argument('--allow-notice', action='store_true',
                              help="Publish documents whose manifest sets metadata.notice "
                                   "(only with the owner's explicit OK)")
    pages_init_p.add_argument('--branch', default='main', help='Deploy on pushes to this branch')
    pages_init_p.add_argument('--only-repo', default=None, metavar='OWNER/NAME',
                              help='Deploy only from this repository; forks and template copies skip the job')
    pages_init_p.add_argument('--force', action='store_true', help='Overwrite an existing workflow')

    return parser


HANDLERS = {
    'init': cmd_init,
    'skills': cmd_skills,
    'build': cmd_build,
    'new-version': cmd_new_version,
    'import': cmd_import,
    'preview': cmd_preview,
    'html': cmd_html,
    'word': cmd_word,
    'convert': cmd_convert,
    'drawio': cmd_drawio,
    'check': cmd_check,
    'site': cmd_site,
    'pages': cmd_pages_init,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler = HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
