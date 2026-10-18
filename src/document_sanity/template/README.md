# Template Repo for a Document Sanity Project

A ready-to-clone GitHub template for documents built with
[document-sanity](https://github.com/yakaboskic/document-sanity), part of
[Sanitism](https://sanitism.dev): built for autists to communicate their
work, sanely. Markdown is the source of truth; one build pipeline produces a
compilable LaTeX tree, a PDF, an interactive HTML viewer, and a Word
(`.docx`) document — all from the same files. Variables with
provenance, figures, and tables (markdown / CSV / TSV) all flow
through every output target identically.

**Live demo:** <https://yakaboskic.github.io/document-sanity-template/>,
both starters as HTML viewer, PDF and Word, built by this repo's own
[Pages workflow](.github/workflows/pages.yml).

The template ships with two **starter versions** so the structure
covers both common shapes of long-form writing:

- **`src/manuscript/`** — a research paper with title block, authors,
  abstract, keywords, and `Introduction / Methods / Results /
  Discussion` sections. Auto-renders the front matter.
- **`src/proposal/`** — a SBIR/STTR-style proposal where the prose
  hand-numbers sections (`1.0 Introduction`, `2.1 Aim 1`, etc.) and
  there is no auto-rendered title block. Demonstrates `metadata.render:
  false` and a separate `templates/proposal.tex`.

Both versions share the same `templates/article.docx`,
`styles/article.yaml`, and `styles/article.css`, so they look like one
coherent design system. Switch which version is active by passing
`VERSION=manuscript` or `VERSION=proposal` to any `make` target.

## Start a project

**No GitHub needed.** One command makes a named copy of this template in a
plain folder (no clone, no `.git` unless you add `--git`):

```bash
uvx --from "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.0" \
  document-sanity init my-paper --title "My paper" --starter manuscript
cd my-paper && uv sync
```

**On GitHub**, click **Use this template** → **Create a new repository**,
clone it, and name it:

```bash
git clone https://github.com/<you>/<your-repo> my-paper
cd my-paper
python init.py          # asks for the name, title, author, which starters to keep
```

Both run the same `document-sanity init`: the project's name goes into
`pyproject.toml` and the README, the title and author into each kept
starter's `manifest.yaml` (the lines marked `TEMPLATE:`), the starters you
don't keep (`--starter manuscript`, `proposal`, or `both`) are dropped, and
the [agent skill](#agent-skill) is installed. `init.py` removes itself, and
this repo's Pages workflow, when it's done. Then edit the affiliations,
abstract and keywords by hand.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (`brew install uv` or `pipx install uv`)
- A TeX distribution (MacTeX / TeX Live) with `pdflatex` and `bibtex`
  for PDF builds. Not required for HTML or Word.
- Optional: [pandoc](https://pandoc.org/) for onboarding Word
  documents into a new version (the [agent skill](#agent-skill)'s `onboard` mode).

## Quickstart

```bash
make install                          # install the pinned document-sanity (uv sync)
make latex                            # LaTeX tree only (no PDF compile)
make pdf                              # build + compile out/<ver>/pdf/main.pdf
make html                             # interactive HTML viewer at out/<ver>/html/index.html
make word                             # Word document at out/<ver>/word/main.docx
make serve                            # also runs `make html`, opens http://localhost:8000
make check                            # every target of every document, before you share

# Pass VERSION=<name> to target a specific version (default: latest auto-detected):
make pdf VERSION=manuscript
make word VERSION=proposal
```

`document-sanity` is pinned to a release tag in `pyproject.toml`, so
every clone builds with the same tool. To upgrade, change the tag to a
newer [release](https://github.com/yakaboskic/document-sanity/releases)
and run `make update` (or `uv lock && uv sync`). `make install-pinned`
installs strictly from `uv.lock` and fails if it's stale (CI).

## Layout

```
.
├── pyproject.toml               # pins document-sanity (a release tag) as the only runtime dep
├── Makefile                     # install / latex / pdf / preview / html / word / check / site / …
├── README.md                    # you are here
├── AGENTS.md                    # points agents at the document-sanity skill + project notes
├── init.py                      # names a "Use this template" copy, then removes itself
├── .github/workflows/pages.yml  # deploys this template's demo (removed by init.py)
├── .gitignore                   # ignores out/, site/ and build intermediates
│
├── scripts/
│   └── finalize_word_layout.py  # post-`make word` pass: table/figure/heading pagination, math size
│
├── templates/
│   ├── article.tex              # LaTeX template — used by manuscript by default
│   ├── proposal.tex             # LaTeX template — same packages, sets secnumdepth=-1,
│   │                            # floats held inside their section (placeins)
│   ├── article.docx             # Word template: header logo, page-of-N, watermark, named styles
│   ├── logo.png                 # logo embedded in the docx header
│   └── watermark.png            # diagonal "DRAFT" watermark, baked into image (not VML)
│
├── styles/
│   ├── article.yaml             # source-of-truth Word styles (auto-emitted by `make word`,
│   │                            # reused via manifest.metadata.word_styles)
│   └── article.css              # HTML override styles, loaded after the inline <style>
│
└── src/
    ├── manuscript/              # paper-style starter (title block + abstract + numbered sections)
    │   ├── manifest.yaml        # metadata, sections, variables, figures, tables — one-stop config
    │   ├── docs/                # markdown sections in manifest.sections order
    │   │   ├── introduction.md
    │   │   ├── methods.md
    │   │   ├── results.md
    │   │   └── discussion.md
    │   ├── figures/             # <id>/<id>.{pdf,png,svg,html} subdirectory layout
    │   │   └── example/
    │   │       ├── example.png
    │   │       └── example.svg
    │   ├── tables/              # CSV/TSV/markdown/latex tables referenced via {{tab:<id>}}
    │   │   └── subgroup_summary.csv
    │   └── references.bib
    │
    └── proposal/                # proposal-style starter (no title block, hand-numbered sections)
        ├── manifest.yaml        # metadata.render: false; template: proposal
        ├── docs/                # 0_cover, 1_introduction, 2_aims, 3_approach, 4_plan, 5_impact
        ├── figures/architecture/architecture.png
        ├── tables/
        │   ├── milestones.csv
        │   └── risk_register.tsv
        └── references.bib
```

## Make targets

| target           | what it does                                                                  |
|------------------|-------------------------------------------------------------------------------|
| `make install`   | Install the `document-sanity` release pinned in `pyproject.toml` (`uv sync`). |
| `make install-pinned` | Install strictly from `uv.lock`; fail if it's stale. Reproducible / CI.  |
| `make update`    | Re-resolve `document-sanity` after moving its tag in `pyproject.toml`.        |
| `make latex`     | Generate LaTeX artifacts in `out/<ver>/latex/` (no PDF compile).              |
| `make pdf`       | Build + compile to `out/<ver>/pdf/main.pdf`.                                  |
| `make preview`   | Insert / refresh markdown-preview blocks next to ```latex fences in `docs/`.  |
| `make preview-check` | Fail if any preview block is missing or stale (CI).                       |
| `make html`      | Emit interactive HTML viewer at `out/<ver>/html/index.html`. Auto-runs preview. |
| `make word`      | Build a Word doc at `out/<ver>/word/main.docx`, then apply table and figure pagination rules. Auto-runs preview. |
| `make serve`     | Build HTML and serve it on `http://localhost:8000`.                           |
| `make check`     | `document-sanity check`: preview check, PDF, references, HTML, Word for every document (or `VERSION`). Exits non-zero on anything to fix. |
| `make site`      | `document-sanity site`: every document's HTML viewer, PDF and Word in `site/` with an index page. |
| `make clean`     | Remove `out/` and `site/`.                                                    |

Pass `VERSION=<name>` to any target for a specific version. The
default is the latest auto-detected `src/<ver>/` directory.

## The manifest

`manifest.yaml` is the single source of configuration per version.
Every option lives here so version-to-version overrides are a copy-edit:

```yaml
metadata:
  title: "My Paper"
  authors:
    - name: "First Author"
      email: "first@example.org"
      affiliations: [1]
  affiliations:
    1: { department: "Dept", institution: "Uni" }
  abstract: |
    A short abstract with {{NUM_SAMPLES:,}} samples and
    R<sup>2</sup> = {{R2:.2f}}.
  keywords: [example, demo]
  template: article            # → templates/article.tex   (LaTeX/PDF target)
  word_template: article       # → templates/article.docx  (Word target)
  word_styles: article         # → styles/article.yaml     (overrides extracted styles)
  html_styles: article         # → styles/article.css      (loaded after the inline <style>)
  render: true                 # auto-render title/authors/abstract block (default true)

sections:
  - docs/introduction.md
  - docs/methods.md
  - _bibliography             # pseudo-section: inserts \bibliography{} here

variables:
  NUM_SAMPLES: 1247           # simple form
  PVAL:                       # full form with provenance — clickable in the HTML viewer
    value: 0.0087
    provenance:
      description: P-value from the primary regression.
      source: data/results.csv
      command: python scripts/fit.py
      updated: "2026-04-21"

figures:
  example:
    width: "\\textwidth"
    # source: figures/example/example.png    # optional explicit fallback
    # The builder auto-scans figures/example/ and picks the best-fit per
    # target: pdf prefers png, html prefers html/svg, word prefers raster.

tables:
  subgroup_summary:
    source: tables/subgroup_summary.csv
    format: csv               # csv | tsv | markdown | latex
```

### `metadata.render`

Default `true`. When `false` the auto-rendered title / authors /
affiliations / abstract / keywords block is suppressed in every output
format — useful for proposals or document types that own their own
front matter (the proposal starter sets `render: false` and puts a
metadata block in `docs/0_cover.md`).

### `metadata.word_styles` / `metadata.html_styles`

Bare names resolve to `styles/<name>.{yaml,yml,json,css}`; explicit
paths (with extension) are taken as-is. `make word` also emits
`out/<ver>/word/styles.yaml` as a source of truth — copy that to
`styles/<name>.yaml`, edit, and feed it back via `word_styles:` to
keep the round trip stable.

### Tables: four formats

| `format`   | Behavior                                                                        |
|------------|---------------------------------------------------------------------------------|
| `csv`      | Comma-separated; expanded to a markdown pipe table on load                      |
| `tsv`      | Tab-separated; expanded to a markdown pipe table on load                        |
| `markdown` | Source file is already a pipe table; inlined verbatim                           |
| `latex`    | Raw `.tex` tabular fragment; reference via `\input{tables/foo.tex}` in a ```latex block (no token expansion) |

For the first three formats, reference the table from markdown with
`{{tab:<id>}}`. The token expands to a markdown pipe table at build
time so PDF, HTML, and Word all render identically.

For inline tables that don't need a separate data source, just write
a markdown pipe table directly. The starter shows both side by side
in `src/manuscript/docs/results.md`.

## Word output

The starter ships `templates/article.docx` with:

- A logo in the header (`templates/logo.png`)
- Page-of-N field on the right with a brand-color bottom rule
- Centered "Built with document-sanity" footer
- A diagonal "DRAFT" watermark anchored to page center, behind text
- Six named styles: Title / Heading 1–3 / Caption / Code

Headers, footers, theme, fonts, and page layout are preserved from
the template; only the body is replaced with generated content. Per-
character formatting (`<sup>`, `<sub>`, `**bold**`, *italic*, inline
`code`) survives table cell boundaries.

The Word target also runs `scripts/finalize_word_layout.py`. It keeps
table rows together, repeats the first row as a header on later pages,
and keeps that header with the first data row. Headings stay with the
following paragraph. Figure images stay with
their captions, and captions stay on one page when they fit. Native
equations use the surrounding paragraph's explicit font size, falling
back to `fontSizes.body` in the exported `styles.yaml`. This prevents
equations from inheriting a different size from the template. The step
changes only body pagination and math formatting, preserving template
defaults, headers and footers. It uses the same explicit or auto-detected
version as the exporter. Edit this build step rather than manually
changing files in `out/`.

- **Swap the logo**: replace `templates/logo.png`. The docx
  references it by relationship, so editing the PNG in place picks up
  on the next build.
- **Swap the watermark**: replace `templates/watermark.png`. Color and
  transparency must be **baked into the image** — the docx anchors it
  as a normal floating picture (`wp:anchor` with `behindDoc="1"`,
  centered on the page). Don't try to use a VML text-watermark; a
  hand-rolled VML watermark hangs Word's *Edit Watermark* dialog for
  ~30s on macOS Word.
- **Word styles**: `make word` emits `out/<ver>/word/styles.yaml` —
  copy to `styles/<name>.yaml`, edit colors / fonts / sizes / spacing,
  then point `manifest.metadata.word_styles: <name>` at it.

## Cross-format authoring tips

Same markdown source feeds LaTeX, HTML, and Word — a few conventions
keep all three happy:

- **Superscript / subscript**: write `R<sup>2</sup>` / `H<sub>2</sub>O`,
  not `R\textsuperscript{2}`. The `<sup>`/`<sub>` form lowers
  correctly to `\textsuperscript{}` for LaTeX, native `<sup>` for
  HTML, and a real `vertAlign=superscript` run for Word.
  `\textsuperscript{}` from LaTeX-native source documents is also
  recognized and lowered the same way.
- **Dollar signs in prose**: use `\$250` for a literal dollar. Bare
  `$` opens LaTeX math mode and eats the rest of the paragraph. HTML
  and Word render `\$` as a literal `$`.
- **Math**: paired `$...$` and `$$...$$` work everywhere. Variable
  tokens inside math (`$p = {{PVAL:.2e}}$`) substitute correctly.
- **Inline code**: backticks emit `\texttt{}` in LaTeX (with full
  escape, so `` `\cite{key}` `` shows literally) and a `Code`-styled
  run in Word (mono via the template's Code character style).
- **Greek / math operators in prose**: `≥`, `≤`, `≠`, `→`, `←`, `×`,
  `µ`, `°` all work. The templates declare the few that pdflatex
  doesn't auto-map; if your prose grows new ones, add them to the
  `\DeclareUnicodeCharacter` block in `templates/article.tex` /
  `templates/proposal.tex`, or compile with LuaLaTeX/XeLaTeX (which
  handle Unicode natively).
- **Tables that overflow in the PDF**: the LaTeX path uses `tabularx`
  with `X` columns by default, so wide tables auto-fit `\textwidth`
  and long cells wrap. No action needed.

## Cutting a new version

```bash
# Snapshot src/manuscript/ into src/MMDDYYYY/ (today's date)
uv run document-sanity new-version --source manuscript --strategy date
# or name it for what it is
uv run document-sanity new-version --source proposal --name nih-resubmission
```

Versions are directories under `src/`. The starter ships
`src/manuscript/` and `src/proposal/`; `new-version` copies one into a
new folder, leaving the original as the archived snapshot. Pass
`--source` (and `VERSION=<name>` to the make targets): without it,
commands auto-detect the "latest" folder, which is the newest dated one,
or else the last alphabetically (`proposal` before `manuscript`).

## Agent skill

`python init.py` and `document-sanity init` install the document-sanity
agent skill into `.claude/skills/document-sanity/` (Claude Code:
`/document-sanity [mode]`) and `.agents/skills/document-sanity/` (other
agents). Its modes cover onboarding a stack of Word / Markdown / PDF / CSV /
figure files into a new document (pandoc for docx→md, figure extraction
and renaming, CSV-into-tables placement, manifest construction), the
edit / preview / build loop, figures and draw.io, variables, citations, Word
styles, versions, LaTeX import, `check`, and publishing.
`uv run document-sanity skills --force` refreshes it after an upgrade.
[AGENTS.md](./AGENTS.md) points other agents at it and holds this
project's own notes.

## Publish on GitHub Pages

> A GitHub Pages site is **public**, even when the repository is private.

```bash
uv run document-sanity pages init       # asks first; → .github/workflows/pages.yml
uv run document-sanity site             # try locally what the workflow publishes
```

On every push to `main` the workflow installs the pinned document-sanity,
runs `document-sanity site` (each document's HTML viewer, PDF and Word,
plus an index page) and deploys `site/`. PDFs need TeX on the runner: the
workflow installs a TeX Live subset from Ubuntu's packages (a minute or
two per run); `pages init --no-pdf` skips it and publishes HTML and Word
only. A document whose manifest sets `metadata.notice` (CUI, distribution
statements) is refused unless you pass `--allow-notice`, and stays refused
on every later build. Name documents to publish only those
(`pages init manuscript`). Then turn Pages on (Settings → Pages → Source:
**GitHub Actions**) and push. See the [document-sanity
README](https://github.com/yakaboskic/document-sanity#publish-on-github-pages)
for the details.

This repo's own workflow is generated with `--only-repo
yakaboskic/document-sanity-template`, so copies made with "Use this
template" don't deploy it (and `init.py` removes it).

## References

- **document-sanity repo**: https://github.com/yakaboskic/document-sanity
- **Opinionated docs**: https://github.com/yakaboskic/document-sanity/tree/main/docs
- **Example paper project**: https://github.com/yakaboskic/pigean-indirect-support
