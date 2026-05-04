#!/usr/bin/env python3
"""
Build a Word (.docx) output from a version's src/ tree.

Parallels ManuscriptBuilder but emits a .docx instead of a .tex/.pdf.

Pipeline:
  src/<version>/docs/*.md        --\\
  src/<version>/manifest.yaml    ---+--> out/<version>/word/main.docx
  templates/<name>.docx          ---/
  src/<version>/figures/*        --(embedded into the docx zip)
  src/<version>/references.bib   --(rendered as References section when cited)

Shares these pieces with the LaTeX pipeline:
  - manifest.py: metadata, sections, variables, figures, tables
  - variable_processor.py: {{VAR}} substitution (with target="word")
  - manifest.resolve_figure: picks the best image format for the 'word' target
  - bib.py: bibtex parsing and author/title/venue cleanup
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional

from .bib import (
    BibEntry,
    _clean_tex,
    _format_authors,
    load_bib,
    parse_bib,
)
from .docx_content import ContentBuilder, TextStyle
from .docx_extract import extract_styles
from .docx_styles import default_styles, load_styles
from .docx_template import TemplateDocument, TemplateDocumentConfig
from .docx_xml import RichText
from .manifest import Manifest, resolve_figure
from .md2docx import render_markdown
from .variable_processor import VariableProcessor


class WordBuilder:
    def __init__(
        self,
        root_dir: Path,
        version: str,
        *,
        template_override: Optional[Path] = None,
        styles_override: Optional[Path] = None,
        placeholder: str = "XXXX",
        strict: bool = False,
        verbose: bool = False,
    ):
        self.root_dir = root_dir
        self.version = version
        self.placeholder = placeholder
        self.strict = strict
        self.verbose = verbose

        self.src_dir = root_dir / "src" / version
        self.manifest_path = self.src_dir / "manifest.yaml"
        self.templates_dir = root_dir / "templates"
        self.figures_dir = self.src_dir / "figures"

        self.out_dir = root_dir / "out" / version / "word"
        self.out_docx = self.out_dir / "main.docx"

        self.manifest = Manifest(self.manifest_path)
        self.template_override = template_override
        self.styles_override = styles_override

        self.processor = VariableProcessor(
            placeholder=placeholder,
            figures={fid: entry for fid, entry in self.manifest.figures.items()},
            figures_dir=self.figures_dir,
            target="word",
        )

    # ---- resolution helpers --------------------------------------------

    def _resolve_template(self) -> Path:
        """Pick the .docx template to use."""
        if self.template_override:
            return self.template_override

        # Honor manifest.metadata.word_template (parsed below as .raw['metadata'])
        meta_raw = self.manifest.raw.get("metadata", {}) or {}
        name = meta_raw.get("word_template") or self.manifest.get_template_name()
        candidate = self.templates_dir / f"{name}.docx"
        if candidate.exists():
            return candidate

        # Any single .docx in templates/ is a reasonable default.
        if self.templates_dir.exists():
            docxes = list(self.templates_dir.glob("*.docx"))
            if len(docxes) == 1:
                return docxes[0]

        raise FileNotFoundError(
            f"No .docx template found. Expected {candidate} or a single *.docx "
            f"in {self.templates_dir}. Pass --template <path> to override."
        )

    def _resolve_styles(self, template_path: Path) -> dict[str, Any]:
        # Precedence: explicit --styles override > manifest word_styles >
        # extracted from template > defaults. Manifest word_styles accepts
        # either a bare name (resolved to styles/<name>.yaml then .json)
        # or an explicit path with extension.
        if self.styles_override:
            return load_styles(self.styles_override)

        word_styles = self.manifest.metadata.word_styles
        if word_styles:
            styles_path = self._resolve_styles_path(word_styles)
            if styles_path and styles_path.exists():
                return load_styles(styles_path)
            print(f"  WARNING: word_styles '{word_styles}' not found, falling back to template extraction")

        try:
            return extract_styles(template_path)
        except Exception as e:
            print(f"  WARNING: extracting styles from {template_path} failed: {e}")
            return default_styles()

    def _resolve_styles_path(self, ref: str) -> Optional[Path]:
        """Resolve a manifest styles reference to a concrete file path.
        Bare names look in styles/<name>.{yaml,yml,json}; extensioned
        paths are taken as-is relative to root_dir or as absolute."""
        styles_dir = self.root_dir / "styles"
        p = Path(ref)
        if p.suffix.lower() in (".yaml", ".yml", ".json"):
            return p if p.is_absolute() else (self.root_dir / p)
        for ext in (".yaml", ".yml", ".json"):
            candidate = styles_dir / f"{ref}{ext}"
            if candidate.exists():
                return candidate
        return None

    def _resolve_figure(self, fig_id: str) -> Optional[Path]:
        entry = self.manifest.figures.get(fig_id)
        if not entry:
            return None
        return resolve_figure(entry, "word", self.figures_dir)

    # ---- pipeline steps -------------------------------------------------

    def _add_title_block(self, doc: TemplateDocument) -> None:
        meta = self.manifest.metadata
        if not meta.title:
            return

        c = doc.content
        c.spacer().spacer()
        c.title(meta.title)

        if meta.authors:
            authors_line = "; ".join(
                a.name + (f" ({','.join(str(x) for x in a.affiliations)})" if a.affiliations else "")
                for a in meta.authors
            )
            c.p(authors_line, TextStyle(alignment="center", italic=True))

        if meta.affiliations:
            for num, info in sorted(meta.affiliations.items()):
                if isinstance(info, dict):
                    parts = [info.get("department"), info.get("institution")]
                    line = ", ".join(p for p in parts if p)
                else:
                    line = str(info)
                if line:
                    c.p(
                        f"[{num}] {line}",
                        TextStyle(alignment="center",
                                  size=c.styles["fontSizes"]["small"],
                                  color=c.styles["colors"]["textLight"]),
                    )

        c.spacer()

    def _add_abstract(self, doc: TemplateDocument) -> None:
        abs_text = self.manifest.metadata.abstract
        if not abs_text:
            return
        body = self.processor.replace_variables(
            abs_text.strip(), "manifest.yaml:abstract"
        )
        c = doc.content
        c.label("Abstract")
        # Pre-resolve variables then render as markdown so any formatting
        # (e.g. **bold**) inside the abstract carries over.
        render_markdown(body, c, figures_dir=self.figures_dir)
        if self.manifest.metadata.keywords:
            kw = ", ".join(self.manifest.metadata.keywords)
            c.labeled_para("Keywords: ", kw)
        c.spacer()

    def _render_sections(self, doc: TemplateDocument) -> None:
        pseudo = {"_bibliography", "_toc"}
        bib_placed = False

        for section_ref in self.manifest.sections:
            if section_ref == "_bibliography":
                self._render_bibliography(doc)
                bib_placed = True
                continue
            if section_ref == "_toc":
                # Word tables-of-contents are built by the client (F9 update).
                # Insert a styled heading the user can replace with a live TOC.
                doc.content.h1("Table of Contents")
                doc.content.p("(Insert field: References > Table of Contents)")
                continue

            src_path = self.src_dir / section_ref
            if not src_path.exists():
                print(f"    WARNING: section not found: {section_ref}")
                continue
            if src_path.suffix != ".md":
                if self.verbose:
                    print(f"    SKIP non-markdown section: {section_ref}")
                continue

            if self.verbose:
                print(f"    [md->docx] {section_ref}")
            content = src_path.read_text(encoding="utf-8")
            # Expand {{tab:id}} on the raw markdown so md2docx sees a
            # native pipe table (consistent with the LaTeX/HTML paths).
            from .manifest import expand_table_tokens
            content = expand_table_tokens(content, self.manifest.tables, self.src_dir)
            content = self.processor.replace_variables(content, str(src_path))
            render_markdown(
                content,
                doc.content,
                figure_resolver=self._resolve_figure,
                figures_dir=self.figures_dir,
                section_path=section_ref,
            )

        if not bib_placed:
            self._render_bibliography(doc)

    def _render_bibliography(self, doc: TemplateDocument) -> None:
        cite_keys = doc.content.citation_keys
        if not cite_keys:
            return
        bib = load_bib(self.root_dir, self.version) or {}

        c = doc.content
        c.page_break()
        c.h1("References")

        for idx, key in enumerate(cite_keys, start=1):
            entry = bib.get(key)
            if entry is None:
                c.p(f"[{idx}] {key} — MISSING",
                    TextStyle(color=c.styles["colors"]["error"]))
                continue
            c.p(_render_bib_entry_rich(entry, idx))

    # ---- public entry points -------------------------------------------

    def extract_styles_to(self, dest: Path) -> Path:
        template = self._resolve_template()
        styles = extract_styles(template)
        dest.parent.mkdir(parents=True, exist_ok=True)
        from .docx_styles import save_styles

        save_styles(dest, styles)
        return dest

    def build(self) -> bool:
        print(f"\n{'='*60}")
        print(f"  Building Word: {self.version}")
        print(f"  Source: {self.src_dir}")
        print(f"  Output: {self.out_docx}")
        print(f"{'='*60}")

        if not self.manifest_path.exists():
            print(f"\n  ERROR: manifest not found: {self.manifest_path}")
            return False

        # Clean output dir, recreate
        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # Load template + styles
        template_path = self._resolve_template()
        print(f"\n  Template: {template_path}")
        styles = self._resolve_styles(template_path)

        # Variables
        print("\n  Loading variables...")
        values = self.manifest.get_variable_values()
        self.processor.variables.update(values)
        print(f"    Loaded {len(values)} variables from manifest")

        # Assemble document
        doc = TemplateDocument(TemplateDocumentConfig(
            template_path=template_path,
            styles=styles,
            title=self.manifest.metadata.title,
            author=", ".join(a.name for a in self.manifest.metadata.authors) or None,
        ))
        if self.manifest.metadata.render:
            self._add_title_block(doc)
            self._add_abstract(doc)
        else:
            print("  Skipping title/abstract block (manifest.metadata.render: false)")

        print("\n  Rendering sections...")
        self._render_sections(doc)

        # Save
        doc.save(self.out_docx)

        # Also emit the resolved styles dict alongside as a source of truth
        # the user can copy to styles/<name>.yaml, edit, and feed back via
        # manifest.metadata.word_styles.
        from .docx_styles import save_styles
        styles_yaml = self.out_dir / "styles.yaml"
        save_styles(styles_yaml, styles)
        print(f"  Styles: {styles_yaml}")

        # Report
        self.processor.print_report(verbose=self.verbose)
        if self.processor.has_undefined_variables() and self.strict:
            print("\n  BUILD FAILED: undefined variables (strict mode)")
            return False

        print(f"\n  Build complete!")
        print(f"  Word:   {self.out_docx}")
        return True


# ---- bibliography rendering (RichText) -----------------------------------

def _render_bib_entry_rich(entry: BibEntry, number: int) -> list[RichText]:
    """Return a list of RichText runs for a single bibliography entry.

    Shape: [NUMBER] Authors. Title. Venue Vol(No), pp-pp (Year). DOI/URL
    Authors get bold, venue italic, title plain.
    """
    f = entry.fields
    runs: list[RichText] = [RichText(text=f"[{number}] ")]

    if "author" in f:
        runs.append(RichText(text=_format_authors(f["author"]) + ". ", bold=True))
    if "title" in f:
        runs.append(RichText(text=_clean_tex(f["title"]) + ". "))
    venue = f.get("journal") or f.get("booktitle") or f.get("publisher")
    if venue:
        runs.append(RichText(text=_clean_tex(venue), italic=True))
        trailer_parts: list[str] = []
        if "volume" in f:
            trailer_parts.append(f" {f['volume']}")
        if "number" in f:
            trailer_parts.append(f"({f['number']})")
        if "pages" in f:
            trailer_parts.append(f", {f['pages'].replace('--', '–')}")
        if "year" in f:
            trailer_parts.append(f" ({f['year']})")
        if trailer_parts:
            runs.append(RichText(text="".join(trailer_parts)))
        runs.append(RichText(text=". "))
    elif "year" in f:
        runs.append(RichText(text=f"({f['year']}). "))

    link = None
    if "doi" in f:
        doi = f["doi"]
        link = f"https://doi.org/{doi}" if not doi.startswith("http") else doi
    elif "url" in f:
        link = f["url"]
    if link:
        runs.append(RichText(text=link, color="1155CC"))
    return runs


def find_latest_version(root_dir: Path) -> str:
    """Reuse the same latest-version detection as ManuscriptBuilder."""
    from .build import find_latest_version as _find
    return _find(root_dir)
