#!/usr/bin/env python3
r"""
Build pipeline for document-sanity v2.

Pipeline:
  src/<version>/docs/*.md  -->  out/<version>/latex/sections/*.tex
  src/<version>/manifest.yaml  -->  out/<version>/latex/main.tex
  out/<version>/latex/  -->  out/<version>/pdf/main.pdf

Supports both the new src/ structure and legacy pigean-style structures.
"""

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .manifest import Manifest
from .variable_processor import VariableProcessor
from .md2latex import convert_md_file, md_to_latex


class ManuscriptBuilder:
    """Build a manuscript from src/ to out/."""

    def __init__(
        self,
        root_dir: Path,
        version: str,
        placeholder: str = "XXXX",
        strict: bool = False,
        verbose: bool = False,
        compile_pdf: bool = False,
        compiler: str = "pdflatex",
    ):
        self.root_dir = root_dir
        self.version = version
        self.placeholder = placeholder
        self.strict = strict
        self.verbose = verbose
        self.compile_pdf = compile_pdf
        self.compiler = compiler

        # Source paths
        self.src_dir = root_dir / "src" / version
        self.manifest_path = self.src_dir / "manifest.yaml"
        self.templates_dir = root_dir / "templates"

        # Output paths
        self.out_dir = root_dir / "out" / version
        self.out_latex_dir = self.out_dir / "latex"
        self.out_sections_dir = self.out_latex_dir / "sections"
        self.out_pdf_dir = self.out_dir / "pdf"
        self.out_main_file = self.out_latex_dir / "main.tex"

        # Load manifest
        self.manifest = Manifest(self.manifest_path)

        # Variable processor (with figure support from manifest)
        self.processor = VariableProcessor(
            placeholder=placeholder,
            figures={fid: entry for fid, entry in self.manifest.figures.items()},
            figures_dir=self.src_dir / "figures",
            target="pdf",
        )

    def _resolve_template(self) -> str:
        """Load and resolve the LaTeX template."""
        template_name = self.manifest.get_template_name()
        template_path = self.templates_dir / f"{template_name}.tex"

        if not template_path.exists():
            # Fall back to built-in article template
            from .init import ARTICLE_TEMPLATE
            return ARTICLE_TEMPLATE

        return template_path.read_text(encoding='utf-8')

    def _build_title_block(self) -> str:
        """Generate LaTeX title/author/affiliation block from manifest metadata.

        If the template already contains \\maketitle, we don't add it again.
        """
        meta = self.manifest.metadata
        template_name = self.manifest.get_template_name()
        lines = []

        if meta.title:
            lines.append(f'\\title{{{meta.title}}}')

        if meta.authors:
            author_parts = []
            for a in meta.authors:
                name = a.name
                if a.affiliations:
                    affil_str = ','.join(str(x) for x in a.affiliations)
                    name = name + '\\textsuperscript{' + affil_str + '}'
                author_parts.append(name)
            and_sep = ' \\and '
            lines.append('\\author{' + and_sep.join(author_parts) + '}')

        if meta.affiliations:
            affil_lines = []
            for num, info in sorted(meta.affiliations.items()):
                if isinstance(info, dict):
                    parts = []
                    if 'department' in info:
                        parts.append(info['department'])
                    if 'institution' in info:
                        parts.append(info['institution'])
                    affil_str = ', '.join(parts)
                else:
                    affil_str = str(info)
                affil_lines.append('\\textsuperscript{' + str(num) + '}' + affil_str)
            if affil_lines:
                sep = '  \\\\  '
                lines.append('\\date{' + sep.join(affil_lines) + '}')

        return '\n'.join(lines)

    def _build_abstract_block(self) -> str:
        """Generate LaTeX abstract block.

        Uses \\abstract{} for sn-jnl class (nature template),
        \\begin{abstract} for standard article class.
        """
        if not self.manifest.metadata.abstract:
            return ''

        abstract = self.manifest.metadata.abstract.strip()
        # Process variables in abstract
        abstract = self.processor.replace_variables(abstract, 'manifest.yaml:abstract')

        template_name = self.manifest.get_template_name()
        lines = []

        if template_name == 'nature':
            # sn-jnl uses \abstract{...} syntax
            lines.append('\\abstract{')
            lines.append(abstract)
            lines.append('}')
            if self.manifest.metadata.keywords:
                kw = ', '.join(self.manifest.metadata.keywords)
                lines.append(f'\\keywords{{{kw}}}')
        else:
            lines.append('\\begin{abstract}')
            lines.append(abstract)
            lines.append('\\end{abstract}')
            if self.manifest.metadata.keywords:
                kw = ', '.join(self.manifest.metadata.keywords)
                lines.append(f'\\textbf{{Keywords:}} {kw}')

        return '\n'.join(lines)

    def load_variables(self) -> None:
        """Load variables from the manifest."""
        print(f"\n  Loading variables...")
        values = self.manifest.get_variable_values()
        self.processor.variables.update(values)
        print(f"    Loaded {len(values)} variables from manifest")

        n_prov = sum(1 for v in self.manifest.variables.values() if v.provenance)
        if n_prov > 0:
            print(f"    {n_prov} variables have provenance records")

    def convert_sections(self) -> list[str]:
        """Convert markdown sections to LaTeX and process variables.

        Returns list of output .tex paths relative to out_latex_dir.
        """
        print(f"\n  Converting sections...")
        self.out_sections_dir.mkdir(parents=True, exist_ok=True)

        section_tex_paths = []
        pseudo_sections = {'_bibliography', '_toc'}
        for section_ref in self.manifest.sections:
            # Pass through pseudo-sections (handled in assemble_main)
            if section_ref in pseudo_sections:
                section_tex_paths.append(section_ref)
                continue

            src_path = self.src_dir / section_ref

            if not src_path.exists():
                print(f"    WARNING: Section not found: {section_ref}")
                continue

            # Determine output .tex name
            stem = src_path.stem
            out_name = f"{stem}.tex"
            out_path = self.out_sections_dir / out_name
            rel_path = f"sections/{out_name}"

            if src_path.suffix == '.md':
                if self.verbose:
                    print(f"    [md->tex] {section_ref} -> {rel_path}")

                # Convert md -> tex (with escape_text=False for LaTeX pass-through)
                convert_md_file(src_path, out_path, escape_text=False)

                # Then process variables
                content = out_path.read_text(encoding='utf-8')
                processed = self.processor.replace_variables(content, str(src_path))
                out_path.write_text(processed, encoding='utf-8')

            elif src_path.suffix == '.tex':
                if self.verbose:
                    print(f"    [tex] {section_ref} -> {rel_path}")
                self.processor.process_file(src_path, out_path)

            else:
                print(f"    WARNING: Unknown section type: {section_ref}")
                continue

            section_tex_paths.append(rel_path)

        print(f"    Converted {len(section_tex_paths)} sections")
        return section_tex_paths

    def assemble_main(self, section_paths: list[str]) -> None:
        """Assemble the main.tex from template + metadata + sections.

        Supports special pseudo-sections in the manifest:
          _bibliography  -> inserts \\bibliography{references} at that point
          _toc           -> inserts \\tableofcontents at that point
        """
        print(f"\n  Assembling main.tex...")

        template = self._resolve_template()
        title_block = self._build_title_block()
        abstract_block = self._build_abstract_block()

        # Resolve bibliography
        bib_cmd = ''
        template_name = self.manifest.get_template_name()

        refs_path = self.src_dir / "references.bib"
        if refs_path.exists():
            shutil.copy2(refs_path, self.out_latex_dir / "references.bib")
            bib_cmd = '\\bibliography{references}'

        root_refs = self.root_dir / "references.bib"
        if root_refs.exists() and not refs_path.exists():
            shutil.copy2(root_refs, self.out_latex_dir / "references.bib")
            bib_cmd = '\\bibliographystyle{plain}\n\\bibliography{references}'

        # Build content block, handling pseudo-sections
        content_lines = []
        bib_placed = False
        for sec_path in section_paths:
            if sec_path == '_bibliography':
                if bib_cmd:
                    content_lines.append(bib_cmd)
                    content_lines.append('')
                bib_placed = True
            elif sec_path == '_toc':
                content_lines.append('\\tableofcontents')
                content_lines.append('\\newpage')
                content_lines.append('')
            else:
                content_lines.append(f'\\input{{{sec_path}}}')
                content_lines.append('')

        content_block = '\n'.join(content_lines)

        # If bibliography wasn't placed inline, put it at the end (default)
        bib_block = '' if bib_placed else bib_cmd

        # Fill template. Accept both current %%DOCUMENT_SANITY:* markers and
        # legacy %%LATEX_BUILDER:* markers — paper repos authored against the
        # old tool name keep building without a forced edit.
        main_tex = template
        for markers, replacement in [
            (('%%DOCUMENT_SANITY:PACKAGES', '%%LATEX_BUILDER:PACKAGES'), ''),
            (('%%DOCUMENT_SANITY:TITLE', '%%LATEX_BUILDER:TITLE'), title_block),
            (('%%DOCUMENT_SANITY:ABSTRACT', '%%LATEX_BUILDER:ABSTRACT'), abstract_block),
            (('%%DOCUMENT_SANITY:CONTENT', '%%LATEX_BUILDER:CONTENT'), content_block),
            (('%%DOCUMENT_SANITY:BIBLIOGRAPHY', '%%LATEX_BUILDER:BIBLIOGRAPHY'), bib_block),
        ]:
            for marker in markers:
                main_tex = main_tex.replace(marker, replacement)

        # Process any remaining variables in main.tex
        main_tex = self.processor.replace_variables(main_tex, 'main.tex')

        self.out_latex_dir.mkdir(parents=True, exist_ok=True)
        self.out_main_file.write_text(main_tex, encoding='utf-8')
        print(f"    Written: {self.out_main_file}")

    def copy_figures(self) -> int:
        """Copy figures to output directory, auto-cropping raster whitespace."""
        from .figure_crop import copy_with_crop, pillow_available

        print(f"\n  Copying figures...")
        figures_src = self.src_dir / "figures"
        figures_dest = self.out_latex_dir / "figures"

        if not figures_src.exists():
            print(f"    No figures directory found")
            return 0

        figures_dest.mkdir(parents=True, exist_ok=True)

        # Per-figure crop toggle: manifest entries can set `crop: false` to
        # opt out. Lookup by basename since output is flat.
        crop_by_stem: dict[str, bool] = {}
        for fig_id, entry in self.manifest.figures.items():
            for p in [entry.source] + list(entry.formats.values()):
                if p:
                    crop_by_stem[Path(p).stem] = entry.crop

        n_copied = n_cropped = 0
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.pdf', '*.eps', '*.svg']:
            for fig in figures_src.rglob(ext):
                dest = figures_dest / fig.name
                crop = crop_by_stem.get(fig.stem, True)
                mode, info = copy_with_crop(fig, dest, crop=crop)
                if mode == 'cropped':
                    n_cropped += 1
                    n_copied += 1
                    if self.verbose and info:
                        print(f"    [cropped] {fig.name}: {info}")
                elif mode == 'copied':
                    n_copied += 1

        msg = f"    Copied {n_copied} figures"
        if pillow_available():
            msg += f" ({n_cropped} cropped)"
        else:
            msg += " (Pillow not installed — cropping skipped)"
        print(msg)
        return n_copied

    def copy_tables(self) -> int:
        """Copy table files to output directory."""
        print(f"\n  Copying tables...")
        tables_src = self.src_dir / "tables"
        tables_dest = self.out_latex_dir / "tables"

        if not tables_src.exists():
            print(f"    No tables directory found")
            return 0

        tables_dest.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in tables_src.iterdir():
            if f.is_file():
                shutil.copy2(f, tables_dest / f.name)
                count += 1

        print(f"    Copied {count} table files")
        return count

    def copy_supporting_files(self) -> None:
        """Copy .bst, .cls files from templates/ to output."""
        print(f"\n  Copying supporting files...")
        count = 0

        # From templates/
        if self.templates_dir.exists():
            for ext in ['.bst', '.cls', '.sty', '.eps']:
                for f in self.templates_dir.glob(f'*{ext}'):
                    shutil.copy2(f, self.out_latex_dir / f.name)
                    if self.verbose:
                        print(f"    {f.name}")
                    count += 1

        # From project root
        for ext in ['.bst', '.cls', '.sty', '.eps']:
            for f in self.root_dir.glob(f'*{ext}'):
                dest = self.out_latex_dir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    count += 1

        print(f"    Copied {count} supporting files")

    def compile_to_pdf(self) -> bool:
        """Compile the assembled LaTeX to PDF.

        Runs the compiler in the latex dir so that pdflatex, bibtex, and the
        bib/bst/cls files all live in the same working directory. This avoids
        bibtex's openout_any=p restriction on writing to absolute paths.
        The final PDF is moved into the pdf/ dir.
        """
        print(f"\n  Compiling to PDF...")
        self.out_pdf_dir.mkdir(parents=True, exist_ok=True)

        main_name = "main"
        main_tex = f"{main_name}.tex"

        if self.compiler == "latexmk":
            cmd = ['latexmk', '-pdf', '-interaction=nonstopmode', main_tex]
            subprocess.run(cmd, capture_output=True, text=True,
                          cwd=self.out_latex_dir)
        else:
            cmd_base = [self.compiler, '-interaction=nonstopmode']

            # Pass 1: produces .aux with \citation entries
            print(f"    Pass 1/3: {self.compiler}...")
            subprocess.run(cmd_base + [main_tex], capture_output=True,
                          text=True, cwd=self.out_latex_dir)

            # BibTeX: reads .aux, produces .bbl
            bib_files = list(self.out_latex_dir.glob("*.bib"))
            if bib_files:
                print(f"    BibTeX...")
                result = subprocess.run(['bibtex', main_name],
                             capture_output=True, text=True,
                             cwd=self.out_latex_dir)
                if result.returncode != 0 and self.verbose:
                    print(f"    BibTeX stderr: {result.stderr}")
                    print(f"    BibTeX stdout: {result.stdout[-500:]}")

            for i in [2, 3]:
                print(f"    Pass {i}/3: {self.compiler}...")
                subprocess.run(cmd_base + [main_tex], capture_output=True,
                             text=True, cwd=self.out_latex_dir)

        # Move the generated PDF and log artifacts into out_pdf_dir
        built_pdf = self.out_latex_dir / f"{main_name}.pdf"
        if built_pdf.exists():
            shutil.copy2(built_pdf, self.out_pdf_dir / f"{main_name}.pdf")
            for ext in ['.log', '.aux', '.out', '.toc', '.bbl', '.blg']:
                f = self.out_latex_dir / f"{main_name}{ext}"
                if f.exists():
                    shutil.copy2(f, self.out_pdf_dir / f.name)
            print(f"    PDF generated: {self.out_pdf_dir / f'{main_name}.pdf'}")
            return True
        else:
            print(f"    PDF generation failed")
            return False

    def generate_build_log(self) -> None:
        """Write a build metadata log."""
        import json
        log = {
            'version': self.version,
            'built_at': datetime.now().isoformat(),
            'template': self.manifest.get_template_name(),
            'sections': self.manifest.sections,
            'variables_count': len(self.manifest.variables),
            'variables_with_provenance': sum(
                1 for v in self.manifest.variables.values() if v.provenance
            ),
            'figures_count': len(self.manifest.figures),
            'tables_count': len(self.manifest.tables),
        }
        log_path = self.out_dir / "build.json"
        log_path.write_text(json.dumps(log, indent=2))

    def build(self) -> bool:
        """Run the complete build pipeline."""
        print(f"\n{'='*60}")
        print(f"  Building: {self.version}")
        print(f"  Source:   {self.src_dir}")
        print(f"  Output:   {self.out_dir}")
        print(f"{'='*60}")

        if not self.src_dir.exists():
            print(f"\n  ERROR: Source directory not found: {self.src_dir}")
            return False

        if not self.manifest_path.exists():
            print(f"\n  ERROR: Manifest not found: {self.manifest_path}")
            return False

        # Clean output
        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.out_latex_dir.mkdir(parents=True, exist_ok=True)

        # Pipeline
        self.load_variables()
        section_paths = self.convert_sections()
        self.assemble_main(section_paths)
        self.copy_figures()
        self.copy_tables()
        self.copy_supporting_files()
        self.generate_build_log()

        # Report
        self.processor.print_report(verbose=self.verbose)

        has_errors = False
        if self.processor.has_undefined_variables():
            if self.strict:
                print(f"\n  BUILD FAILED: undefined variables (strict mode)")
                has_errors = True
            else:
                print(f"\n  Build completed with warnings")

        if not has_errors:
            print(f"\n  Build complete!")
            print(f"  LaTeX:  {self.out_latex_dir}")
            print(f"  Main:   {self.out_main_file}")

        # Compile
        if self.compile_pdf and not has_errors:
            self.compile_to_pdf()

        return not has_errors


def find_latest_version(root_dir: Path) -> str:
    """Find the latest version in src/."""
    src_dir = root_dir / "src"
    if not src_dir.exists():
        raise ValueError(f"No src/ directory found in {root_dir}")

    versions = [d.name for d in src_dir.iterdir() if d.is_dir() and (d / "manifest.yaml").exists()]
    if not versions:
        raise ValueError(f"No versions found in {src_dir} (no manifest.yaml)")

    # Try to sort by date (MMDDYYYY prefix), then alphabetically
    from .version import parse_version_date
    dated = [(v, parse_version_date(v)) for v in versions]
    dated_with_time = [(v, d) for v, d in dated if d is not None]
    undated = [v for v, d in dated if d is None]

    if dated_with_time:
        dated_with_time.sort(key=lambda x: x[1], reverse=True)
        return dated_with_time[0][0]
    else:
        return sorted(undated)[-1]
