# HTML multi-plot standard

How `document-sanity` renders interactive figures (Plotly exports, etc.) in the
HTML viewer, what layout we expect the source HTML to have, and how the
normalization pipeline rewrites it at build time.

## The problem

Plotly's `fig.write_html()` emits one `<div class="plotly-graph-div">` per
figure, each styled `height: 100%; width: 100%`. Dropping a multi-plot
export directly into an `<iframe>` has two bad failure modes:

1. **Stacked plots fight for space.** Each plot fills the iframe viewport,
   so N plots take roughly N × iframe-height — you get scrollbars or
   chopped off content.
2. **Feedback loop with autosize.** If the parent page measures the iframe's
   `scrollHeight` and grows the iframe to match, each plot's `height: 100%`
   makes its scrollHeight grow too, which the parent re-reads, etc. The
   iframe grows without bound.

Chrome's `file://` same-origin policy also blocks the parent from reading
`iframe.contentDocument` directly, ruling out cheap in-browser height
measurement.

## The standard

`document-sanity` rewrites every interactive HTML figure into a known shape
at build time. A figure becomes one of:

- **Single plot** → unchanged body layout; just a tiny resize-reporter
  script is injected so the parent iframe can size to the content.
- **Multi-plot** → the plots are rewrapped into a tab bar + stacked panels;
  only one plot is visible at a time.

Both shapes use `postMessage` to tell the parent page their natural height.

### Markup emitted for multi-plot figures

```html
<!-- The standard wrapper, identified by the class `lb-plotly-tabs`. -->
<div class="lb-plotly-tabs" data-lb-plotly-tabs>
  <nav class="lb-tab-bar" role="tablist">
    <button class="lb-tab active" type="button" data-tab="0" role="tab">
      Plot 1
    </button>
    <button class="lb-tab" type="button" data-tab="1" role="tab">
      Avg Ratio
    </button>
    <button class="lb-tab" type="button" data-tab="2" role="tab">
      Plot 3
    </button>
  </nav>
  <div class="lb-tab-panels">
    <div class="lb-tab-panel active" data-panel="0" role="tabpanel">
      <!-- original <div class="plotly-graph-div" id="…">…</div> -->
    </div>
    <div class="lb-tab-panel" data-panel="1" role="tabpanel">
      <!-- next plotly-graph-div -->
    </div>
    <div class="lb-tab-panel" data-panel="2" role="tabpanel">
      <!-- last plotly-graph-div -->
    </div>
  </div>
</div>

<!-- Original Plotly.newPlot() scripts follow, unchanged — they reference
     the plot divs by id, which are preserved. -->
```

### Accompanying CSS (prepended to the file's `<head>`)

- Pin each plot to a fixed pixel height so the iframe has a stable natural
  size that doesn't feed back on itself:

  ```css
  .lb-tab-panel .plotly-graph-div,
  .lb-tab-panel .js-plotly-plot {
    height: 540px !important;
    width: 100%  !important;
  }
  ```

  The value is `plotly_html.PLOT_H_PX` — change it once if you want taller
  or shorter plots across the whole project.

- Reset `html`/`body` margins so the iframe content flushes to its edges.

- Tab-bar styling uses a neutral slate palette (`#f8fafc` / `#e2e8f0` /
  `#2563eb` for active) and picks up the host page's `ui-sans-serif` font
  stack — no external CSS dependencies.

### Accompanying JS (appended before `</body>`)

Two small vanilla scripts, no framework:

- **Tab switcher.** Clicking `.lb-tab[data-tab="N"]` toggles the matching
  `.lb-tab-panel[data-panel="N"]` to visible and calls
  `Plotly.Plots.resize(plotDiv)` so the newly-shown plot snaps to its
  container (Plotly caches layout dimensions and needs a nudge when it
  was previously `display: none`).

- **Resize reporter.** Measures `body.scrollHeight` on `load`, on `resize`,
  and at 100 / 500 / 1500 ms timers (Plotly mounts SVG asynchronously), and
  posts the result to the parent via
  `window.parent.postMessage({latexBuilderFigureHeight: h, url: …}, "*")`.
  A 2-px hysteresis threshold prevents message storms.

### Parent-side contract (in `out/<ver>/html/index.html`)

```js
window.addEventListener("message", (e) => {
  if (!e || !e.data || typeof e.data.latexBuilderFigureHeight !== "number")
    return;
  const h = e.data.latexBuilderFigureHeight;
  const cap = Math.round(window.innerHeight * 0.9);  // safety cap
  const clamped = Math.min(h, cap);
  document.querySelectorAll("iframe.interactive-fig").forEach(iframe => {
    if (iframe.contentWindow === e.source) {
      iframe.style.height = clamped + "px";
    }
  });
});
```

The iframe defaults to `height: 420px` until a message arrives; the
`transition: height .2s ease-out` rule smooths the resize. Height is
clamped to `90vh` so a rogue figure can't eat the whole viewport.

## Marker

Every normalized file gets a single HTML comment so we can detect "already
processed" and skip on rebuilds:

```html
<!-- document-sanity:plotly-normalized -->
```

