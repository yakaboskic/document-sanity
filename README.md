# document-sanity

Build PDF (LaTeX), interactive HTML, Word (`.docx`), and preview-friendly
markdown — all from a single Markdown source of truth. `manifest.yaml` is the
one source of configuration per version; variables carry provenance;
figures/equations/tables render across every target, including inline
GitHub/VSCode/Obsidian previews. Sibling project to
[`presentation-sanity`](https://github.com/yakaboskic/presentation-sanity);
both are part of [Sanitism](https://sanitism.dev): built for autists to
communicate their work, sanely.

```bash
uvx --from "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.0" \
  document-sanity init my-paper --title "My paper"
```

That's a named project from
[document-sanity-template](https://github.com/yakaboskic/document-sanity-template)
(a manuscript and a proposal starter, live at
<https://yakaboskic.github.io/document-sanity-template/>), with an
[agent skill](#agent-skill) installed. No clone, no git required. See
[Start a project](#start-a-project).

## What it does

| Command | Output | When to use |
|---|---|---|
| `document-sanity build --compile` | `out/<ver>/pdf/main.pdf` | Build the paper PDF. |
| `document-sanity html --open` | `out/<ver>/html/index.html` | Interactive viewer: TOC sidebar, KaTeX math, clickable variables with a provenance panel, hyperlinked bibliography. |
| `document-sanity word` | `out/<ver>/word/main.docx` | Build a Word document from a `.docx` template in `templates/` — styles are extracted from the template, figures are embedded, citations render as a numbered References list, and tables, headings and figures are kept together across page breaks (`--no-layout` skips that). |
| `document-sanity word --extract-styles` | `out/<ver>/word/styles.json` | Dump the template's extracted styles so you can hand-tune before the next build. |
| `document-sanity preview` | Inline preview blocks in each `.md` | Make ```latex figure/equation/table blocks render as `![alt](path)` / `$$...$$` / `\|cell\|` so GitHub shows something meaningful. Idempotent; hash-tagged. |
| `document-sanity preview --check` | Exit 1 if stale | CI-friendly. |
| `document-sanity import` | New `src/<ver>/` tree | Convert an existing `\input{}`-style LaTeX project into the markdown-as-source-of-truth layout. |
| `document-sanity new-version` | Copied `src/<ver>/` | Snapshot today's version from the previous one. |
| `document-sanity init [DIR]` | A project from the template | Start a new project: manuscript and/or proposal starters, the agent skill. See [Start a project](#start-a-project). |
| `document-sanity check [DOC…]` | Exit 1 on anything to fix | Every target (PDF, HTML, Word) of every document, plus `preview --check` and unresolved variables / citations / `\ref`s. One command before sharing. See [Check](#check-before-you-share). |
| `document-sanity site [DOC…]` | `site/` | Every document's HTML viewer, PDF and Word, with an index page. What the Pages workflow publishes. |
| `document-sanity pages init` | `.github/workflows/pages.yml` | Publish on GitHub Pages (public! it asks first). See [Publish on GitHub Pages](#publish-on-github-pages). |
| `document-sanity skills` | `.claude/skills/`, `.agents/skills/` | Install or refresh the [agent skill](#agent-skill). |
| `document-sanity convert file.md/.tex` | The other format | One-off md↔tex conversion (useful for scripting). |
| `document-sanity drawio sync <fig-id>` | Refreshed `figures/<id>/<id>.png` | Re-import regenerated source assets into a draw.io-composed figure (crop/position recorded in the .drawio XML) and re-export the PNG. See [docs/drawio-figures.md](docs/drawio-figures.md). |
| `document-sanity drawio status <fig-id>` | Exit 1 if stale | CI-friendly staleness check for composed figures. |

## Documentation

Opinionated conventions are documented in detail under [`docs/`](./docs):

- [Figures](./docs/figures.md) — subdirectory layout, target-specific artifact resolution, whitespace cropping.
- [References & labels](./docs/references-and-labels.md) — `fig:` / `tab:` / `eq:` prefix convention drives auto-numbering.
- [Preview blocks](./docs/preview-blocks.md) — hash-tagged markdown approximations of ```latex blocks for GitHub/VSCode.
- [Variables & provenance](./docs/variables-and-provenance.md) — `{{VAR:fmt}}` syntax + provenance metadata that powers the HTML viewer's side panel.
- [HTML viewer](./docs/html-viewer.md) — layout, TOC, KaTeX, figure modal, scroll-spy.
- [HTML multi-plot standard](./docs/html-multi-plot-standard.md) — Plotly normalization and tabbed layouts.
- [Bibliography](./docs/bibliography.md) — `.bib` parsing, citation numbering, entry rendering.

## Start a project

One command, no clone and no git:

```bash
uvx --from "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.0" \
  document-sanity init my-paper --title "My paper" --starter manuscript
cd my-paper
uv sync                                  # the pinned document-sanity; writes uv.lock (commit it)
make html VERSION=manuscript             # → out/manuscript/html/index.html
make pdf VERSION=manuscript              # → out/manuscript/pdf/main.pdf (needs TeX)
uv run document-sanity check             # every target, before you share
```

`init` copies the snapshot of
[`document-sanity-template`](https://github.com/yakaboskic/document-sanity-template)
that ships inside this release, so a project made by vX.Y.Z is the template
vX.Y.Z was released with, and its dependency line is pinned back to vX.Y.Z.

- **Answers** are prompted for, or given as flags: `--name` (default: the
  folder's name), `--title`, `--author` and `--email` (default: your git
  config), `--description`, and `--starter` (`manuscript`, `proposal`, or
  `both`, the default). `--yes` takes the defaults for anything unset. The
  name goes into `pyproject.toml` and `README.md`; the title and author into
  each kept starter's `manifest.yaml` (the lines the template marks
  `TEMPLATE:`); the starters you don't keep are left out.
- **The folder** can be new, empty, or an existing one to knit into (`init
  .`). Everything is assembled in memory first. If any file would be
  replaced, `init` lists them and writes nothing; `--force` overwrites them.
  A folder that already has documents under `src/` is refused outright
  (`skills` refreshes the skill; `new-version` adds a document).
- **`--git`** adds `git init` and a first commit. Without it there's no `.git`.
- **`uv.lock`** is left out, `--in-place` included: the template's lock is
  one release behind the snapshot's pin, and renaming the project renames its
  root package. The project's first `uv sync` writes a lock for the pinned
  tag. Commit it; the Pages workflow installs with `--locked`.
- **`--from gh:owner/repo[@ref]`** starts from a GitHub tarball instead, e.g.
  your lab's fork of the template. No git binary needed; `GH_TOKEN` (or
  `GITHUB_TOKEN`) reaches a private fork. A fork's own pin is left alone.
- **The agent skill** goes into `.claude/skills/document-sanity/` and
  `.agents/skills/document-sanity/` unless `--no-skills` ([below](#agent-skill)).

On GitHub, **"Use this template"** on document-sanity-template works too:
its `init.py` is a thin shim that runs `document-sanity init --in-place`
with the pinned version, so both ways share one code path.

## Use it in your paper project

Each paper is its own repo that declares `document-sanity` as a dependency.
This keeps paper content out of the tool's history and lets multiple papers
track different versions independently. `init` writes this for you:

**`pyproject.toml`** (paper repo):

```toml
[project]
name = "my-paper"
version = "0.1.0"
requires-python = ">=3.10"
# Pin a release tag (https://github.com/yakaboskic/document-sanity/releases),
# not @main; to upgrade, change the tag and run `uv lock`.
dependencies = [
    "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.0",
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

The template's [`Makefile`](https://github.com/yakaboskic/document-sanity-template/blob/main/Makefile)
is the reference for paper repos (targets: `install`, `latex`, `pdf`,
`preview`, `preview-check`, `html`, `word`, `serve`, `check`, `site`, `clean`).

## Agent skill

`skills/document-sanity/` is a skill for coding agents: a router
(`SKILL.md`, invoked as `/document-sanity [mode]` in Claude Code) and one file
per mode under `modes/`: `_shared` (the ground rules), `init`, `onboard`
(Word / PDF / CSV sources → a new document), `iterate` (the edit → preview →
build loop), `figures` (including draw.io sync), `variables`, `cite`, `word`
(the .docx template and styles), `version`, `import` (LaTeX → markdown),
`check` and `deploy`.

- **It explains; the CLI does.** Every mode works through commands
  (`new-version`, `preview`, `check`, `pages init`, …) rather than having
  the agent write generated files. When a step is deterministic, it belongs
  in the CLI.
- **It finds the project** from its sentinel files (a `pyproject.toml` that
  depends on document-sanity, next to `src/<doc>/manifest.yaml`) and resolves
  every path from there.
- **It checks the version.** It runs `document-sanity --version`, and when
  that differs from the version the skill was written for, it trusts
  `--help` over its own text.
- **It ends every iteration with `preview`**, and runs `check` before saying
  done.
- **It asks before anything public.** The deploy mode warns that a Pages site
  is public even from a private repository, waits for a yes, and won't
  publish a document with a `metadata.notice` unless the owner says so.

The wheel carries the skill. `init` installs it into new projects, and
`document-sanity skills [--force]` installs or refreshes it in an existing
one. Run that after upgrading, so the skill matches the tool. The repo is also
a Claude Code plugin (`.claude-plugin/plugin.json`).

## Check before you share

```bash
uv run document-sanity check              # every document under src/
uv run document-sanity check manuscript   # or some (inside src/<doc>/, that one)
uv run document-sanity check --no-pdf     # no TeX here
```

For each document, in order: `preview --check` (every ```latex block's
preview is current), the LaTeX build compiled to PDF (`!` errors in the log
fail it; no TeX installed is a warning), unresolved references (undefined
`{{VARIABLES}}`, `\cite` keys missing from `references.bib`, `\ref`s with no
`\label`, sections listed but missing), the HTML viewer, and the Word file
(laid out, as `document-sanity word` makes it). The builders' output is
captured and shown only for a failing step (`-v` shows everything). It exits
non-zero on any error, so it works in CI too. All outputs land in `out/<doc>/`
as usual.

## Publish on GitHub Pages

> A GitHub Pages site is **public**, even when the repository is private.

```bash
uv run document-sanity pages init          # asks first (--yes once the owner agreed)
uv run document-sanity site                # what the workflow will publish → site/
```

`pages init` writes `.github/workflows/pages.yml`. On each push to `main` it:

1. checks out the repo, sets up uv, and installs a TeX Live subset from
   Ubuntu's packages (`texlive-latex-recommended`, `texlive-latex-extra`,
   `texlive-fonts-recommended`, `lmodern`: pdflatex, bibtex, natbib, …);
2. runs `uv sync --locked` (the project's pinned document-sanity);
3. runs `document-sanity site`: every document under `src/` → its HTML
   viewer, PDF and Word file, gathered into `site/` with an index page;
4. uploads `site/` and deploys it.

```
site/index.html              one card per document: read online · PDF · Word
site/<doc>/index.html        the HTML viewer (with a small "all documents · PDF · Word" pill)
site/<doc>/<doc>.pdf, .docx
```

Then turn Pages on (Settings → Pages → Source: **GitHub Actions**, or
`gh api -X POST repos/OWNER/REPO/pages -f build_type=workflow`) and push.

**PDFs need TeX on the runner.** The apt subset is the template's needs
plus headroom, needs no third-party action, and adds about a minute or two to
each run. A template that `\usepackage`s something outside it fails the
deploy with a missing `.sty`. `pages init --no-pdf` leaves TeX out entirely
and publishes the HTML viewer and Word only (fast, nothing to install).

**The privacy gate.** `pages init` asks before writing anything (or, with no
terminal, refuses without `--yes`). A document whose manifest sets
`metadata.notice` (a CUI banner, a distribution statement) is refused unless
`--allow-notice`, and the workflow's `site` call enforces the same rule on
every build, so a notice added later stops the deploy instead of publishing
it. To publish some documents only, name them: `pages init manuscript`.

Options: `--branch` (default `main`), `--only-repo OWNER/NAME` (forks and
template copies skip the job; the template uses this for its own demo),
`--force` to regenerate. Action versions at the time of writing:
`actions/checkout@v7`, `configure-pages@v6`, `upload-pages-artifact@v5`,
`deploy-pages@v5`, and `astral-sh/setup-uv@v10.3.0` (setup-uv publishes no
floating major tag past v7).

Every link in `site/` is relative, so the same folder works on any static
host (`aws s3 sync`, Netlify, an intranet share) under any URL prefix.

## Install the tool directly

For local development on the tool itself:

```bash
git clone https://github.com/yakaboskic/document-sanity
cd document-sanity
uv sync
uv run document-sanity --help
uv run pytest
```

To iterate on the tool against a real project, clone
[`document-sanity-template`](https://github.com/yakaboskic/document-sanity-template)
alongside this repo and point its dependency at the local checkout:

```toml
[tool.uv.sources]
document-sanity = { path = "../document-sanity", editable = true }
```

### Releasing

Paper repos and the template pin release tags, so a change reaches them
only through a release. Each release also carries a snapshot of the template
(for `init`), so the two move together:

1. Bump the version in four places: `version` in `pyproject.toml`,
   `__version__` in `src/document_sanity/__init__.py`, `metadata.version`
   in `skills/document-sanity/SKILL.md`, and `version` in
   `.claude-plugin/plugin.json` (`tests/test_skill.py` fails until they
   agree). Update the tags in the snippets above and in the skill's `init`
   mode.
2. In `document-sanity-template`, move the pin to the new tag (the
   `pyproject.toml` dependency line and the README's `uvx` line), regenerate
   the demo workflow with `document-sanity pages init --yes --force
   --only-repo yakaboskic/document-sanity-template`, and commit.
3. Back here, refresh the snapshot from that commit and commit it:
   ```bash
   uv run python scripts/sync_template.py      # tracked files only, via git archive
   uv run pytest
   ```
4. Push to `main`, then tag and publish:
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z — summary" && git push origin vX.Y.Z
   gh release create vX.Y.Z --verify-tag --title "vX.Y.Z — summary" --notes-file notes.md
   ```
5. In the template, once the tag exists: `uv lock` (it resolves the new tag),
   `make check`, commit `uv.lock`, and push. The Pages workflow (which installs
   with `--locked`) deploys the demo. The snapshot still carries the previous
   lock, one reason `init` leaves `uv.lock` out (in every mode): a new
   project's first `uv sync` writes its own.

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
  # Optional: set apart above the first section in every output (centered,
  # italic, small type). For legends, CUI banners, distribution statements.
  notice: |
    This document contains proprietary data; see the restriction notice.

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
document-sanity new-version --source manuscript                  # → MMDDYYYY-<fun-name>/
document-sanity new-version --source manuscript --strategy date  # MMDDYYYY
document-sanity new-version --source manuscript --strategy fun   # elegant-crimson-fox
document-sanity new-version --source proposal --name resubmission
```

Without `--source` it copies the latest version, which is the newest dated
folder, or else the last name alphabetically.

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
- **Layout** — table rows don't split and the header row repeats, headings
  keep with the next paragraph, figures keep with their captions, and
  equations take the body font size. `--no-layout` skips this pass.

## Library inspiration

- [word-builder](https://github.com/yakaboskic/word-builder) — CLI architecture,
  docx-template philosophy (now ported into this project as the `word`
  subcommand).
- [pigean-manuscripts](https://github.com/yakaboskic/pigean-manuscripts) —
  original build system, variable processor, figure manifest, versioning scheme.
