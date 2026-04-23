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

## Caveats

- **Blockquotes** render as inline "Note:" text, not shaded callout boxes.
- **Equations** in `latex` blocks render as centered italic monospace — no
  OOXML math conversion yet.
- **Tables** inside `latex` blocks render as a placeholder; markdown pipe
  tables render as real Word tables.
- **Inline `code` spans** don't switch to monospace (Word doesn't inherit
  font changes cleanly across runs in our current emit).
