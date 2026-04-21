# HTML viewer

`latex-builder html` emits a single self-contained `index.html` (plus
`figures/` copied alongside) with an interactive reading experience:
TOC sidebar, client-side math, clickable variables with a provenance
panel, expand-to-modal on figures, scroll-spy on the nav, hyperlinked
bibliography.

Only external dependencies are Tailwind Play CDN and KaTeX CDN — drop
the `html/` folder onto any static host (GitHub Pages, S3, your local
`python3 -m http.server`) and it works.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│                          Paper title                         │
│                     Authors · Affiliations                    │
├────────────────────┬────────────────────┬─────────────────────┤
│                    │                    │                     │
│   CONTENTS         │   Abstract         │  Provenance         │
│   (sticky TOC)     │                    │  (slide-in panel,   │
│                    │   # Section        │   shows when a      │
│   - heading 1      │   ...              │   variable is       │
│   - heading 1.1    │   ![fig](path)     │   clicked)          │
│   - heading 2      │   Table 3          │                     │
│   ...              │   ...              │                     │
│                    │                    │                     │
│                    │   ## Discussion    │                     │
│                    │   ...              │                     │
└────────────────────┴────────────────────┴─────────────────────┘
```

Grid columns: `240px · minmax(0, 820px) · 0px` in the default state,
transition to `240px · minmax(0, 1fr) · 380px` when the provenance
panel opens. `justify-content: center` keeps the content centered when
the panel is closed so nothing shifts laterally just from being on the
page.

Responsive collapse under 900px: single-column layout, TOC loses
stickiness, provenance panel is hidden entirely.

## Paper title vs section headings

The paper title is a plain `<div class="paper-title">` — **not** an
`<h1>`. That keeps it out of the TOC (which scans `<h1>`/`<h2>`/`<h3>`/
`<h4>` in the `<main>` content) and lets it be styled independently:
centered, 2.25rem, tight letter-spacing. Section headings are
left-aligned with slightly smaller sizes (h1: 1.875rem, h2: 1.5rem, h3:
1.25rem, h4: 1.05rem).

All heading CSS is qualified with `.content h1` / `.content h2` etc.
because Tailwind Play CDN injects its Preflight reset dynamically and
bare element selectors lose to the class-qualified rules in the order
of the cascade.

## TOC sidebar

Auto-built from every `<h1>` / `<h2>` / `<h3>` / `<h4>` in the rendered
content. Indentation reflects heading level. Scroll-spy uses an
`IntersectionObserver` with a 40%/55% root margin so the active link
highlights once the heading is within the reader's focal zone, not
right at the top/bottom of the viewport.

If a heading has a trailing `<!-- \label{sec:something} -->` HTML
comment in the source, that label becomes the heading's `id` instead
of the slugified text. So `\ref{sec:something}` links directly.

## Variables with provenance

See [variables-and-provenance.md](./variables-and-provenance.md) for the
manifest schema. On the page side, every `{{VAR}}` becomes:

```html
<span class="var var-has-provenance"
      data-var="…" data-fmt="…"
      data-provenance='{"description":…}'>formatted value</span>
```

Click handler on `document.body` listens for `.var.var-has-provenance`
clicks. Parses the JSON, renders the panel:

```
Provenance
──────────────────────────────
Description of what this is.   ← muted paragraph

┌─────── inputs ───────┐
│ data/raw.parquet     │
│ data/manual.tsv      │
└──────────────────────┘
           ↓
┌───── command ──────┐
│ python scripts/... │   ← monospace
└────────────────────┘
           ↓
┌─────── variable ───────┐
│ NUM_SAMPLES:,  1,000   │   ← green accent
└────────────────────────┘

                                       updated 2026-03-28
```

Panel close: ✕ button, Escape key, or click outside the panel.
Re-click the same variable → close. Click a different variable → panel
re-renders for the new one (no close-then-open).

Grid transition uses Material ease-in-out
(`cubic-bezier(0.4, 0, 0.2, 1)`, 0.45s for the column, 0.35s for the
panel fade), with a 100ms delay on the panel entry so the columns widen
first and the content eases in on top of the motion.

## Figure expand-to-modal

Hover any figure (raster, interactive, PDF) and a small expand icon
appears in the top-right corner. Click opens a modal:

- `95vw × 92vh` max (capped at 1600×1100).
- Header with the caption + close button.
- Body mirrors the figure's content at viewport scale: `<iframe>`
  for interactive HTML, `<img>` for raster, `<embed>` for PDF.
- Dismissable via ✕, backdrop click, or Escape.
- Body scroll locked while the modal is open.

## Math rendering

KaTeX + `auto-render` loaded from jsdelivr. Delimiters:

| Markdown writes | KaTeX renders as |
|---|---|
| `$…$` | inline math |
| `$$…$$` | display math |
| `\[…\]` | display math |
| `\(…\)` | inline math |

Template `\newcommand{\foo}{body}` macros (e.g. `\prob` →
`\text{Pr}`) are parsed from `templates/<name>.tex` and registered with
KaTeX's `macros` option so `$\prob(x)$` renders without pre-expansion.

Scientific notation inside math is rewritten at build time:
`8.65e-09` → `8.65 \times 10^{-9}`. See
[variables-and-provenance.md](./variables-and-provenance.md#math-mode-rewriting)
for details.

## Figures

See [figures.md](./figures.md) for how the right artifact gets chosen
per target. In the HTML viewer specifically:

- `.png` / `.jpg` → `<figure><img></figure>` with `<figcaption>`.
- `.html` → `<iframe>` with auto-resize via postMessage
  ([html-multi-plot-standard.md](./html-multi-plot-standard.md) covers
  Plotly-specific handling).
- `.pdf` → `<embed>` with PDF plugin fallback.
- Raster figures get whitespace-cropped on copy into `html/figures/`.

## Bibliography

See [bibliography.md](./bibliography.md). Short version: `references.bib`
next to the `src/<ver>/manifest.yaml` is parsed by a small BibTeX
reader; cited keys get numbered in first-appearance order; the final
`<section id="references">` renders each as a numbered `<li>` with a DOI
link when available.

## Tables

From markdown pipe-tables in the `.md` (auto-converted to
`<table class="md-table">` with zebra-striped rows, muted header
background, border-collapse layout) or from `_convert_table` in
`md2html.py` when we render preview-block tables.

## Known oddities

- **Table/Figure word doubling** — see
  [references-and-labels.md](./references-and-labels.md#undefined-labels).
  `Table \ref{tab:x}` renders as "Table Table 4" in HTML because the
  resolver emits the full "Table N" for the ref.
- **Plotly "Save As" exports** — if the HTML loads `plotly.js` from a
  relative `_files/` path, normalization rewrites it to the CDN so
  interactivity works.
- **Cross-origin file://** — Chrome treats each `file://` path as a
  separate origin, so contentDocument reads on iframes fail. All
  interactive sizing uses `postMessage` instead.

## Related code

| File | Responsibility |
|---|---|
| `src/latex_builder/html_builder.py::build_html` | End-to-end orchestration. |
| `src/latex_builder/html_builder.py::INDEX_TEMPLATE` | The single-file HTML page template (HTML + embedded CSS + JS). |
| `src/latex_builder/md2html.py::md_to_html` | Markdown → HTML fragment converter. |
| `src/latex_builder/plotly_html.py` | Plotly HTML normalizer (tabs + postMessage). |
| `src/latex_builder/bib.py` | BibTeX parser + citation rendering. |
| `src/latex_builder/cli.py::cmd_html` | CLI entry point. |
