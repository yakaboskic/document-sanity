# document-sanity

Build PDF (LaTeX), interactive HTML, Word (`.docx`), and preview-friendly
markdown — all from a single Markdown source of truth. `manifest.yaml` is the
one source of configuration per version; variables carry provenance;
figures/equations/tables render across every target, including inline
GitHub/VSCode/Obsidian previews.

## What it does

| Command | Output | When to use |
|---|---|---|
| `document-sanity build --compile` | `out/<ver>/pdf/main.pdf` | Build the paper PDF. |
| `document-sanity html --open` | `out/<ver>/html/index.html` | Interactive viewer: TOC sidebar, KaTeX math, clickable variables with a provenance panel, hyperlinked bibliography. |
| `document-sanity word` | `out/<ver>/word/main.docx` | Build a Word document from a `.docx` template in `templates/` — styles are extracted from the template, figures are embedded, citations render as a numbered References list. |
| `document-sanity word --extract-styles` | `out/<ver>/word/styles.json` | Dump the template's extracted styles so you can hand-tune before the next build. |
| `document-sanity preview` | Inline preview blocks in each `.md` | Make ```latex figure/equation/table blocks render as `![alt](path)` / `$$...$$` / `\|cell\|` so GitHub shows something meaningful. Idempotent; hash-tagged. |
| `document-sanity preview --check` | Exit 1 if stale | CI-friendly. |
| `document-sanity import` | New `src/<ver>/` tree | Convert an existing `\input{}`-style LaTeX project into the markdown-as-source-of-truth layout. |
| `document-sanity new-version` | Copied `src/<ver>/` | Snapshot today's version from the previous one. |
| `document-sanity init <name>` | Fresh project scaffold | Start a new manuscript project from scratch. |
| `document-sanity convert file.md/.tex` | The other format | One-off md↔tex conversion (useful for scripting). |

## Documentation

Opinionated conventions are documented in detail under [`docs/`](./docs):

- [Figures](./docs/figures.md) — subdirectory layout, target-specific artifact resolution, whitespace cropping.
- [References & labels](./docs/references-and-labels.md) — `fig:` / `tab:` / `eq:` prefix convention drives auto-numbering.
- [Preview blocks](./docs/preview-blocks.md) — hash-tagged markdown approximations of ```latex blocks for GitHub/VSCode.
- [Variables & provenance](./docs/variables-and-provenance.md) — `{{VAR:fmt}}` syntax + provenance metadata that powers the HTML viewer's side panel.
- [HTML viewer](./docs/html-viewer.md) — layout, TOC, KaTeX, figure modal, scroll-spy.
- [HTML multi-plot standard](./docs/html-multi-plot-standard.md) — Plotly normalization and tabbed layouts.
- [Bibliography](./docs/bibliography.md) — `.bib` parsing, citation numbering, entry rendering.

## Use it in your paper project (recommended)

Create a separate repo for each paper and declare `document-sanity` as a
dependency. This keeps paper content out of the tool's history and lets
multiple papers track different versions independently.

**`pyproject.toml`** (paper repo):

```toml
[project]
name = "my-paper"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@main",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.metadata]
allow-direct-references = true  # required for the git+ dependency

[tool.hatch.build.targets.wheel]
bypass-selection = true          # this repo has no importable Python
```

Then:

```bash
uv sync                           # install document-sanity from GitHub
uv run document-sanity build --compile
uv run document-sanity html --open
```

