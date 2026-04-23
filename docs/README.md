# `document-sanity` documentation

Opinionated conventions and pipeline details. The top-level
[README](../README.md) covers the CLI and paper-repo setup; these docs go
deeper into the design decisions the tool makes on your behalf.

| Topic | What's opinionated |
|---|---|
| [Figures](./figures.md) | Per-figure subdirectories (`figures/<id>/<id>.{pdf,png,html,...}`), target-specific artifact resolution (PDF prefers `.pdf`, HTML prefers `.html`, Word prefers `.png`/`.jpg`), automatic whitespace cropping on raster figures during build. |
| [Word output](./word.md) | `.docx` template discovery, style extraction from `styles.xml` + `theme1.xml`, body-preserving splice that keeps headers/footers/theme intact, inline figure embedding, `\cite{}` → `[N]` with a References section. |
| [References & labels](./references-and-labels.md) | Label prefix convention (`fig:`, `tab:`, `eq:`, `sec:`, `app:`, `alg:`) drives automatic numbering and "Figure 3" / "Table 2" hyperlink text in the HTML viewer. |
| [Preview blocks](./preview-blocks.md) | `<!-- document-sanity:preview:begin hash=… -->` auto-generated markdown-renderable approximations of ```latex figures / tables / math, keyed by a hash of the source block. |
| [Variables & provenance](./variables-and-provenance.md) | `{{VAR:fmt}}` token syntax, the `provenance:` block that powers the HTML viewer's side panel, scientific-notation rewriting inside math. |
| [HTML viewer](./html-viewer.md) | Layout (paper title + TOC + content + provenance panel), KaTeX setup with template-macro registration, figure expand-to-modal dialog, scroll-spy. |
| [HTML multi-plot standard](./html-multi-plot-standard.md) | How interactive Plotly exports get normalized into a tabbed iframe layout with CDN fallback and parent-side postMessage resizing. |
| [Bibliography](./bibliography.md) | Minimal BibTeX parser, first-appearance citation numbering, `<li>` rendering contract. |
