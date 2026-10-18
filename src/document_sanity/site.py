"""`document-sanity site`: every document, built and gathered into one folder.

    site/
    ├── index.html            # one card per document: read online · PDF · Word
    ├── manuscript/
    │   ├── index.html        # the interactive HTML viewer (+ figures/)
    │   ├── manuscript.pdf
    │   └── manuscript.docx
    └── proposal/ …

This is what the GitHub Pages workflow (`document-sanity pages init`) runs
and uploads; any static host serves it the same way, since every link is
relative. A document whose manifest sets `metadata.notice` (a CUI banner, a
distribution statement) is refused unless `allow_notice` — publishing is the
moment that notice exists for.
"""

from __future__ import annotations

import html
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import __version__
from .check import BUILD_STEPS, DocResult, build_document
from .manifest import Manifest

MARKER = ".document-sanity-site"


class SiteError(Exception):
    """The site can't be built as asked; nothing was published."""


@dataclass
class DocInfo:
    doc: str
    title: str
    authors: list[str]
    notice: str | None


@dataclass
class SiteReport:
    out: Path
    results: list[DocResult] = field(default_factory=list)
    published: list[str] = field(default_factory=list)

    @property
    def failed(self) -> list[DocResult]:
        return [r for r in self.results if any(s.name in BUILD_STEPS for s in r.errors)]


def doc_info(root: Path, doc: str) -> DocInfo:
    meta = Manifest(root / "src" / doc / "manifest.yaml").metadata
    notice = (meta.notice or "").strip() or None
    return DocInfo(doc, meta.title or doc, [a.name for a in meta.authors if a.name], notice)


def with_notice(root: Path, docs: list[str]) -> list[DocInfo]:
    """The documents whose manifest sets `metadata.notice`."""
    return [info for info in (doc_info(root, d) for d in docs) if info.notice]


def notice_error(flagged: list[DocInfo], flag: str = "--allow-notice") -> SiteError:
    lines = "\n".join(
        f"    src/{i.doc}/manifest.yaml: {' '.join(i.notice.split())[:120]}" for i in flagged
    )
    return SiteError(
        "these documents carry a metadata.notice (a restriction or distribution "
        f"statement), so they don't go on a public site:\n{lines}\n"
        "  Leave them out (name the documents to publish), or — only with the "
        f"owner's explicit OK — pass {flag}."
    )


def project_meta(root: Path) -> tuple[str, str]:
    """(name, description) from pyproject.toml, falling back to the folder name."""
    path = root / "pyproject.toml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    project = text.split("[project]", 1)[1] if "[project]" in text else ""
    project = re.split(r"^\[", project, maxsplit=1, flags=re.M)[0]
    name = re.search(r'^name\s*=\s*"([^"]*)"', project, re.M)
    desc = re.search(r'^description\s*=\s*"([^"]*)"', project, re.M)
    return (name.group(1) if name else root.resolve().name), (desc.group(1) if desc else "")


def _prepare(out: Path, root: Path) -> None:
    """Empty `out` for a fresh site — only if it is one we built before (or empty)."""
    if out.resolve() in (root.resolve(), *root.resolve().parents):
        raise SiteError(f"--out {out} would replace the project itself")
    if out.exists():
        if not out.is_dir():
            raise SiteError(f"{out} exists and is not a folder")
        if any(out.iterdir()) and not (out / MARKER).is_file():
            raise SiteError(
                f"{out} already has files that `site` didn't put there; "
                "choose another --out or empty it first"
            )
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_text("Built by `document-sanity site`; rebuilt from scratch each run.\n")
    (out / ".nojekyll").write_text("")


def build_site(
    root: Path,
    docs: list[str],
    out: Path,
    *,
    pdf: bool = True,
    allow_notice: bool = False,
    compiler: str = "pdflatex",
    verbose: bool = False,
) -> SiteReport:
    """Build `docs` (every target) and gather them, with an index, into `out`."""
    if not docs:
        raise SiteError("no documents to publish (no src/<doc>/manifest.yaml)")
    flagged = with_notice(root, docs)
    if flagged and not allow_notice:
        raise notice_error(flagged)

    report = SiteReport(out)
    for doc in docs:
        report.results.append(build_document(
            root, doc, pdf=pdf, require_tex=pdf, compiler=compiler, verbose=verbose,
        ))
    if report.failed:
        return report

    _prepare(out, root)
    infos = []
    for result in report.results:
        doc = result.doc
        target = out / doc
        html_dir = root / "out" / doc / "html"
        shutil.copytree(html_dir, target)
        downloads = {}
        for step, ext in (("pdf", "pdf"), ("word", "docx")):
            s = result.step(step)
            if s is not None and s.status == "ok" and s.output and s.output.is_file():
                shutil.copy2(s.output, target / f"{doc}.{ext}")
                downloads[ext] = f"{doc}/{doc}.{ext}"
        _add_site_nav(target / "index.html", doc, downloads)
        infos.append((doc_info(root, doc), downloads))
        report.published.append(doc)
    (out / "index.html").write_text(render_index(root, infos), encoding="utf-8")
    return report


