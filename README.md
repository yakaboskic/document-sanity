<a href="https://sanitism.dev"><img src="https://sanitism.dev/media/one-number-poster.jpg" alt="One number in manifest.yaml and a sentence in docs/results.md build into LaTeX, PDF, Word, HTML, slides and a blog post, each showing 12,453." width="100%"></a>

# document-sanity

**Write a paper, proposal or report once in Markdown. Get LaTeX, a PDF, a Word file and an interactive HTML page, with every number traced to the script that made it.**

Part of [Sanitism](https://sanitism.dev): built for autists to communicate their work, sanely. The sibling for talks is [presentation-sanity](https://github.com/yakaboskic/presentation-sanity).

**See it:** [the starter paper](https://document.sanitism.dev/manuscript/), [its PDF](https://document.sanitism.dev/manuscript/manuscript.pdf), [its Word file](https://document.sanitism.dev/manuscript/manuscript.docx) and [a proposal](https://document.sanitism.dev/proposal/), all built from [document-sanity-template](https://github.com/yakaboskic/document-sanity-template).

## Start a project

<img src="https://sanitism.dev/figures/two-ways-in.svg" alt="A template repo leads two ways. Use this template on GitHub gives the project a repo with history. Running uvx init gives a plain folder with no git. Both arrive at the same project." width="100%">

**Just give me a folder.** No clone, no git. It needs [uv](https://docs.astral.sh/uv/):

```bash
uvx --from "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.1" \
  document-sanity init my-paper --title "My paper"
```

```bash
cd my-paper
uv sync                                  # the pinned document-sanity; writes uv.lock (commit it)
make html VERSION=manuscript             # → out/manuscript/html/index.html
make pdf VERSION=manuscript              # → out/manuscript/pdf/main.pdf (needs TeX)
uv run document-sanity check             # every target, before you share
```

**Keep it in git.** On [document-sanity-template](https://github.com/yakaboskic/document-sanity-template), click **Use this template**, clone your copy and run `python init.py`. It is a thin shim over the same `init`, so both ways give you the same project: the starters you asked for, pinned to this release, with the [agent skill](#agent-skill) installed.

<details>
<summary><b>What <code>init</code> does, flag by flag</b></summary>

`init` copies the snapshot of [`document-sanity-template`](https://github.com/yakaboskic/document-sanity-template) that ships inside this release, so a project made by vX.Y.Z is the template vX.Y.Z was released with, and its dependency line is pinned back to vX.Y.Z.

- **Answers** are prompted for, or given as flags: `--name` (default: the folder's name), `--title`, `--author` and `--email` (default: your git config), `--description`, and `--starter` (`manuscript`, `proposal`, or `both`, the default). `--yes` takes the defaults for anything unset. The name goes into `pyproject.toml` and `README.md`; the title and author into each kept starter's `manifest.yaml` (the lines the template marks `TEMPLATE:`); the starters you don't keep are left out.
- **The folder** can be new, empty, or an existing one to knit into (`init .`). Everything is assembled in memory first. If any file would be replaced, `init` lists them and writes nothing; `--force` overwrites them. A folder that already has documents under `src/` is refused outright (`skills` refreshes the skill; `new-version` adds a document).
- **`--git`** adds `git init` and a first commit. Without it there's no `.git`.
- **`uv.lock`** is left out, `--in-place` included: the template's lock is one release behind the snapshot's pin, and renaming the project renames its root package. The project's first `uv sync` writes a lock for the pinned tag. Commit it; the Pages workflow installs with `--locked`.
- **`--from gh:owner/repo[@ref]`** starts from a GitHub tarball instead, e.g. your lab's fork of the template. No git binary needed; `GH_TOKEN` (or `GITHUB_TOKEN`) reaches a private fork. A fork's own pin is left alone.
- **The agent skill** goes into `.claude/skills/document-sanity/` and `.agents/skills/document-sanity/` unless `--no-skills`.

</details>

## What goes in, what comes out

<img src="https://sanitism.dev/figures/document-pipeline.svg" alt="What you write: manifest.yaml, docs/*.md, figures, tables and refs.bib, and templates. One document-sanity check builds every target. What your readers get: LaTeX, PDF, Word, and interactive HTML where 12,453 traces back to data/qc.csv and scripts/qc.py." width="100%">

You write plain text that diffs well. One `manifest.yaml` per document holds the title, authors, section order and every number with its source. The same Markdown sections then print four ways:

- **LaTeX.** A clean, compilation-ready `out/<doc>/latex/main.tex` from your own `templates/<name>.tex`, for the journal or Overleaf.
- **PDF.** That LaTeX compiled with your class and bib style.
- **Word.** A `.docx` built on your own Word template: its headers, footers, theme and styles are kept, and tables, headings and figures stay together across page breaks.
- **Interactive HTML.** A single page with a contents sidebar, KaTeX math, a linked bibliography, and numbers that open their provenance when clicked.

| Command | Output | When |
|---|---|---|
| `document-sanity check [DOC…]` | every target, plus broken references | Before you share. Exits non-zero on anything to fix. |
| `document-sanity build --compile` | `out/<doc>/latex/`, `out/<doc>/pdf/main.pdf` | The LaTeX tree and the PDF. |
| `document-sanity word` | `out/<doc>/word/main.docx` | The Word file. |
| `document-sanity html --open` | `out/<doc>/html/index.html` | The interactive viewer. |
| `document-sanity preview` | preview blocks in each `.md` | Makes ```` ```latex ```` blocks readable on GitHub. |
| `document-sanity new-version` | a copied `src/<doc>/` | A new version is a new folder. |
| `document-sanity site` / `pages init` | `site/`, a Pages workflow | Publish every document ([below](#publish-on-github-pages)). |

<details>
<summary><b>Every command</b></summary>

| Command | Output | When to use |
|---|---|---|
| `document-sanity init [DIR]` | A project from the template | Start a new project ([above](#start-a-project)). |
| `document-sanity build --compile` | `out/<doc>/pdf/main.pdf` | Build the LaTeX tree and compile the PDF. |
| `document-sanity html --open` | `out/<doc>/html/index.html` | Interactive viewer: TOC sidebar, KaTeX math, clickable variables with a provenance panel, hyperlinked bibliography. |
| `document-sanity word` | `out/<doc>/word/main.docx` | Word document from a `.docx` template in `templates/`. Styles are extracted from the template, figures are embedded, citations render as a numbered References list, and tables, headings and figures are kept together across page breaks (`--no-layout` skips that). |
| `document-sanity word --extract-styles` | `out/<doc>/word/styles.json` | Dump the template's extracted styles to hand-tune before the next build. |
| `document-sanity preview` | Inline preview blocks in each `.md` | Make ```` ```latex ```` figure/equation/table blocks render as `![alt](path)` / `$$...$$` / `\|cell\|` so GitHub shows something meaningful. Idempotent; hash-tagged. |
| `document-sanity preview --check` | Exit 1 if stale | CI-friendly. |
| `document-sanity check [DOC…]` | Exit 1 on anything to fix | Every target (PDF, HTML, Word) of every document, plus `preview --check` and unresolved variables / citations / `\ref`s ([below](#check-before-you-share)). |
| `document-sanity site [DOC…]` | `site/` | Every document's HTML viewer, PDF and Word, with an index page. What the Pages workflow publishes. |
| `document-sanity pages init` | `.github/workflows/pages.yml` | Publish on GitHub Pages (public! it asks first). |
| `document-sanity new-version` | Copied `src/<doc>/` | Snapshot a document into a new version folder. |
| `document-sanity import` | New `src/<doc>/` tree | Convert an existing `\input{}`-style LaTeX project into Markdown sources. |
| `document-sanity skills` | `.claude/skills/`, `.agents/skills/` | Install or refresh the [agent skill](#agent-skill). |
| `document-sanity convert file.md/.tex` | The other format | One-off md↔tex conversion (useful for scripting). |
| `document-sanity drawio sync <fig-id>` | Refreshed `figures/<id>/<id>.png` | Re-import regenerated source assets into a draw.io-composed figure and re-export the PNG ([docs](docs/drawio-figures.md)). |
| `document-sanity drawio status <fig-id>` | Exit 1 if stale | CI-friendly staleness check for composed figures. |

</details>

## A project, folder by folder

This is what `init` writes. Every document is a folder under `src/`, and versions are folders too.

```
my-paper/
├── pyproject.toml          # pins document-sanity to a release
├── Makefile                # install, latex, pdf, html, word, check, site, …
├── AGENTS.md               # points coding agents at the skill
├── templates/
│   ├── article.tex         # LaTeX template (the manuscript's look)
│   ├── proposal.tex        # the proposal's: same packages, unnumbered sections
│   └── article.docx        # Word template: header logo, page-of-N, watermark, styles
├── styles/
│   ├── article.yaml        # Word styles, round-tripped from the template
│   └── article.css         # extra HTML styles
├── src/
│   ├── manuscript/         # a paper: title block, abstract, IMRaD sections
│   │   ├── manifest.yaml   # the one source of configuration
│   │   ├── docs/*.md       # sections, in manifest order
│   │   ├── figures/<id>/   # one folder per figure, any formats
│   │   ├── tables/         # CSV, TSV, Markdown or LaTeX tables
│   │   └── references.bib
│   └── proposal/           # a proposal: hand-numbered sections, its own cover
└── out/                    # generated, gitignored
    └── manuscript/{latex,pdf,html,word}/
```

## The manifest

One file per document. This is the starter manuscript's, shortened:

```yaml
metadata:
  title: "A Starter Manuscript Built with document-sanity"
  authors:
    - { name: "First Author", email: "first.author@example.edu", affiliations: [1] }
  affiliations:
    1: { department: "Department of Research", institution: "Example University" }
  abstract: |
    We analyzed {{NUM_SAMPLES:,}} samples and found a significant effect
    ($p = {{PVAL:.2e}}$, R<sup>2</sup> = {{R2:.2f}}).
  template: article            # templates/article.tex   (LaTeX, PDF)
  word_template: article       # templates/article.docx  (Word)
  # notice: |                  # optional banner above the first section, in every
  #   Distribution limited.    #   output (CUI, distribution statements)

sections:
  - docs/introduction.md
  - docs/methods.md
  - docs/results.md
  - docs/discussion.md
  - _bibliography              # inserts the reference list here

variables:
  NUM_SAMPLES: 1247            # the simple form
  PVAL:                        # the full form: the HTML viewer shows where it came from
    value: 0.0087
    provenance:
      description: P-value of the primary test, after Benjamini–Hochberg adjustment.
      source: data/analysis_results.parquet
      data: [data/raw_measurements.csv, data/phenotype_metadata.tsv]
      command: python scripts/primary_test.py --out data/analysis_results.parquet
      updated: "2026-04-21"

figures:
  example: { width: "\\textwidth" }   # picks figures/example/example.{pdf,png,svg,html} per target

tables:
  subgroup_summary: { source: tables/subgroup_summary.csv, format: csv }
```

## Writing in Markdown

````markdown
We analyzed {{NUM_SAMPLES:,}} samples ($p = {{PVAL:.2e}}$), summarized in Table \ref{tab:subgroups}.

{{tab:subgroup_summary}}

```latex
\begin{figure}[h!]
    \centering
    {{fig:example}}
    \caption{The framework at a glance.}
    \label{fig:overview}
\end{figure}
```
````

- **Numbers** come from `{{NAME}}` or `{{NAME:fmt}}` with Python-style specs (`:,`, `:.2f`, `:.2e`, `:.1%`). An undefined name renders as `XXXX` and is reported, never silently blank.
- **Figures** live in `figures/<id>/` in as many formats as you have; each target picks its best (PDF prefers vector, HTML prefers interactive HTML or SVG, Word prefers raster). See [docs/figures.md](docs/figures.md).
- **Tables** come from CSV, TSV, Markdown or LaTeX files via `{{tab:<id>}}`, or as plain pipe tables inline.
- **Citations and references** are LaTeX-shaped everywhere: `\cite{key}` against `references.bib`, and `\ref{fig:…}` / `tab:` / `eq:` labels numbered in every output ([docs](docs/references-and-labels.md)).
- **LaTeX where it counts.** Anything Markdown can't say goes in a ```` ```latex ```` block. `document-sanity preview` writes a readable stand-in next to each one so GitHub, VS Code and Obsidian show something real ([docs](docs/preview-blocks.md)).

## Check before you share

```bash
uv run document-sanity check              # every document under src/
uv run document-sanity check manuscript   # or some (inside src/<doc>/, that one)
uv run document-sanity check --no-pdf     # no TeX here
```

For each document, in order: `preview --check` (every ```` ```latex ```` block's preview is current), the LaTeX build compiled to PDF (`!` errors in the log fail it; no TeX installed is a warning), unresolved references (undefined `{{VARIABLES}}`, `\cite` keys missing from `references.bib`, `\ref`s with no `\label`, sections listed but missing), the HTML viewer, and the Word file. Builder output is shown only for a failing step (`-v` shows everything). It exits non-zero on any error, so it works in CI too.

## Publish on GitHub Pages

> [!WARNING]
> A GitHub Pages site is **public**, even when the repository is private.

```bash
uv run document-sanity pages init          # asks first (--yes once the owner agreed)
uv run document-sanity site                # what the workflow will publish → site/
```

`pages init` writes `.github/workflows/pages.yml`. On each push to `main` it checks out the repo, installs a TeX Live subset from Ubuntu's packages, runs `uv sync --locked`, runs `document-sanity site` (every document's HTML viewer, PDF and Word, with an index page) and deploys `site/`. Then turn Pages on (Settings → Pages → Source: **GitHub Actions**) and push. The [template's own demo](https://document.sanitism.dev/) is built exactly this way.

- **The privacy gate.** `pages init` asks before writing anything (with no terminal, it refuses without `--yes`). A document whose manifest sets `metadata.notice` is refused unless `--allow-notice`, and the workflow enforces the same rule on every build, so a notice added later stops the deploy instead of publishing it. Name documents to publish only those: `pages init manuscript`.
- **PDFs need TeX on the runner.** The apt subset adds a minute or two per run; `--no-pdf` leaves TeX out and publishes HTML and Word only.
- **Options:** `--branch` (default `main`), `--only-repo OWNER/NAME` (forks and template copies skip the job), `--force` to regenerate.
- **Any static host works.** Every link in `site/` is relative, so the same folder works on S3, Netlify or an intranet share under any URL prefix.

## Versions are folders

```bash
uv run document-sanity new-version --source manuscript                  # → MMDDYYYY-<fun-name>/
uv run document-sanity new-version --source manuscript --strategy date  # MMDDYYYY
uv run document-sanity new-version --source proposal --name resubmission
```

The original stays as the archived snapshot. Without `--source` it copies the latest version: the newest dated folder, or else the last name alphabetically. `build`, `html` and `preview` default to that latest version too.

**Coming from a LaTeX project?** `document-sanity import --source ./old-paper --target ./new-paper --manuscript <name> --version <ver>` walks a `versions/<name>/main_<ver>.tex` + `sections/<name>/<ver>/*.tex` layout and writes a `src/<ver>/` tree: sections become Markdown, environments that can't be translated losslessly stay in ```` ```latex ```` blocks, and variables, the bibliography and figures come along.

<details>
<summary><b>Word output in detail</b></summary>

Drop a `.docx` into `templates/` and point `metadata.word_template` at it.

- **Styles** are extracted from the template's `styles.xml` + `theme1.xml` (Title, Heading 1–3, Normal, accent colors) and applied to the generated body. `word --extract-styles` dumps them; pass `--styles path.json`, or `metadata.word_styles`, to override after hand-tuning.
- **Body only.** The template's `<w:sectPr>` (headers, footers, margins, theme refs) is kept; the body is replaced.
- **Variables, figures and citations** resolve as in the LaTeX build. Figures are embedded as centered drawings with captions (Word prefers `png/jpg/gif/bmp`); `\cite{key}` renders as numbered `[N]` with a References section where `_bibliography` sits.
- **Math** becomes native Word equations.
- **Layout.** Table rows don't split and header rows repeat, headings keep with the next paragraph, figures keep with their captions, and equations take the body font size. `--no-layout` skips this pass.

</details>

<details>
<summary><b>The HTML viewer in detail</b></summary>

`document-sanity html` writes one `index.html` (plus copied figures):

- a left contents sidebar with scroll-spy;
- client-side KaTeX math, with the template's `\newcommand` macros registered automatically;
- clickable variables: a provenance panel slides in with the description, an inputs → command → output graph and the updated date;
- a hyperlinked bibliography rendered from `references.bib`;
- figures as `<img>`, `.html` figures (Plotly) as `<iframe>`, PDFs as `<embed>`.

It is self-contained apart from the Tailwind and KaTeX CDNs. Serve it with `python3 -m http.server` from `html/`. See [docs/html-viewer.md](docs/html-viewer.md).

</details>

## Agent skill

`init` installs a skill for coding agents into `.claude/skills/document-sanity/` (Claude Code: `/document-sanity [mode]`) and `.agents/skills/document-sanity/` (other agents). Ask for the work instead of looking up flags:

| Ask | What happens |
|---|---|
| `/document-sanity onboard` | A folder of Word files, PDFs and CSVs becomes a new document. |
| `/document-sanity iterate` | The edit → preview → build loop. |
| `/document-sanity check` | Every output built, every reference resolved, before you share. |
| `/document-sanity deploy` | GitHub Pages, after confirming the work is meant to be public. |

The other modes: `init`, `figures` (including draw.io sync), `variables`, `cite`, `word`, `version` and `import`.

- **It explains; the CLI does.** Every mode works through commands rather than having the agent write generated files.
- **It finds the project** from its sentinel files (a `pyproject.toml` that depends on document-sanity, next to `src/<doc>/manifest.yaml`).
- **It checks the version.** When `document-sanity --version` differs from the version it was written for, it trusts `--help` over its own text.
- **It ends every iteration with `preview`**, runs `check` before saying done, and asks before anything public.

The wheel carries the skill; `document-sanity skills [--force]` refreshes it after an upgrade. The repo is also a Claude Code plugin (`.claude-plugin/plugin.json`).

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

## Documentation

The conventions, in detail, under [`docs/`](./docs):

- [Figures](./docs/figures.md): one folder per figure, per-target format choice, whitespace cropping.
- [draw.io figures](./docs/drawio-figures.md): composed figures whose source assets re-import on demand.
- [References & labels](./docs/references-and-labels.md): `fig:` / `tab:` / `eq:` prefixes drive numbering.
- [Preview blocks](./docs/preview-blocks.md): readable stand-ins for ```` ```latex ```` blocks on GitHub.
- [Variables & provenance](./docs/variables-and-provenance.md): `{{VAR:fmt}}` and the provenance panel.
- [HTML viewer](./docs/html-viewer.md) and the [multi-plot standard](./docs/html-multi-plot-standard.md).
- [Bibliography](./docs/bibliography.md) and [Word](./docs/word.md).

## Install the tool directly

For local development on the tool itself:

```bash
git clone https://github.com/yakaboskic/document-sanity
cd document-sanity
uv sync
uv run document-sanity --help
uv run pytest
```

To iterate on the tool against a real project, clone [`document-sanity-template`](https://github.com/yakaboskic/document-sanity-template) alongside this repo and point its dependency at the local checkout:

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

## Lineage

document-sanity grew out of [meta-sanity](https://github.com/yakaboskic/meta-sanity), which expands one YAML file into the meta files a research pipeline needs. The same idea (declare it once, generate the rest) applied to papers. The Word output started as [word-builder](https://github.com/yakaboskic/word-builder), now ported here as the `word` command.

---

<sub>Part of <a href="https://sanitism.dev">Sanitism</a>. Also in the family: <a href="https://github.com/yakaboskic/presentation-sanity">presentation-sanity</a> for talks. MIT licensed.</sub>
