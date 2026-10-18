# Word (.docx) output

`document-sanity word` renders the same markdown sources that feed PDF and
HTML into a Microsoft Word document. The template contributes headers,
footers, theme, page layout, and typography; your `docs/*.md` contributes
the body.

## Template discovery

In order, the builder picks:

1. `--template <path>` if passed on the CLI.
2. `templates/<name>.docx` where `<name>` is `metadata.word_template` in
   `manifest.yaml`, falling back to `metadata.template`.
3. The only `.docx` in `templates/` if exactly one exists.

If nothing matches the build exits with a clear error. Add `word_template`
to the manifest so intent is explicit:

```yaml
metadata:
  title: "My Paper"
  template: nature              # used for LaTeX builds
  word_template: corporate-memo # used for Word builds
```

## Style extraction

The builder reads `word/styles.xml` and `word/theme/theme1.xml` from the
template's zip. It resolves the `basedOn` chain and `docDefaults` to derive:

- `colors.primary / secondary / accent` from theme `accent1–3`
- `colors.heading1–3` from the matching paragraph styles
- `fonts.heading / body` from Title / Heading 1 / Normal
- `fontSizes.title / h1 / h2 / h3 / body` from the same styles
- Paragraph and heading spacing defaults

The resulting JSON tree matches
[word-builder](https://github.com/yakaboskic/word-builder)'s `StylesConfig`
byte-for-byte, so styles extracted by either tool are interchangeable.

Dump the extracted styles to disk to hand-tune before a build:

```bash
document-sanity word --extract-styles
document-sanity word --extract-styles -t templates/corporate.docx -o /tmp/corp.json
```

Then re-apply with `--styles /tmp/corp.json`.

## Body preservation

Only the template's `<w:sectPr>` (headers, footers, margins, theme refs) is
kept from the original body — everything else inside `<w:body>` is replaced
with generated content. Templates should be "shells" without body content
you want preserved.

`word/numbering.xml` is rewritten so bullet (`numId=1`) and ordered
(`numId=2`) lists work consistently across templates. If the template's
headers/footers reference other `numId` values, they may lose list
formatting — rare, and fixable by restoring the original `numbering.xml`
by hand.

## Figures

Inline figures are embedded as real `<w:drawing>` elements with
`/word/media/imageN.<ext>` entries and matching relationships in
`word/_rels/document.xml.rels`.

Two authoring patterns are supported:

```markdown
![Caption text](figures/overview.png)          <!-- inline markdown -->

```latex
\begin{figure}[h!]
    \centering
    {{fig:overview}}                           <!-- or \includegraphics{...} -->
    \caption{Caption text.}
    \label{fig:overview}
\end{figure}
```
```

The `'word'` build target prefers `png / jpg / jpeg / gif / bmp` — DOCX has
no native PDF or SVG support. If your figures are authored as `.pdf`,
supply a sibling `.png` (recommended layout is
[`figures/<id>/<id>.pdf`](./figures.md) + `figures/<id>/<id>.png`) so all
three targets pick the right artifact.

Image dimensions are read via Pillow; each figure is scaled to fit 6" wide
while preserving aspect ratio.

## Variables

`{{VAR}}` and `{{VAR:fmt}}` tokens resolve through the same
[`VariableProcessor`](./variables-and-provenance.md) used by the LaTeX and
HTML pipelines, with `target="word"`. Provenance isn't surfaced visually in
the .docx (Word has no equivalent of the HTML side panel), but the values
substitute identically.

## Citations and bibliography

`\cite{key}` in the source renders as a numbered `[N]` in the Word output.
First appearance assigns a number; later citations of the same key reuse
it. A `References` section is rendered at the end (or wherever
`_bibliography` appears in `manifest.sections`) using the same
`references.bib` as the LaTeX build.

Entries render with:

- **Author list** in bold (`J. Smith, A. Doe`)
- Title plain
- *Venue* italic, with volume/number/pages/year trailing
- DOI / URL as the last run (colored like a link)

Multi-key cites (`\cite{smith2024,jones2025}`) render as `[1, 2]`.

## Layout

Every build ends with a pagination pass over the finished `.docx`
(`docx_layout.py`):

- table rows don't split across pages, and each table's first row repeats
  as a header row on every page it spans;
- headings keep with the paragraph after them and don't split;
- a figure's image keeps with its caption (a `Caption`-styled paragraph or
  one starting `Figure N:`), and the caption doesn't split;
- equations take their paragraph's font size: `fontSizes.body` from the
  resolved styles, or the size the paragraph sets itself (captions,
  headings). Word would otherwise draw them at its own default.

Only `word/document.xml` changes. `document-sanity word --no-layout`
skips the pass. `check` and `site` build the same laid-out file.

Projects made from an older template ship `scripts/finalize_word_layout.py`
and run it from `make word`. The pass is idempotent, so running the script
again changes nothing; delete it and its line in the Makefile's `word`
target. `check -v` notes it when it's there.

## Caveats

- **Blockquotes** render as italic paragraphs, not shaded callout boxes.
- **Equations** (`$…$`, `$$…$$`, and `equation`/`align`/`gather`
  environments in `latex` blocks) become native Word equations through
  pandoc. Without `pandoc` on the PATH, or for a snippet it can't convert,
  the LaTeX source is written as centered italic monospace text instead.
  Template macros that take arguments don't expand.
- **`latex` blocks** render from their [preview block](./preview-blocks.md):
  a table there becomes a real Word table. A `table` environment with no
  preview renders as a caption-only placeholder, so run `preview` first.
  Previews flatten what markdown can't hold (merged header cells, subfigure
  panels). Markdown pipe tables and `{{tab:…}}` tables are real Word tables.
- **Inline `code` spans** use the template's `Code` character style; if the
  template doesn't define one, they render in the body font.
