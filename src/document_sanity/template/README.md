<a href="https://document.sanitism.dev/manuscript/"><img src="https://sanitism.dev/shots/doc-viewer.jpg" alt="The starter manuscript in document-sanity's interactive HTML viewer: a contents sidebar, the title and authors, and an abstract whose numbers 1,247 and 0.87 are marked as clickable." width="100%"></a>

# document-sanity-template

**A starter project for papers, proposals and reports: Markdown in, LaTeX, PDF, Word and interactive HTML out, every number traced to its source.**

Built with [document-sanity](https://github.com/yakaboskic/document-sanity), part of [Sanitism](https://sanitism.dev): built for autists to communicate their work, sanely.

**Live:** this repo builds and publishes itself at [document.sanitism.dev](https://document.sanitism.dev/): [the manuscript](https://document.sanitism.dev/manuscript/) and [the proposal](https://document.sanitism.dev/proposal/), each as HTML, PDF and Word.

## Start a project

**Keep it in git.** Click **Use this template** → **Create a new repository**, then:

```bash
git clone https://github.com/<you>/<your-repo> my-paper
cd my-paper
python init.py          # asks for the name, title, author, and which starters to keep
```

**Just give me a folder.** No GitHub needed; it needs [uv](https://docs.astral.sh/uv/):

```bash
uvx document-sanity init my-paper --title "My paper"
```

Both run the same `document-sanity init`. The project's name goes into `pyproject.toml`, this README is replaced by a short one for your project, the title and author into each kept starter's `manifest.yaml` (the lines marked `TEMPLATE:`), the starters you don't keep (`--starter manuscript`, `proposal`, or `both`) are dropped, and the [agent skill](#agent-skill) is installed. `init.py` then removes itself and this repo's demo workflow. Edit the affiliations, abstract and keywords by hand.

Then, in the project:

```bash
make install            # the pinned document-sanity (uv sync); commit the uv.lock it writes
make html VERSION=manuscript
make check              # every target of every document, before you share
```

You need Python 3.10+ and [uv](https://docs.astral.sh/uv/). PDFs need a TeX distribution with `pdflatex` and `bibtex` (MacTeX or TeX Live); HTML and Word don't. [pandoc](https://pandoc.org/) is optional, for onboarding Word documents.

## Two starters

| | `src/manuscript/` | `src/proposal/` |
|---|---|---|
| **Shape** | A research paper: title block, authors, abstract, keywords, IMRaD sections | An SBIR/STTR-style proposal: a cover page and hand-numbered sections (`1.0 Introduction`, `2.1 Aim 1`) |
| **Front matter** | Rendered automatically from `metadata` | Its own, in `docs/0_cover.md` (`metadata.render: false`) |
| **LaTeX template** | `templates/article.tex` | `templates/proposal.tex` (same packages, unnumbered sections, floats kept in their section) |
| **Shows off** | variables with provenance, a figure, a CSV table, citations, math | CSV and TSV tables, a figure, the cover pattern |

Both share `templates/article.docx`, `styles/article.yaml` and `styles/article.css`, so they look like one design system. Pick one with `VERSION=manuscript` or `VERSION=proposal` on any `make` target.

## What's inside

```
.
├── pyproject.toml               # pins document-sanity to a release tag
├── Makefile                     # install, latex, pdf, preview, html, word, check, site, …
├── AGENTS.md                    # points coding agents at the skill, plus this project's notes
├── init.py                      # names a "Use this template" copy, then removes itself
├── .github/workflows/pages.yml  # publishes this template's demo (removed by init.py)
│
├── templates/
│   ├── article.tex              # the manuscript's LaTeX template
│   ├── proposal.tex             # the proposal's
│   ├── article.docx             # Word template: header logo, page-of-N, watermark, named styles
│   ├── logo.png                 # the logo in the docx header
│   └── watermark.png            # the diagonal "DRAFT" watermark, baked into the image
│
├── styles/
│   ├── article.yaml             # Word styles, round-tripped through `make word`
│   └── article.css              # HTML styles, loaded after the viewer's own
│
└── src/
    ├── manuscript/
    │   ├── manifest.yaml        # metadata, sections, variables, figures, tables
    │   ├── docs/                # introduction, methods, results, discussion
    │   ├── figures/example/     # one folder per figure: example.png, example.svg
    │   ├── tables/subgroup_summary.csv
    │   └── references.bib
    └── proposal/
        ├── manifest.yaml        # metadata.render: false; template: proposal
        ├── docs/                # 0_cover, 1_introduction, 2_aims, 3_approach, 4_plan, 5_impact
        ├── figures/architecture/architecture.png
        ├── tables/              # milestones.csv, risk_register.tsv
        └── references.bib
```

## Build it

| Target | What it does |
|---|---|
| `make install` | Install the `document-sanity` release pinned in `pyproject.toml` (`uv sync`). |
| `make install-pinned` | Install strictly from `uv.lock`; fail if it's stale. For CI. |
| `make update` | Re-resolve `document-sanity` after moving its tag in `pyproject.toml`. |
| `make latex` | The LaTeX tree in `out/<doc>/latex/`, without compiling. |
| `make pdf` | Build and compile `out/<doc>/pdf/main.pdf`. |
| `make preview` | Insert or refresh the preview blocks next to ```` ```latex ```` fences in `docs/`. |
| `make preview-check` | Fail if a preview block is missing or stale. For CI. |
| `make html` | The interactive viewer at `out/<doc>/html/index.html`. Runs `preview` first. |
| `make word` | The Word file at `out/<doc>/word/main.docx`, laid out (pagination, equation sizes). Runs `preview` first. |
| `make serve` | Build the HTML and serve it on `http://localhost:8000`. |
| `make check` | `document-sanity check`: previews, PDF, references, HTML and Word for every document (or `VERSION`). Exits non-zero on anything to fix. |
| `make site` | `document-sanity site`: every document's HTML, PDF and Word in `site/`, with an index page. |
| `make clean` | Remove `out/` and `site/`. |

`VERSION=<name>` picks a document; without it, the latest folder under `src/` is used.

## The manifest

One `manifest.yaml` per document holds everything, so a new version is a copy and an edit:

```yaml
metadata:
  title: "My Paper"
  authors:
    - { name: "First Author", email: "first@example.org", affiliations: [1] }
  affiliations:
    1: { department: "Dept", institution: "Uni" }
  abstract: |
    A short abstract with {{NUM_SAMPLES:,}} samples and R<sup>2</sup> = {{R2:.2f}}.
  keywords: [example, demo]
  template: article            # templates/article.tex   (LaTeX, PDF)
  word_template: article       # templates/article.docx  (Word)
  word_styles: article         # styles/article.yaml     (overrides the extracted styles)
  html_styles: article         # styles/article.css      (loaded after the viewer's own)
  render: true                 # the auto-rendered title block (false for the proposal)

sections:
  - docs/introduction.md
  - docs/methods.md
  - _bibliography              # the reference list goes here

variables:
  NUM_SAMPLES: 1247            # the simple form
  PVAL:                        # the full form: clickable in the HTML viewer
    value: 0.0087
    provenance:
      description: P-value from the primary regression.
      source: data/results.csv
      command: python scripts/fit.py
      updated: "2026-04-21"

figures:
  example:
    width: "\\textwidth"       # figures/example/ is scanned; each target picks its best format

tables:
  subgroup_summary:
    source: tables/subgroup_summary.csv
    format: csv                # csv | tsv | markdown | latex
```

- **`metadata.render: false`** suppresses the auto-rendered title, authors, affiliations, abstract and keywords in every output, for documents that own their front matter.
- **`word_styles` / `html_styles`** take a bare name (`styles/<name>.{yaml,json,css}`) or a path. `make word` also writes `out/<doc>/word/styles.yaml`: copy it to `styles/<name>.yaml`, edit, and point `word_styles` at it to keep the round trip stable.
- **Tables** in `csv`, `tsv` or `markdown` format are referenced from Markdown with `{{tab:<id>}}` and render identically in PDF, HTML and Word. A `latex` table is a raw tabular fragment, used with `\input{}` in a ```` ```latex ```` block. Plain pipe tables work inline too; `src/manuscript/docs/results.md` shows both.

## Word output

`templates/article.docx` carries a header logo (`templates/logo.png`), a page-of-N field with a brand-color rule, a "Built with document-sanity" footer, a diagonal "DRAFT" watermark behind the text, and six named styles (Title, Heading 1–3, Caption, Code).

The template's headers, footers, theme, fonts and page layout are kept; only the body is generated. `document-sanity word` then lays the file out: table rows stay together and header rows repeat, headings keep with the next paragraph, figures keep with their captions, and equations take the paragraph's font size.

- **Swap the logo:** replace `templates/logo.png`. The docx references it, so the next build picks it up.
- **Swap the watermark:** replace `templates/watermark.png`, with the color and transparency baked into the image. It is anchored as a floating picture behind the text; a hand-made VML watermark hangs Word's *Edit Watermark* dialog, so avoid one.
- **Change the styles:** copy `out/<doc>/word/styles.yaml` to `styles/<name>.yaml`, edit colors, fonts, sizes and spacing, and set `metadata.word_styles: <name>`.

## Writing for every output at once

The same Markdown feeds LaTeX, HTML and Word. A few conventions keep all three happy:

- **Superscripts and subscripts:** write `R<sup>2</sup>` and `H<sub>2</sub>O`, not `\textsuperscript{2}`. They become `\textsuperscript{}` in LaTeX, `<sup>` in HTML and a real superscript run in Word.
- **Dollar signs:** `\$250` is a literal dollar. A bare `$` opens math mode and swallows the paragraph.
- **Math:** `$...$` and `$$...$$` work everywhere, with variables inside (`$p = {{PVAL:.2e}}$`).
- **Symbols in prose:** `≥ ≤ ≠ → ← × µ °` all work. The templates declare the few pdflatex doesn't map; add new ones to the `\DeclareUnicodeCharacter` block in `templates/*.tex`, or compile with LuaLaTeX or XeLaTeX.
- **Wide tables** use `tabularx` in the PDF, so they fit `\textwidth` and long cells wrap.

## Versions are folders

```bash
uv run document-sanity new-version --source manuscript --strategy date   # → src/MMDDYYYY/
uv run document-sanity new-version --source proposal --name resubmission # → src/resubmission/
```

`new-version` copies a document into a new folder and leaves the original as the archived snapshot. Pass `--source` (and `VERSION=<name>` to `make`): without it, commands use the latest folder, the newest dated one or else the last alphabetically.

## Agent skill

`init` installs the document-sanity skill into `.claude/skills/document-sanity/` (Claude Code: `/document-sanity [mode]`) and `.agents/skills/document-sanity/` (other agents). Its modes cover turning a pile of Word, Markdown, PDF, CSV and figure files into a new document, the edit → preview → build loop, figures and draw.io, variables, citations, Word styles, versions, LaTeX import, `check`, and publishing. `uv run document-sanity skills --force` refreshes it after an upgrade. [AGENTS.md](./AGENTS.md) points other agents at it and holds this project's own notes.

## Publish on GitHub Pages

> [!WARNING]
> A GitHub Pages site is **public**, even when the repository is private.

```bash
uv run document-sanity pages init       # asks first; writes .github/workflows/pages.yml
uv run document-sanity site             # try locally what the workflow publishes
```

On every push to `main` the workflow installs the pinned document-sanity, runs `document-sanity site` and deploys `site/`. PDFs need TeX on the runner, so the workflow installs a TeX Live subset (a minute or two per run); `pages init --no-pdf` skips it. A document whose manifest sets `metadata.notice` (CUI, distribution statements) is refused unless you pass `--allow-notice`, and stays refused on every later build. Name documents to publish only those (`pages init manuscript`). Then turn Pages on (Settings → Pages → Source: **GitHub Actions**) and push. The [document-sanity README](https://github.com/yakaboskic/document-sanity#publish-on-github-pages) has the details.

This repo's own workflow is generated with `--only-repo yakaboskic/document-sanity-template`, so copies made with "Use this template" don't run it (and `init.py` removes it).

## Upgrade document-sanity

`pyproject.toml` pins a release tag, so every copy builds with the same tool. To upgrade, read the [release notes](https://github.com/yakaboskic/document-sanity/releases), change the tag on the dependency line, then:

```bash
make update                                   # uv lock && uv sync
uv run document-sanity skills --force         # the skill that matches the new tool
make check
```

`make install-pinned` installs strictly from `uv.lock` and fails if it's stale, for CI.

## House rules

```yaml
# sanitism.yaml
principles:
  one_manifest: everything else is generated, never hand-edited
  every_number_has_a_source: the file, command and date travel with the value
  versions_are_folders: not branches, and not final_v3_REAL.docx
  one_repo_per_obsession: papers, proposals and talks share figures and numbers
  same_input_same_output: a rebuild never surprises your co-authors
```

## More

- [document-sanity](https://github.com/yakaboskic/document-sanity): the tool, every command, and how releases work.
- [The conventions in detail](https://github.com/yakaboskic/document-sanity/tree/main/docs): figures, labels, preview blocks, variables, the HTML viewer, the bibliography, Word.
- [presentation-sanity-template](https://github.com/yakaboskic/presentation-sanity-template): the same idea for talks.

---

<sub>Part of <a href="https://sanitism.dev">Sanitism</a>. MIT licensed.</sub>