A reference `Makefile` for paper repos is in
[`papers/pigean-indirect-support/Makefile`](https://github.com/yakaboskic/pigean-indirect-support/blob/main/Makefile)
(targets: `install`, `build`, `pdf`, `preview`, `preview-check`, `html`, `serve`, `clean`).

## Install the tool directly

For local development on the tool itself:

```bash
git clone https://github.com/yakaboskic/document-sanity
cd document-sanity
uv sync
uv run document-sanity --help
```

## Project layout

A paper project has this shape:

```
my-paper/
├── pyproject.toml              # declares document-sanity dependency
├── templates/
│   ├── article.tex             # or nature.tex for sn-jnl (Springer Nature)
│   ├── *.cls / *.bst           # class + bib style files copied into build
├── src/
│   ├── 03302026/               # MMDDYYYY-named version directory
│   │   ├── manifest.yaml       # single source of configuration
│   │   ├── docs/               # *.md sections, in manifest.sections order
│   │   ├── figures/            # png/jpg/pdf/html images
│   │   ├── tables/             # optional: legacy .tex tables (can inline)
│   │   └── references.bib      # bibliography
│   └── 04202026-elegant-fox/   # another snapshot
└── out/                        # generated — gitignored
    └── 03302026/
        ├── latex/main.tex      # compilation-ready LaTeX
        ├── pdf/main.pdf        # compiled PDF
        └── html/index.html     # interactive viewer
```

## manifest.yaml

Single source of truth per version:

```yaml
metadata:
  title: "My Paper Title"
  authors:
    - name: "First Author"
      email: "first@example.com"
      affiliations: [1]
  affiliations:
    1:
      department: "Department"
      institution: "University"
  abstract: |
    Paper abstract. Variable tokens like {{NUM_SAMPLES:,}} and inline math
    $p = {{PVAL:.2e}}$ are substituted at build time.
  keywords: [genetics, drug-targets, bayesian]
  template: nature              # or article; loads templates/<name>.tex

sections:
  - docs/introduction.md
  - docs/methods.md
  - docs/results.md
  - docs/discussion.md
  - _bibliography              # pseudo-section: inserts \bibliography{} here
  - docs/supplementary.md

variables:
  NUM_SAMPLES: 1000             # simple form
  PVAL:                         # full form with provenance (powers the
    value: 0.0087               # interactive HTML viewer's panel)
    provenance:
      source: data/results.csv
      data: [data/raw.parquet]
      command: python scripts/fit.py --out data/results.csv
      description: Primary p-value from the genome-wide regression.
      updated: "2026-04-20"

figures:
  fig_1:
    source: figures/overview.png
    width: "\\textwidth"
  "2":                          # canva page mapping; {{canva:2}} resolves here
    source: figures/pigean-figure-1.png

tables:
  results_summary:
    source: tables/results.tex
    format: latex
```

## Variable and figure syntax in markdown

```markdown
We analyzed {{NUM_SAMPLES:,}} samples ($p = {{PVAL:.2e}}$).

```latex
\begin{figure}[h!]
    \centering
    {{fig:fig_1}}
    \caption{Framework overview.}
    \label{fig:overview}
\end{figure}
```
```

**Supported format specs** (Python-style): `:.2f`, `:.2e`, `:,`, `:.1%`.

Undefined variables render as `XXXX` (configurable via `--placeholder`) and
are reported in the build summary.

## Preview blocks

`document-sanity preview` auto-generates a markdown approximation next to each
```latex block so GitHub renders something useful:

~~~markdown
```latex
\begin{figure}[h!]
    \includegraphics[width=\textwidth]{figures/overview.png}
    \caption{Framework overview.}
    \label{fig:overview}
\end{figure}
```

<!-- document-sanity:preview:begin hash=a1b2c3d4 -->
![Framework overview.](../figures/overview.png)
<!-- document-sanity:preview:end -->
~~~

- Block kinds handled: `figure`/`figure*`, `table`/`table*`/`longtable`,
  `align`/`equation`/`eqnarray`/`gather`/`multline` and their starred variants.
- Template `\newcommand` macros (e.g. `\prob` → `\text{Pr}`) auto-expand inside
  `$...$`, `$$...$$`, `\[...\]` math so KaTeX-based viewers don't choke.
- `.pdf` figures fall back to a sibling `.png` if one exists (md viewers
  can't render PDFs).
- Paths are computed relative to the doc's own directory.
- Hand-edits between `preview:begin/end` markers get overwritten; edit the
  source ```latex block instead.
- `preview --check` returns non-zero on drift — wire into CI.

## Interactive HTML viewer

`document-sanity html` emits a single `index.html` (plus copied `figures/`)
with:

- Left sidebar TOC with scroll-spy and hyperlinked headings.
- Client-side KaTeX math, with `\newcommand` macros from the template
  registered automatically.
- Clickable variable tokens — a **right-side provenance panel** slides in
  showing description, an inputs→command→output graph, and the updated
  timestamp. The clicked token stays outlined while the panel is open.
- Hyperlinked bibliography: `\cite{key}` → numbered link → entry rendered
  from `references.bib`.
- Figures: `.png`/`.jpg` → `<img>`, `.html` → `<iframe>` (great for Plotly),
  `.pdf` → `<embed>`.
- Self-contained: only external deps are Tailwind Play CDN and KaTeX CDN.
  Serve with `python3 -m http.server` from the `html/` directory.

## Build pipeline

```
                             ┌─► out/<ver>/latex/main.tex ──► out/<ver>/pdf/main.pdf
src/<ver>/docs/*.md     ─┐   │
src/<ver>/manifest.yaml ─┼───┼─► out/<ver>/html/index.html
src/<ver>/figures/       │   │
templates/<tmpl>.tex    ─┤   └─► out/<ver>/word/main.docx
templates/<tmpl>.docx   ─┘
```

The same markdown sources feed PDF (via LaTeX), HTML, and Word simultaneously.
Section order and bibliography placement are controlled from
`manifest.sections`. `_bibliography` is a pseudo-section that inserts
`\bibliography{references}` (LaTeX) / a References section (Word) /
a bibliography pane (HTML) at that point; `_toc` similarly for
`\tableofcontents`.

## Versioning

```bash
document-sanity new-version               # copy latest -> MMDDYYYY-<fun-name>/
document-sanity new-version --strategy date    # MMDDYYYY
document-sanity new-version --strategy fun     # elegant-crimson-fox
document-sanity new-version --strategy both    # MMDDYYYY-elegant-crimson-fox (default)
```

`document-sanity build` / `html` / `preview` all auto-detect the latest
dated version if `--version` isn't given.

## Importing an existing LaTeX project

```bash
document-sanity import \
  --source ./my-old-paper \
  --target ./my-new-paper \
  --manuscript indirect-support \
  --version 03302026 \
  --name 03302026
```

Walks `versions/<manuscript>/main_<ver>.tex` + `sections/<manuscript>/<ver>/*.tex`
and produces a `src/<ver>/` tree: sections become `.md` with ```latex blocks
preserving environments we can't losslessly markdown-ify (figures, tables,
align, etc.), variables are copied from `variables/<manuscript>.json`, the
bib and figures are brought along.

## Word (.docx) output

Drop a `.docx` template into `templates/` and `document-sanity word` emits a
Word document from the same markdown sources:

```
templates/apiflow.docx         # headers, footers, theme, fonts — all preserved
src/<ver>/manifest.yaml        # points at it via metadata.word_template: apiflow
src/<ver>/docs/*.md            # same sections as the LaTeX build
```

- **Styles** are extracted from the template's `styles.xml` + `theme1.xml`
  (Title / Heading 1-3 / Normal, accent colors) and applied to the generated
  body. Pass `--styles path.json` to override after hand-tuning.
- **Variables** (`{{VAR}}`, `{{VAR:.2e}}`) resolve the same way as in the
  LaTeX build, using `manifest.variables`.
- **Figures** — `![alt](path)` and ` ```latex \includegraphics{path} ``` `
  blocks are embedded inline as centered drawings with a caption. The
  `'word'` target prefers `png/jpg/gif/bmp` (DOCX has no native PDF/SVG).
- **Bibliography** — `\cite{key}` renders as numbered `[N]` inline;
  duplicate keys reuse the same number. A `References` section is appended
  at the end (or wherever `_bibliography` is placed in `manifest.sections`).
- **Body preservation** — only the template's `<w:sectPr>` (headers,
  footers, margins, theme refs) is kept. Body content is replaced.

## Library inspiration

- [word-builder](https://github.com/yakaboskic/word-builder) — CLI architecture,
  docx-template philosophy (now ported into this project as the `word`
  subcommand).
- [pigean-manuscripts](https://github.com/yakaboskic/pigean-manuscripts) —
  original build system, variable processor, figure manifest, versioning scheme.
