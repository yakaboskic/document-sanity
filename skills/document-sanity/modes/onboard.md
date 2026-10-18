# onboard: a heap of sources → a new document

The user hands you source material (Word, markdown, PDF, CSV, loose figures,
in `./inputs/`, a zip, a download). Goal: a new `src/<doc>/` with a manifest,
docs, figures, tables and references that builds cleanly on every target.

For a LaTeX project, use `import` mode instead.

## 1. Pick a starter and a name

- **Manuscript-shaped** (paper, journal article, technical report with
  abstract / methods / results): start from `src/manuscript/`. Auto-rendered
  title block; LaTeX numbers the sections.
- **Proposal-shaped** (SBIR/STTR, NIH/NSF, whitepaper, hand-numbered
  "1.0 Introduction" headings): start from `src/proposal/`.
  `metadata.render: false`, `template: proposal`, numbers written in the
  headings.

Don't overwrite either starter. Make a new folder from the closer one:

```bash
uv run document-sanity new-version --source proposal --name nih-r01-2026
```

Then clear the demo content in `src/<doc>/docs/`, `figures/`, `tables/` and
`references.bib`. Keep `manifest.yaml` as the skeleton you'll edit. Ask
before deleting a starter the user might still want.

## 2. Word inputs (`.docx`) → markdown + media

document-sanity doesn't read Word. Use **pandoc** (ask the user to install it
if it's missing: `brew install pandoc`):

```bash
mkdir -p inputs/extracted
pandoc inputs/source.docx -t gfm --extract-media=inputs/extracted/media \
  -o inputs/extracted/source.md
```

`-t gfm` gives pipe tables and predictable headings. `--extract-media` writes
every embedded image out and rewrites the references. A table that comes
through as raw HTML is a signal: simplify it, rewrite it as a pipe table, or
promote it to a CSV (step 5). Keep the extracted files as scratch in
`inputs/extracted/`. Never edit them in place as if they were the document.

PDFs: extract the text (`pdftotext -layout`) and treat it as a rough draft;
ask for the original Word or LaTeX if layout matters.

## 3. Plan the sections

Read the extracted markdown end to end. Map the logical sections onto files:

- manuscript-shaped: one file per section, named by content
  (`introduction.md`, `methods.md`, …);
- proposal-shaped: a numeric prefix so disk order is reading order
  (`1_introduction.md`, `2_aims.md`, …).

List them in order under `sections:`. `_bibliography` is a pseudo-section
where the reference list goes, `_toc` one for `\tableofcontents`. Don't
hand-number headings in a manuscript-shaped document: LaTeX numbers them
already ("1 1. Introduction").

## 4. Figures

Move each image into `src/<doc>/figures/<id>/<id>.<ext>`, named by what it
shows, and register it. See `figures` mode for the layout, the formats each
target prefers, and draw.io compositions.

## 5. Tables

- **Small, presentation-only**: a markdown pipe table in the doc.
- **Data** (an analysis output, regenerated, or wider than 4–5 columns): a
  file in `src/<doc>/tables/` plus a `tables:` entry, referenced as
  `{{tab:<id>}}`. See `variables` mode for the entry and its provenance.
- **Layouts that don't flatten** (multi-row headers): a ```latex block with
  `\begin{tabular}`, optionally from a `format: latex` file.

## 6. Numbers → variables

Scan the prose for numbers derived from data (sample sizes, p-values, R²,
accuracies, budgets) and promote each to a variable, with provenance that
points at the source document or the analysis that produced it (`variables`
mode). Ask for the source when it isn't in the material. Don't invent one.

## 7. References

- `\cite{key}` already in the source: keep it; add the entry to
  `references.bib`.
- Numbered `[1]` or author-year `(Smith 2024)`: replace with `\cite{key}` and
  transcribe the source's reference list into `references.bib`.

Never fabricate an entry. Missing details: ask for the paper or DOI (`cite`
mode).

## 8. The look (Word)

If the input `.docx` has the design the user wants, extract its styles and
optionally adopt it as the Word template (`word` mode).

## 9. The manifest

By now `manifest.yaml` is mostly written: `metadata` (title, authors,
affiliations, abstract, keywords, `template`, `word_template`,
`word_styles`, `html_styles`, `render`), `sections`, `variables`, `figures`,
`tables`. Set `metadata.notice` if the material carries a restriction or
distribution statement (CUI, proprietary, export-controlled). It prints on
every output, and keeps the document off a public site.

## 10. First build

```bash
uv run document-sanity preview -V <doc>     # mandatory after every change
uv run document-sanity check <doc>          # LaTeX + PDF, refs, HTML, Word
```

Common first-build failures:

- an unescaped `$` in prose ("Missing $ inserted"): write `\$250`;
- `\textsuperscript{2}` from LaTeX-native sources: write `R<sup>2</sup>`;
- a `|` inside a table cell: `\|`;
- a figure that doesn't show: the folder name and file stem must both be the
  figure id (`figures/overview/overview.png`);
- a Unicode symbol pdflatex doesn't know: add it to the
  `\DeclareUnicodeCharacter` block in `templates/<name>.tex` (ask first; it's
  shared), or build with `--compiler lualatex`.

Then hand over to `iterate` mode.