SITE_NAV = """<nav class="ds-site-nav" aria-label="Site">{links}</nav>
<style>
.ds-site-nav {{ position: fixed; left: 12px; bottom: 12px; z-index: 40; display: flex; gap: 2px;
  padding: 3px; border-radius: 999px; background: rgba(127,127,127,.16);
  backdrop-filter: blur(6px); font: 13px/1.2 system-ui, -apple-system, sans-serif; }}
.ds-site-nav a {{ padding: 5px 11px; border-radius: 999px; color: inherit; text-decoration: none; }}
.ds-site-nav a:hover {{ background: rgba(127,127,127,.24); }}
@media print {{ .ds-site-nav {{ display: none; }} }}
</style>
"""


def _add_site_nav(index: Path, doc: str, downloads: dict[str, str]) -> None:
    """A small pill on the copied viewer: back to the index, and the downloads."""
    links = ['<a href="../">All documents</a>']
    if "pdf" in downloads:
        links.append(f'<a href="{html.escape(doc)}.pdf">PDF</a>')
    if "docx" in downloads:
        links.append(f'<a href="{html.escape(doc)}.docx">Word</a>')
    text = index.read_text(encoding="utf-8")
    nav = SITE_NAV.format(links="".join(links))
    head, sep, tail = text.rpartition("</body>")
    text = head + nav + sep + tail if sep else text + nav
    index.write_text(text, encoding="utf-8")


# ── the index page ───────────────────────────────────────────────────────────

INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="document-sanity {version}">
<title>{title}</title>
<style>
:root {{
  --bg: #fbfaf7; --surface: #ffffff; --text: #1d1d1b; --muted: #66645e;
  --line: #e4e1d8; --accent: #2f5d8a; --accent-text: #ffffff; --notice: #8a5a00;
  --notice-bg: #fff6df;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #151514; --surface: #1f1f1d; --text: #ecebe6; --muted: #a3a097;
    --line: #34332f; --accent: #8db8e6; --accent-text: #10202f; --notice: #f2c46d;
    --notice-bg: #2c2414;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}}
main {{ max-width: 56rem; margin: 0 auto; padding: 3rem 1rem 4rem; }}
header h1 {{ font-size: 1.9rem; line-height: 1.2; margin: 0 0 .4rem; }}
header p {{ color: var(--muted); margin: 0 0 2rem; }}
.docs {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr)); }}
.doc {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 1.1rem 1.2rem; display: flex; flex-direction: column; gap: .5rem;
}}
.doc h2 {{ font-size: 1.12rem; line-height: 1.3; margin: 0; }}
.doc h2 a {{ color: inherit; text-decoration: none; }}
.doc h2 a:hover {{ text-decoration: underline; }}
.authors {{ color: var(--muted); font-size: .92rem; margin: 0; }}
.folder {{ color: var(--muted); font: .8rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; margin: 0; }}
.notice {{
  background: var(--notice-bg); color: var(--notice); border-radius: 6px;
  padding: .45rem .6rem; font-size: .85rem; margin: 0;
}}
.links {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-top: auto; padding-top: .4rem; }}
.links a {{
  border: 1px solid var(--line); border-radius: 999px; padding: .25rem .8rem;
  color: var(--text); text-decoration: none; font-size: .9rem;
}}
.links a.primary {{ background: var(--accent); border-color: var(--accent); color: var(--accent-text); }}
.links a:hover {{ border-color: var(--accent); }}
footer {{ color: var(--muted); font-size: .85rem; margin-top: 3rem; border-top: 1px solid var(--line); padding-top: 1rem; }}
footer a {{ color: inherit; }}
</style>
</head>
<body>
<main>
<header>
<h1>{title}</h1>
{description}
</header>
<section class="docs">
{cards}
</section>
<footer>
Built {built} with <a href="https://github.com/yakaboskic/document-sanity">document-sanity</a>
v{version}, part of <a href="https://sanitism.dev">Sanitism</a>: one markdown source,
three printouts (HTML, PDF, Word), every number with its provenance.
</footer>
</main>
</body>
</html>
"""


def render_index(root: Path, infos: list[tuple[DocInfo, dict[str, str]]]) -> str:
    name, description = project_meta(root)
    cards = []
    for info, downloads in infos:
        e = html.escape
        links = [f'<a class="primary" href="{e(info.doc)}/">Read online</a>']
        if "pdf" in downloads:
            links.append(f'<a href="{e(downloads["pdf"])}">PDF</a>')
        if "docx" in downloads:
            links.append(f'<a href="{e(downloads["docx"])}">Word</a>')
        parts = [f'<h2><a href="{e(info.doc)}/">{e(info.title)}</a></h2>']
        if info.authors:
            parts.append(f'<p class="authors">{e(", ".join(info.authors))}</p>')
        if info.notice:
            parts.append(f'<p class="notice">{e(" ".join(info.notice.split()))}</p>')
        parts.append(f'<p class="folder">src/{e(info.doc)}/</p>')
        parts.append(f'<nav class="links">{" ".join(links)}</nav>')
        cards.append('<article class="doc">\n' + "\n".join(parts) + "\n</article>")
    return INDEX.format(
        title=html.escape(name),
        description=f"<p>{html.escape(description)}</p>" if description else "",
        cards="\n".join(cards),
        built=date.today().isoformat(),
        version=__version__,
    )
