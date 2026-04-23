#!/usr/bin/env python3
"""
Normalize Plotly offline HTML exports into a tabbed, iframe-friendly layout.

Plotly's offline `fig.write_html()` emits one `<div class="plotly-graph-div">`
per figure, each styled `height:100%; width:100%`. When there are multiple
plots in one file, stacking them in an iframe is awkward: either the plots
fight each other for the iframe's vertical space or, with autosize, they
create a height feedback loop with any parent-side resizer.

This module rewrites a Plotly HTML file into the "document-sanity standard":

    <div class="lb-plotly-tabs">
      <nav class="lb-tab-bar">
        <button class="lb-tab active" data-tab="0">Plot 1</button>
        <button class="lb-tab"        data-tab="1">Plot 2</button>
        ...
      </nav>
      <div class="lb-tab-panels">
        <div class="lb-tab-panel active" data-panel="0"> <!-- plot div --> </div>
        <div class="lb-tab-panel"        data-panel="1"> <!-- plot div --> </div>
        ...
      </div>
    </div>

Each plot is pinned to a fixed pixel height so the iframe's total content
height is stable (tab bar + one visible panel). A tab switcher script shows
one panel at a time and calls `Plotly.Plots.resize()` on the newly-visible
plot. The top-of-file resize-reporter posts the stable height to the parent
via postMessage, closing the loop.

Files we can't parse or that contain 0-1 Plotly plots fall back to the raw
source (with just the resize-reporter prepended so single-plot embeds still
auto-size).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


MARKER = '<!-- document-sanity:plotly-normalized -->'
REPORTER_MARKER = '<!-- document-sanity:iframe-resize-reporter -->'

# Height reserved per plot inside a tab panel. A fixed value breaks the
# feedback loop between Plotly's `height:100%` and the iframe's own height.
# 640 gives Plotly ~80px of axis label / modebar space below the plot area
# without clipping.
PLOT_H_PX = 640

# CDN fallback for when the source HTML loads plotly.js from a relative path
# (common for "Save As" exports whose sibling _files/ dir didn't come along).
PLOTLY_CDN = 'https://cdn.plot.ly/plotly-3.4.0.min.js'


_PLOT_DIV_OPEN_RE = re.compile(
    r'<div\b[^>]*\bclass="[^"]*\bplotly-graph-div\b[^"]*"[^>]*>',
    re.IGNORECASE,
)
_PLOT_DIV_ID_RE = re.compile(r'\bid="([^"]+)"', re.IGNORECASE)
_DIV_TAG_RE = re.compile(r'<(/?)div\b[^>]*>', re.IGNORECASE)


def _extract_balanced_div(text: str, start: int) -> tuple[int, str]:
    """Given text[start] begins '<div ...>', return (end_pos_exclusive, html)
    covering the full <div>...</div> including any nested <div>s. Falls back
    to the opening tag alone if no matching close is found."""
    open_tag_end = text.find('>', start)
    if open_tag_end < 0:
        return start, ''
    depth = 1
    i = open_tag_end + 1
    for m in _DIV_TAG_RE.finditer(text, i):
        is_close = m.group(1) == '/'
        if is_close:
            depth -= 1
            if depth == 0:
                end = m.end()
                return end, text[start:end]
        else:
            depth += 1
    # Unbalanced — return everything up to </body> as a safety
    body_close = re.search(r'</body\s*>', text[start:], re.IGNORECASE)
    if body_close:
        end = start + body_close.start()
        return end, text[start:end]
    return start, ''
_TITLE_NEAR_ID_RE = re.compile(
    r'"title"\s*:\s*(?:"([^"]+)"|\{\s*"text"\s*:\s*"([^"]+)")',
)


@dataclass
class _PlotlyDiv:
    html: str           # full <div class="plotly-graph-div"> ... </div>
    plot_id: str
    title: str          # tab label


def _extract_title(text: str, plot_id: str, fallback: str) -> str:
    """Look for a title near the Plotly.newPlot("<plot_id>", ...) call."""
    # Find the Plotly.newPlot call for this id
    npat = re.compile(
        r'Plotly\.newPlot\(\s*["\']' + re.escape(plot_id) + r'["\']',
    )
    m = npat.search(text)
    if not m:
        return fallback
    # Look within ~4KB after the call for the first "title":"..." / "title":{"text":"..."}
    window = text[m.end(): m.end() + 4000]
    tm = _TITLE_NEAR_ID_RE.search(window)
    if tm:
        return (tm.group(1) or tm.group(2) or fallback).strip()
    return fallback


def _find_body(text: str) -> tuple[int, int] | None:
    body_open = re.search(r'<body\b[^>]*>', text, re.IGNORECASE)
    body_close = re.search(r'</body\s*>', text, re.IGNORECASE)
    if not body_open or not body_close:
        return None
    return (body_open.end(), body_close.start())


_STANDARD_CSS = f"""
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; }}
  .lb-plotly-tabs {{
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: #0f172a;
  }}
  .lb-tab-bar {{
    display: flex; gap: .25rem;
    padding: .5rem .5rem 0 .5rem;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
    overflow-x: auto;
  }}
  .lb-tab {{
    padding: .5rem .9rem;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    font: inherit; font-size: .85rem;
    color: #475569;
    white-space: nowrap;
    transition: color .15s, border-color .15s, background .15s;
  }}
  .lb-tab:hover {{ background: #f1f5f9; color: #0f172a; }}
  .lb-tab.active {{
    color: #0f172a;
    border-bottom-color: #2563eb;
    font-weight: 600;
  }}
  .lb-tab-panels {{ padding: .5rem; }}
  .lb-tab-panel {{ display: none; }}
  .lb-tab-panel.active {{ display: block; }}
  /* Pin each Plotly plot to a fixed height so the iframe content size is
     stable and Plotly's autosize does not create a feedback loop. */
  .lb-tab-panel .plotly-graph-div,
  .lb-tab-panel .js-plotly-plot {{
    height: {PLOT_H_PX}px !important;
    width: 100% !important;
  }}
</style>
"""

_TAB_SWITCHER_JS = """
<script>
(function(){
  var root = document.querySelector(".lb-plotly-tabs");
  if (!root) return;
  var tabs = root.querySelectorAll(".lb-tab");
  var panels = root.querySelectorAll(".lb-tab-panel");
  function activate(idx) {
    tabs.forEach(function(t){ t.classList.toggle("active", t.dataset.tab === idx); });
    panels.forEach(function(p){ p.classList.toggle("active", p.dataset.panel === idx); });
    var active = root.querySelector('.lb-tab-panel[data-panel="'+idx+'"]');
    if (!active) return;
    var plot = active.querySelector(".plotly-graph-div");
    if (plot && window.Plotly && window.Plotly.Plots && window.Plotly.Plots.resize) {
      try { window.Plotly.Plots.resize(plot); } catch(e) {}
    }
  }
  tabs.forEach(function(t){
    t.addEventListener("click", function(){ activate(t.dataset.tab); });
  });
})();
</script>
"""

_RESIZE_REPORTER_SCRIPT = """
<!-- document-sanity:iframe-resize-reporter -->
<script>
(function(){
  if (window.parent === window) return;
  var lastH = 0;
  function measure(){
    var h = Math.max(
      document.body ? document.body.scrollHeight : 0,
      document.documentElement ? document.documentElement.scrollHeight : 0
    );
    if (h && Math.abs(h - lastH) > 2) {
      lastH = h;
      window.parent.postMessage(
        {latexBuilderFigureHeight: h, url: location.href}, "*"
      );
    }
  }
  window.addEventListener("load", function(){
    measure();
    setTimeout(measure, 100);
    setTimeout(measure, 500);
    setTimeout(measure, 1500);
  });
  window.addEventListener("resize", measure);
})();
</script>
"""


def _rewrap_as_tabs(text: str, plots: list[_PlotlyDiv]) -> str:
    """Rebuild the body with a tabbed layout; leave scripts (Plotly.newPlot) in place."""
    body_bounds = _find_body(text)
    if body_bounds is None:
        return text
    body_start, body_end = body_bounds
    body = text[body_start:body_end]

    # Build tab nav + panels
    tabs_html = ['<nav class="lb-tab-bar" role="tablist">']
    panels_html = ['<div class="lb-tab-panels">']
    for i, p in enumerate(plots):
        active = ' active' if i == 0 else ''
        tabs_html.append(
            f'<button class="lb-tab{active}" type="button" '
            f'data-tab="{i}" role="tab">{_escape_attr(p.title)}</button>'
        )
        panels_html.append(
            f'<div class="lb-tab-panel{active}" data-panel="{i}" role="tabpanel">'
            f'{p.html}</div>'
        )
    tabs_html.append('</nav>')
    panels_html.append('</div>')

    tabbed_dom = ('<div class="lb-plotly-tabs" data-lb-plotly-tabs>'
                  + ''.join(tabs_html) + ''.join(panels_html) + '</div>')

    # Strip the original plot divs from the body (their `Plotly.newPlot`
    # scripts must stay, otherwise the plots won't render inside the tabs).
    new_body = body
    for p in plots:
        new_body = new_body.replace(p.html, '', 1)

    # Prepend the tabbed DOM + append scripts; preserves any residual markup.
    new_body = tabbed_dom + new_body + _TAB_SWITCHER_JS

    return text[:body_start] + new_body + text[body_end:]


def _escape_attr(s: str) -> str:
    return (s.replace('&', '&amp;').replace('"', '&quot;')
             .replace('<', '&lt;').replace('>', '&gt;'))


def _inject_before_body_close(text: str, snippet: str) -> str:
    idx = re.search(r'</body\s*>', text, re.IGNORECASE)
    if not idx:
        return text + snippet
    pos = idx.start()
    return text[:pos] + snippet + text[pos:]


def _rewrite_plotly_script_to_cdn(html: str) -> str:
    """Swap a local plotly*.min.js <script src="..."> to the CDN.

    "Save As" exports frequently point at `./<name>_files/plotly-<ver>.min.js`,
    a sibling directory that rarely makes it into the figures/ layout. If we
    detect such a script, rewrite its src to Plotly's CDN so interactivity
    works even without the sibling files."""
    pattern = re.compile(
        r'(<script\b[^>]*\bsrc=")([^"]*plotly[-.a-zA-Z0-9_]*\.min\.js)(")',
        re.IGNORECASE,
    )

    def _repl(m):
        src = m.group(2)
        # Leave http(s) sources alone — they already work.
        if src.lower().startswith(('http://', 'https://', '//')):
            return m.group(0)
        return m.group(1) + PLOTLY_CDN + m.group(3)

    return pattern.sub(_repl, html)


def normalize(html: str) -> tuple[str, int]:
    """Return (new_html, n_tabs). n_tabs == 0 means the file was untouched
    (single-plot or non-Plotly), n_tabs >= 2 means we built a tabbed layout.

    The resize-reporter script is always ensured to be present."""
    # Already processed? Bail early.
    if MARKER in html:
        return html, _count_tabs(html)

    # Always rewrite broken local plotly.js srcs to the CDN.
    html = _rewrite_plotly_script_to_cdn(html)

    # Find all plot divs (balanced match — Plotly divs may contain rendered SVG).
    plots: list[_PlotlyDiv] = []
    pos = 0
    idx = 0
    while True:
        m = _PLOT_DIV_OPEN_RE.search(html, pos)
        if not m:
            break
        end_pos, div_html = _extract_balanced_div(html, m.start())
        id_match = _PLOT_DIV_ID_RE.search(m.group(0))
        if id_match and div_html:
            plot_id = id_match.group(1)
            title = _extract_title(html, plot_id, fallback=f'Plot {idx + 1}')
            plots.append(_PlotlyDiv(html=div_html, plot_id=plot_id, title=title))
            idx += 1
        pos = end_pos if end_pos > m.end() else m.end()

    # Ensure the resize-reporter is injected regardless of tab count
    if REPORTER_MARKER not in html:
        html = _inject_before_body_close(html, _RESIZE_REPORTER_SCRIPT)

    # Also ensure we've tagged this file as normalized so we don't re-run
    html = _inject_before_body_close(html, MARKER)

    if len(plots) < 2:
        # Single-plot or unrecognized layout — leave as-is (reporter already
        # injected above). The parent's 420px fallback + scrollbar is fine.
        return html, 0

    # Inject our standard CSS in <head>, rewrap body with tabs
    head_close = re.search(r'</head\s*>', html, re.IGNORECASE)
    if head_close:
        html = html[:head_close.start()] + _STANDARD_CSS + html[head_close.start():]
    else:
        html = _STANDARD_CSS + html

    html = _rewrap_as_tabs(html, plots)
    return html, len(plots)


def _count_tabs(html: str) -> int:
    m = re.findall(r'class="lb-tab(?:\s+active)?"\s+type="button"', html)
    return len(m)
