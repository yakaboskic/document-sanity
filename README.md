# latex-builder

Build LaTeX documents, interactive HTML viewers, and preview-friendly markdown
from a single Markdown source of truth. `manifest.yaml` is the one source of
configuration per version; variables carry provenance; figures/equations/tables
render both to PDF and to markdown-native previews for GitHub/VSCode/Obsidian.

## What it does

| Command | Output | When to use |
|---|---|---|
| `latex-builder build --compile` | `out/<ver>/pdf/main.pdf` | Build the paper PDF. |
| `latex-builder html --open` | `out/<ver>/html/index.html` | Interactive viewer: TOC sidebar, KaTeX math, clickable variables with a provenance panel, hyperlinked bibliography. |
| `latex-builder preview` | Inline preview blocks in each `.md` | Make ```latex figure/equation/table blocks render as `![alt](path)` / `$$...$$` / `\|cell\|` so GitHub shows something meaningful. Idempotent; hash-tagged. |
| `latex-builder preview --check` | Exit 1 if stale | CI-friendly. |
| `latex-builder import` | New `src/<ver>/` tree | Convert an existing `\input{}`-style LaTeX project into the markdown-as-source-of-truth layout. |
| `latex-builder new-version` | Copied `src/<ver>/` | Snapshot today's version from the previous one. |
| `latex-builder init <name>` | Fresh project scaffold | Start a new manuscript project from scratch. |
| `latex-builder convert file.md/.tex` | The other format | One-off md↔tex conversion (useful for scripting). |

## Use it in your paper project (recommended)

Create a separate repo for each paper and declare `latex-builder` as a
dependency. This keeps paper content out of the tool's history and lets
multiple papers track different versions independently.

**`pyproject.toml`** (paper repo):

```toml
[project]
name = "my-paper"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "latex-builder @ git+https://github.com/yakaboskic/latex-builder.git@main",
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
uv sync                           # install latex-builder from GitHub
uv run latex-builder build --compile
uv run latex-builder html --open
```

A reference `Makefile` for paper repos is in
[`papers/pigean-indirect-support/Makefile`](https://github.com/yakaboskic/pigean-indirect-support/blob/main/Makefile)
(targets: `install`, `build`, `pdf`, `preview`, `preview-check`, `html`, `serve`, `clean`).

## Install the tool directly

For local development on the tool itself:

```bash
git clone https://github.com/yakaboskic/latex-builder
cd latex-builder
uv sync
uv run latex-builder --help
```

## Project layout

A paper project has this shape:

```
my-paper/
├── pyproject.toml              # declares latex-builder dependency
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

`latex-builder preview` auto-generates a markdown approximation next to each
```latex block so GitHub renders something useful:

~~~markdown
```latex
\begin{figure}[h!]
    \includegraphics[width=\textwidth]{figures/overview.png}
    \caption{Framework overview.}
    \label{fig:overview}
\end{figure}
```

<!-- latex-builder:preview:begin hash=a1b2c3d4 -->
![Framework overview.](../figures/overview.png)
<!-- latex-builder:preview:end -->
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

`latex-builder html` emits a single `index.html` (plus copied `figures/`)
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
src/<ver>/docs/*.md   ──┐
src/<ver>/manifest.yaml ─┼─► out/<ver>/latex/main.tex  ──► out/<ver>/pdf/main.pdf
templates/<tmpl>.tex  ──┘                    └─ bibtex resolved (pdflatex runs
                                                in the latex/ dir so
                                                openout_any=p doesn't block)
```

Section order and the bibliography placement are controlled from
`manifest.sections`. `_bibliography` is a pseudo-section that inserts
`\bibliography{references}` at that point; `_toc` similarly for
`\tableofcontents`.

## Versioning

```bash
latex-builder new-version               # copy latest -> MMDDYYYY-<fun-name>/
latex-builder new-version --strategy date    # MMDDYYYY
latex-builder new-version --strategy fun     # elegant-crimson-fox
latex-builder new-version --strategy both    # MMDDYYYY-elegant-crimson-fox (default)
```

`latex-builder build` / `html` / `preview` all auto-detect the latest
dated version if `--version` isn't given.

## Importing an existing LaTeX project

```bash
latex-builder import \
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

## Library inspiration

- [word-builder](https://github.com/yakaboskic/word-builder) — CLI architecture
  and markdown-as-source philosophy.
- [pigean-manuscripts](https://github.com/yakaboskic/pigean-manuscripts) —
  original build system, variable processor, figure manifest, versioning scheme.