The resize-reporter has its own marker (`<!-- document-sanity:iframe-resize-reporter -->`)
because single-plot files get it even when no tab rewriting happens.

## When normalization fires

The pipeline is:

```
src/<ver>/figures/<id>/<id>.html        # author's Plotly export (or similar)
        │
        │  build.py::copy_figures →  crop + flatten
        ▼
out/<ver>/html/figures/<id>.html        # copy in html/ build only
        │
        │  html_builder._normalize_plotly_html_figures()
        ▼
out/<ver>/html/figures/<id>.html        # normalized in-place, idempotent
```

Only `document-sanity html` runs normalization. `document-sanity build` (PDF)
and `document-sanity preview` leave the source HTML alone — neither
consumes interactive figures.

## Plotly.js source rewriting

Some source HTML files (especially browser "Save As" exports) load
`plotly.js` from a relative path like `./<name>_files/plotly-3.4.0.min.js`.
That sibling directory usually doesn't come along with the HTML file,
leaving the embed non-interactive.

The normalizer detects any `<script src="…plotly*.min.js">` whose `src` is
not already an `http(s)`/`//` URL and rewrites it to `PLOTLY_CDN` in
`plotly_html.py` (currently `https://cdn.plot.ly/plotly-3.4.0.min.js`).
CDN requests are same-version-pinned rather than `plotly-latest` so the
figure's JSON config stays compatible with the Plotly API it was authored
against.

## Detection heuristics

`plotly_html.normalize(html)` classifies an HTML figure by counting
`<div class="plotly-graph-div">` elements (balanced-brace extraction, so
rendered SVG inside the div doesn't confuse the parser):

| Plot divs found | Action |
|---|---|
| 0 | Not a Plotly figure — inject resize-reporter only, leave the body unchanged. Parent falls back to the 420 px initial height with scrollbar for overflow. |
| 1 | Single plot — inject resize-reporter, leave body unchanged. The pinned height rule still applies via the CSS style block we prepend. |
| ≥ 2 | Multi-plot — rewrap body into the tabbed layout described above. |

Titles for each tab are sourced from the accompanying `Plotly.newPlot(...)`
call's layout: we regex for `"title":"<str>"` or `"title":{"text":"<str>"}`
within ~4 KB after the call. If nothing matches, tabs fall back to
`"Plot 1"`, `"Plot 2"`, … .

## Authoring guidelines

- **One-off interactive figure**: export with `fig.write_html("out.html")`.
  `document-sanity html` will pin it to a reasonable height, wire up the
  resize-reporter, and the HTML viewer's iframe will auto-size. No other
  action required.
- **Multi-panel figure**: build a Python figure with sub-plots, or write
  multiple figures to one HTML with `with open("out.html", "w") as f:
  ...write_html(file=f, include_plotlyjs="cdn", full_html=False)`.
  Give each figure a layout title so the auto-extracted tab labels are
  meaningful rather than `Plot 1 / Plot 2 / …`:
  ```python
  fig.update_layout(title="My Figure Label")
  ```
- **Override the per-plot height**: edit `PLOT_H_PX` in
  `src/document_sanity/plotly_html.py` (project-wide change). A per-figure
  override through the manifest is a future improvement if demand appears.
- **Non-Plotly HTML**: the tool doesn't need to understand the content.
  Any file with 0 Plotly divs passes through with just the resize-reporter
  added. If your custom HTML renders at a predictable height, it'll be
  displayed fine.

## Integration points

| File | Role |
|---|---|
| `src/document_sanity/plotly_html.py` | `normalize(html) -> (new_html, n_tabs)`, plus the CSS/JS snippets and the balanced-brace div extractor. |
| `src/document_sanity/html_builder.py::_normalize_plotly_html_figures` | Walks every `*.html` under `out/<ver>/html/figures/` and applies `normalize`. Idempotent. |
| `src/document_sanity/md2html.py::_img` (under `figure_preview`) | Emits `<iframe class="interactive-fig" scrolling="no" frameborder="0">` when an image src ends in `.html` / `.htm`. |
| `INDEX_TEMPLATE` in `html_builder.py` | Provides the parent-side `postMessage` listener and the fallback iframe height. |

## Troubleshooting

- **Tabs don't appear after switching.** Check the console for CSP warnings
  blocking the inline `<script>` — the build emits plain-text scripts; any
  restrictive CSP at the hosting layer will break the tab switcher.
- **Height stays at 420 px.** The resize-reporter didn't run. Common causes:
  Plotly plot crashed (check iframe console), the injected script got
  stripped by a naive HTML post-processor, or the parent page's `message`
  listener didn't get registered. Rebuild with `--verbose` to see which
  files the normalizer touched.
- **Plot looks squished when a tab is first selected.** Plotly needs a
  resize nudge after `display: none → block`. The switcher calls
  `Plotly.Plots.resize()` for this; if it fails check that the injected
  script runs after `plotly.js` is loaded (the original `Plotly.newPlot`
  calls must still appear later in the body).

## Related

- [`docs/pyproject-template.md`](./pyproject-template.md) (not present yet)
  — planned write-up of the paper-repo-consumes-tool `pyproject.toml`
  pattern that's currently documented only in the top-level README.
