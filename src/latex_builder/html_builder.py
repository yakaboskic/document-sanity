#!/usr/bin/env python3
"""
Build an interactive static HTML page from the manuscript sources.

Reads the same inputs as `build` (manifest.yaml + docs/*.md + figures/, etc.)
and emits:

    out/<version>/html/
        index.html      # single-file viewer
        figures/...     # copied verbatim so <img>/<iframe> paths resolve

The generated page is entirely self-contained except for three CDN pulls
(Tailwind Play, KaTeX, and a tiny popover script) — open it in any browser
or serve with `python -m http.server` from the html/ dir.

Highlights:
- Variables are wrapped in <span class="var" data-provenance='{...}'> so
  clicking a value pops up its source / command / description / updated date.
- Figures with .html extensions render as <iframe> (interactive plotly etc.).
- Math renders client-side via KaTeX using macros pulled from the template.
- Tables render from the preview blocks (already markdown-tables by that point).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from .manifest import Manifest
from .preview import parse_macros
from .variable_processor import VariableProcessor
from .md2html import md_to_html
from .bib import load_bib, render_entry_html, BibEntry


def _compute_figures_copy_plan(src_dir: Path, html_dir: Path) -> list[tuple[Path, Path]]:
    """Pairs of (source_fig, dest_fig) to copy alongside the HTML output."""
    src_figs = src_dir / 'figures'
    if not src_figs.exists():
        return []
    dest_figs = html_dir / 'figures'
    pairs = []
    for f in src_figs.rglob('*'):
        if f.is_file():
            rel = f.relative_to(src_figs)
            pairs.append((f, dest_figs / rel))
    return pairs


def _build_resolve_variable(processor: VariableProcessor, manifest: Manifest):
    """Return a (name, fmt) -> (display, provenance, is_defined) callable."""
    var_entries = manifest.variables

    def resolve(name: str, fmt: Optional[str]):
        entry = var_entries.get(name)
        if entry is None:
            return (processor.placeholder, None, False)
        if entry.value is None:
            display = processor.placeholder
            is_defined = False
        else:
            try:
                display = processor.format_value(entry.value, fmt)
            except Exception:
                display = str(entry.value)
            is_defined = True
        provenance = None
        if entry.provenance:
            p = entry.provenance
            provenance = {
                'source': p.source,
                'data': p.data,
                'command': p.command,
                'description': p.description,
                'updated': p.updated,
            }
            # Drop empty keys to keep the JSON attribute tidy
            provenance = {k: v for k, v in provenance.items() if v}
        return (display, provenance, is_defined)

    return resolve


def _render_authors_html(manifest: Manifest) -> str:
    meta = manifest.metadata
    if not meta.authors:
        return ''
    parts = []
    for a in meta.authors:
        sup = ''
        if a.affiliations:
            sup = '<sup>' + ','.join(str(x) for x in a.affiliations) + '</sup>'
        parts.append(f'<span class="author">{a.name}{sup}</span>')
    return '<div class="authors">' + ' '.join(parts) + '</div>'


def _render_affiliations_html(manifest: Manifest) -> str:
    aff = manifest.metadata.affiliations
    if not aff:
        return ''
    items = []
    for num, info in sorted(aff.items()):
        if isinstance(info, dict):
            parts = [info.get('department'), info.get('institution'), info.get('address')]
            text = ', '.join(p for p in parts if p)
        else:
            text = str(info)
        items.append(f'<li><sup>{num}</sup> {text}</li>')
    return '<ol class="affiliations">' + ''.join(items) + '</ol>'


class CitationCollector:
    """Assigns numbers to bib keys in first-appearance order during rendering."""

    def __init__(self, bib_entries: dict[str, BibEntry]):
        self.bib_entries = bib_entries
        self.order: list[str] = []  # keys in the order they were first seen
        self._numbers: dict[str, int] = {}

    def resolve(self, key: str) -> tuple:
        """(number_int_or_None, href_str_or_None) for a cite key."""
        # Auto-number keys, even if missing from the bib (renders as '?')
        if key not in self._numbers and key in self.bib_entries:
            self._numbers[key] = len(self.order) + 1
            self.order.append(key)
        if key in self._numbers:
            return (self._numbers[key], f'#ref-{key}')
        return (None, None)

    def render_bibliography_html(self) -> str:
        if not self.order:
            return ''
        items = []
        for i, key in enumerate(self.order, start=1):
            items.append(render_entry_html(self.bib_entries[key], i))
        return (
            '<section class="paper-section" id="references">'
            '<h1 id="references">References</h1>'
            '<ol class="references">'
            + '\n'.join(items)
            + '</ol></section>'
        )


def _render_section_html(body: str, title: Optional[str] = None) -> str:
    if title:
        return f'<section class="paper-section"><h1>{title}</h1>\n{body}\n</section>'
    return f'<section class="paper-section">{body}</section>'


_HEADING_RE = __import__('re').compile(
    r'<h([1-4])\s+id="([^"]+)">(.*?)</h\1>',
    __import__('re').DOTALL,
)


def _extract_toc(sections_html: str) -> list[dict]:
    """Walk the combined sections HTML and extract headings for the sidebar TOC."""
    toc = []
    for m in _HEADING_RE.finditer(sections_html):
        level = int(m.group(1))
        slug = m.group(2)
        raw_title = m.group(3)
        # Strip HTML tags for TOC display (keeps math readable as plain text)
        import re as _re
        clean = _re.sub(r'<[^>]+>', '', raw_title).strip()
        toc.append({'level': level, 'slug': slug, 'title': clean})
    return toc


def _render_toc_html(toc: list[dict]) -> str:
    if not toc:
        return ''
    items = []
    for entry in toc:
        indent_class = f'toc-h{entry["level"]}'
        items.append(
            f'<li class="{indent_class}">'
            f'<a href="#{entry["slug"]}">{entry["title"]}</a>'
            f'</li>'
        )
    return '<nav class="toc"><h3>Contents</h3><ul>' + ''.join(items) + '</ul></nav>'


INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"/>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<style>
  :root {{
    --border: 214 32% 91%;
    --muted: 220 14% 96%;
    --muted-foreground: 220 9% 46%;
    --accent: 221 83% 53%;
  }}
  body {{
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: #111827;
    margin: 0;
    padding: 0;
    line-height: 1.65;
  }}
  .layout {{
    display: grid;
    grid-template-columns: 240px minmax(0, 820px) 0px;
    gap: 2rem;
    justify-content: center;  /* keep columns centered regardless of panel state */
    max-width: 1480px;
    margin: 0 auto;
    padding: 2rem 1.5rem 6rem;
    /* Material-style ease-in-out for the column-width shift */
    transition: grid-template-columns .45s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .layout.prov-open {{
    grid-template-columns: 240px minmax(0, 1fr) 380px;
  }}
  @media (max-width: 900px) {{
    .layout {{ grid-template-columns: 1fr; justify-content: stretch; }}
    .toc {{ position: static !important; max-height: none !important; }}
    .layout.prov-open {{ grid-template-columns: 1fr; }}
    .provenance-panel {{ display: none !important; }}
  }}
  .toc {{
    position: sticky;
    top: 1.5rem;
    align-self: start;
    max-height: calc(100vh - 3rem);
    overflow-y: auto;
    font-size: .85rem;
    padding-right: .5rem;
    border-right: 1px solid hsl(var(--border));
  }}
  .toc h3 {{
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: hsl(var(--muted-foreground));
    margin: 0 0 .75rem 0;
    font-weight: 600;
  }}
  .toc ul {{ list-style: none; padding: 0; margin: 0; }}
  .toc li {{ margin: .15rem 0; }}
  .toc li a {{
    display: block;
    padding: .15rem .5rem;
    border-radius: .25rem;
    color: #374151;
    transition: background .1s, color .1s;
  }}
  .toc li a:hover {{ background: hsl(var(--muted)); color: hsl(var(--accent)); text-decoration: none; }}
  .toc li a.active {{ background: color-mix(in srgb, hsl(var(--accent)) 12%, transparent); color: hsl(var(--accent)); font-weight: 500; }}
  .toc-h1 a {{ font-weight: 600; }}
  .toc-h2 {{ padding-left: 0.75rem; }}
  .toc-h3 {{ padding-left: 1.75rem; font-size: .8rem; }}
  .toc-h4 {{ padding-left: 2.5rem; font-size: .75rem; color: hsl(var(--muted-foreground)); }}
  /* Qualify with .content because Tailwind Play CDN injects preflight AFTER
     the page's <style>, resetting bare `h1 {{ ... }}` rules. Higher specificity
     (class selector) beats Tailwind's element selector. */
  .content h1, .content h2, .content h3, .content h4 {{
    font-weight: 700; line-height: 1.25; color: #0f172a;
  }}
  /* Paper title: a distinct element, centered, larger. Not a section heading. */
  .paper-title {{
    font-size: 2.25rem; font-weight: 700; line-height: 1.2;
    letter-spacing: -0.015em; color: #0f172a;
    text-align: center; margin: 0 0 1.25rem 0;
  }}
  /* Section and subsection headings: left-aligned, sized for in-document use. */
  .content h1 {{
    font-size: 1.875rem; margin-top: 3rem; margin-bottom: 1rem;
    letter-spacing: -0.01em;
  }}
  .content h2 {{
    font-size: 1.5rem; margin-top: 2.5rem; margin-bottom: .75rem;
    letter-spacing: -0.005em;
  }}
  .content h3 {{ font-size: 1.25rem; margin-top: 2rem; margin-bottom: .5rem; font-weight: 600; }}
  .content h4 {{ font-size: 1.05rem; margin-top: 1.5rem; margin-bottom: .4rem; font-weight: 600; color: #334155; }}
  .toc h3 {{
    font-size: .75rem; text-transform: uppercase; letter-spacing: .1em;
    color: hsl(var(--muted-foreground)); margin: 0 0 .75rem 0; font-weight: 600;
  }}
  .abstract h2 {{
    border: none; font-size: 1rem; text-transform: uppercase;
    letter-spacing: .08em; margin: 0 0 .5rem 0; padding: 0;
    font-weight: 700; color: hsl(var(--muted-foreground));
  }}
  .paper-section {{ margin-top: 3rem; }}
  .paper-section:first-of-type {{ margin-top: 0; }}
  .paper-section > h1:first-child,
  .paper-section > h2:first-child {{ margin-top: 0; }}
  p {{ margin: .75rem 0; }}
  a {{ color: hsl(var(--accent)); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{ background: hsl(var(--muted)); padding: 0.1rem 0.35rem; border-radius: .25rem; font-size: 0.9em; }}
  pre {{ background: hsl(var(--muted)); padding: 1rem; border-radius: .5rem; overflow-x: auto; }}
  blockquote {{ border-left: 3px solid hsl(var(--border)); padding-left: 1rem; color: hsl(var(--muted-foreground)); margin: 1rem 0; }}
  figure {{ margin: 3rem 0; text-align: center; }}
  figure img {{ display: inline-block; max-width: 100%; border-radius: .5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  figure figcaption, .figure-html .caption, .figure-pdf .caption {{
    font-size: .9rem; color: hsl(var(--muted-foreground)); margin-top: 1rem;
    text-align: center; padding: 0 1rem; line-height: 1.5;
  }}
  .figure-html, .figure-pdf {{ margin: 3rem 0; }}
  p + figure, figure + p {{ margin-top: 2.5rem; }}
  p + .figure-html, p + .figure-pdf {{ margin-top: 2.5rem; }}
  .figure-html + p, .figure-pdf + p {{ margin-top: 2.5rem; }}
  .md-table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .9rem; }}
  .md-table th, .md-table td {{ border: 1px solid hsl(var(--border)); padding: .4rem .6rem; text-align: left; }}
  .md-table thead th {{ background: hsl(var(--muted)); font-weight: 600; }}
  .md-table tr:nth-child(even) td {{ background: color-mix(in srgb, hsl(var(--muted)) 50%, white); }}

  /* Variable styling (inline, in prose) */
  .var {{
    background: color-mix(in srgb, hsl(var(--accent)) 10%, transparent);
    padding: 0.05rem 0.25rem;
    border-radius: .25rem;
    font-variant-numeric: tabular-nums;
    cursor: default;
  }}
  .var.var-has-provenance {{ cursor: help; text-decoration: underline dotted; text-underline-offset: 3px; }}
  .var.var-active {{
    background: color-mix(in srgb, hsl(var(--accent)) 30%, transparent);
    outline: 2px solid hsl(var(--accent));
    outline-offset: 1px;
  }}
  .var.var-undefined {{
    background: color-mix(in srgb, #ef4444 20%, transparent);
    color: #991b1b;
  }}
  a.cite {{ color: hsl(var(--accent)); text-decoration: none; padding: 0 .1rem; }}
  a.cite:hover {{ text-decoration: underline; }}
  .cite-missing {{ color: #991b1b; }}
  .ref {{ color: hsl(var(--accent)); font-style: italic; }}
  ol.references {{ list-style: none; padding-left: 0; counter-reset: none; }}
  ol.references li {{
    display: grid; grid-template-columns: 2.5rem 1fr; gap: .25rem;
    padding: .5rem 0; border-bottom: 1px solid hsl(var(--border));
    font-size: .9rem;
  }}
  ol.references li:target {{
    background: color-mix(in srgb, hsl(var(--accent)) 12%, transparent);
    margin: 0 -1rem; padding: .5rem 1rem;
    border-radius: .25rem;
  }}
  ol.references .bib-number {{ color: hsl(var(--muted-foreground)); font-variant-numeric: tabular-nums; }}
  ol.references .bib-title {{ font-weight: 500; }}
  ol.references .bib-venue {{ color: hsl(var(--muted-foreground)); }}

  /* Provenance side panel. Kept in DOM so the grid transitions smoothly from
     0 → 380px for the third column. overflow:hidden clips the content while
     the column width is small. */
  .provenance-panel {{
    position: sticky;
    top: 1.5rem;
    align-self: start;
    max-height: calc(100vh - 3rem);
    overflow: hidden auto;
    padding: 1.25rem 1rem 1rem 1rem;
    border-left: 1px solid hsl(var(--border));
    font-size: .875rem;
    line-height: 1.5;
    opacity: 0;
    visibility: hidden;
    transform: translateX(16px);
    transition:
      opacity .35s cubic-bezier(0.4, 0, 0.2, 1),
      transform .45s cubic-bezier(0.4, 0, 0.2, 1),
      visibility 0s linear .45s;
  }}
  .layout.prov-open .provenance-panel {{
    opacity: 1;
    visibility: visible;
    transform: none;
    /* Delay the fade-in slightly so the column widens first, then content
       eases in — feels like one coordinated motion. */
    transition:
      opacity .35s cubic-bezier(0.4, 0, 0.2, 1) .12s,
      transform .45s cubic-bezier(0.4, 0, 0.2, 1) .08s,
      visibility 0s;
  }}
  .prov-head {{ display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 1rem; }}
  .prov-title {{
    font-size: .75rem; text-transform: uppercase; letter-spacing: .1em;
    color: hsl(var(--muted-foreground)); font-weight: 600; margin: 0;
  }}
  .prov-close {{
    background: none; border: none; cursor: pointer;
    color: hsl(var(--muted-foreground)); font-size: 1.25rem; line-height: 1;
    padding: .125rem .5rem; border-radius: .25rem;
  }}
  .prov-close:hover {{ background: hsl(var(--muted)); color: #0f172a; }}
  .prov-graph {{ display: flex; flex-direction: column; align-items: stretch; gap: .25rem; margin-bottom: 1rem; }}
  .prov-node {{
    border: 1px solid hsl(var(--border)); border-radius: .5rem;
    padding: .6rem .75rem; background: white;
    transition: border-color .15s;
  }}
  .prov-node:hover {{ border-color: color-mix(in srgb, hsl(var(--accent)) 50%, hsl(var(--border))); }}
  .prov-node .prov-label {{
    display: block; font-size: .65rem; text-transform: uppercase;
    letter-spacing: .08em; color: hsl(var(--muted-foreground));
    font-weight: 600; margin-bottom: .25rem;
  }}
  .prov-node.inputs {{ background: color-mix(in srgb, #60a5fa 10%, white); border-color: color-mix(in srgb, #60a5fa 30%, hsl(var(--border))); }}
  .prov-node.command {{ background: color-mix(in srgb, #f59e0b 10%, white); border-color: color-mix(in srgb, #f59e0b 30%, hsl(var(--border))); font-family: ui-monospace, SFMono-Regular, monospace; font-size: .8rem; word-break: break-word; }}
  .prov-node.output {{ background: color-mix(in srgb, #16a34a 10%, white); border-color: color-mix(in srgb, #16a34a 35%, hsl(var(--border))); }}
  .prov-node ul {{ list-style: none; padding: 0; margin: 0; }}
  .prov-node li {{ padding: .1rem 0; font-family: ui-monospace, SFMono-Regular, monospace; font-size: .8rem; word-break: break-word; }}
  .prov-node li + li {{ border-top: 1px dashed hsl(var(--border)); margin-top: .25rem; padding-top: .35rem; }}
  .prov-arrow {{
    display: flex; align-items: center; justify-content: center;
    color: hsl(var(--muted-foreground)); font-size: 1.25rem; line-height: 1;
    height: 1.25rem;
  }}
  .prov-output-name {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: .85rem; font-weight: 600; }}
  .prov-output-value {{
    display: inline-block; margin-left: .5rem; padding: .05rem .35rem;
    background: hsl(var(--muted)); border-radius: .25rem;
    font-family: ui-monospace, SFMono-Regular, monospace; font-variant-numeric: tabular-nums;
  }}
  .prov-description {{
    font-size: .85rem; color: hsl(var(--muted-foreground));
    margin: 0 0 1rem 0;
  }}
  .prov-updated {{
    font-size: .75rem; color: hsl(var(--muted-foreground));
    text-align: right; margin: .75rem 0 0 0;
    font-variant-numeric: tabular-nums;
  }}
  .prov-empty {{
    color: hsl(var(--muted-foreground)); font-style: italic;
    padding: 1rem; text-align: center;
  }}

  .paper-header {{
    margin-bottom: 2rem; border-bottom: 1px solid hsl(var(--border));
    padding-bottom: 1.5rem; text-align: center;
  }}
  .authors {{ margin-top: 1rem; font-size: 1rem; }}
  .author {{ margin: 0 .5rem; }}
  .affiliations {{ font-size: .85rem; color: hsl(var(--muted-foreground)); padding-left: 1.5rem; margin-top: .5rem; }}
  .abstract {{ background: hsl(var(--muted)); padding: 1.25rem; border-radius: .5rem; margin: 1.5rem 0; }}
  hr {{ border: 0; border-top: 1px solid hsl(var(--border)); margin: 2rem 0; }}
  iframe {{ background: white; }}
</style>
</head>
<body>
  <div class="layout">
    {toc_html}
    <div class="content">
      <header class="paper-header">
        <div id="top" class="paper-title">{title}</div>
        {authors_html}
        {affiliations_html}
      </header>

      {abstract_html}

      <main>
        {sections_html}
      </main>
    </div>
    <aside class="provenance-panel" id="provenance-panel" aria-hidden="true">
      <div class="prov-head">
        <h3 class="prov-title">Provenance</h3>
        <button class="prov-close" type="button" aria-label="Close provenance panel">&times;</button>
      </div>
      <div id="prov-body"></div>
    </aside>
  </div>

  <script>
    // KaTeX auto-render with our template's \\newcommand macros wired in
    const katexMacros = {katex_macros_json};
    document.addEventListener("DOMContentLoaded", function () {{
      renderMathInElement(document.body, {{
        delimiters: [
          {{left: "$$", right: "$$", display: true}},
          {{left: "\\\\[", right: "\\\\]", display: true}},
          {{left: "$", right: "$", display: false}},
          {{left: "\\\\(", right: "\\\\)", display: false}}
        ],
        macros: katexMacros,
        throwOnError: false,
        strict: "ignore"
      }});
    }});

    // Provenance side panel: click a variable to render its graph.
    const layout = document.querySelector(".layout");
    const panel = document.getElementById("provenance-panel");
    const panelBody = document.getElementById("prov-body");
    const panelClose = panel.querySelector(".prov-close");
    let activeVar = null;

    function escapeHtml(s) {{
      return String(s).replace(/[&<>"']/g, c => ({{
        "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
      }})[c]);
    }}

    function renderProvenance(data, varName, varFmt, displayValue) {{
      const label = varFmt ? `${{varName}}:${{varFmt}}` : varName;
      const inputs = data.data && data.data.length ? data.data : [];
      const fullName = escapeHtml(label);
      const parts = [];

      // 1. Description as muted text (no background card)
      if (data.description) {{
        parts.push(`<p class="prov-description">${{escapeHtml(data.description)}}</p>`);
      }}

      // 2. Graph: inputs -> command -> output variable
      let graphHtml = '<div class="prov-graph">';
      if (inputs.length) {{
        graphHtml += '<div class="prov-node inputs">';
        graphHtml += '<span class="prov-label">inputs</span>';
        graphHtml += '<ul>' + inputs.map(d => `<li>${{escapeHtml(d)}}</li>`).join("") + '</ul>';
        graphHtml += '</div>';
        graphHtml += '<div class="prov-arrow">&#8595;</div>';
      }} else if (data.source) {{
        graphHtml += '<div class="prov-node inputs">';
        graphHtml += '<span class="prov-label">source</span>';
        graphHtml += `<ul><li>${{escapeHtml(data.source)}}</li></ul>`;
        graphHtml += '</div>';
        graphHtml += '<div class="prov-arrow">&#8595;</div>';
      }}
      if (data.command) {{
        graphHtml += '<div class="prov-node command">';
        graphHtml += '<span class="prov-label">command</span>';
        graphHtml += escapeHtml(data.command);
        graphHtml += '</div>';
        graphHtml += '<div class="prov-arrow">&#8595;</div>';
      }}
      graphHtml += '<div class="prov-node output">';
      graphHtml += '<span class="prov-label">variable</span>';
      graphHtml += `<span class="prov-output-name">${{fullName}}</span>`;
      graphHtml += `<span class="prov-output-value">${{escapeHtml(displayValue)}}</span>`;
      graphHtml += '</div></div>';
      parts.push(graphHtml);

      // 3. Updated timestamp right-aligned under the graph
      if (data.updated) {{
        parts.push(`<p class="prov-updated">updated ${{escapeHtml(data.updated)}}</p>`);
      }}

      panelBody.innerHTML = parts.join("");
    }}

    function openProvenance(target) {{
      if (activeVar) activeVar.classList.remove("var-active");
      activeVar = target;
      target.classList.add("var-active");
      try {{
        const data = JSON.parse(target.dataset.provenance);
        renderProvenance(data, target.dataset.var, target.dataset.fmt || "", target.textContent);
        layout.classList.add("prov-open");
        panel.setAttribute("aria-hidden", "false");
      }} catch (err) {{ console.error(err); }}
    }}

    function closeProvenance() {{
      if (activeVar) {{
        activeVar.classList.remove("var-active");
        activeVar = null;
      }}
      layout.classList.remove("prov-open");
      panel.setAttribute("aria-hidden", "true");
    }}

    document.body.addEventListener("click", (e) => {{
      const target = e.target.closest(".var.var-has-provenance");
      if (target) {{
        e.preventDefault();
        if (activeVar === target) {{
          closeProvenance();
        }} else {{
          openProvenance(target);
        }}
        return;
      }}
      // Ignore clicks inside the panel itself
      if (e.target.closest(".provenance-panel")) return;
    }});

    panelClose.addEventListener("click", closeProvenance);
    document.addEventListener("keydown", (e) => {{
      if (e.key === "Escape") closeProvenance();
    }});

    // Scroll-spy: highlight the TOC entry matching the heading currently in view.
    document.addEventListener("DOMContentLoaded", () => {{
      const tocLinks = Array.from(document.querySelectorAll(".toc a[href^='#']"));
      if (!tocLinks.length) return;
      const linksBySlug = new Map(tocLinks.map(a => [a.getAttribute("href").slice(1), a]));
      const headings = Array.from(document.querySelectorAll("main h1[id], main h2[id], main h3[id], main h4[id]"));
      if (!headings.length) return;
      const observer = new IntersectionObserver((entries) => {{
        entries.forEach(entry => {{
          const link = linksBySlug.get(entry.target.id);
          if (!link) return;
          if (entry.isIntersecting) {{
            tocLinks.forEach(a => a.classList.remove("active"));
            link.classList.add("active");
          }}
        }});
      }}, {{ rootMargin: "-40% 0px -55% 0px" }});
      headings.forEach(h => observer.observe(h));
    }});
  </script>
</body>
</html>
"""


def build_html(root_dir: Path, version: str, open_browser: bool = False,
               verbose: bool = False) -> bool:
    """Emit out/<version>/html/index.html from src/<version>/ sources."""
    src_dir = root_dir / 'src' / version
    manifest_path = src_dir / 'manifest.yaml'
    docs_dir = src_dir / 'docs'

    if not manifest_path.exists():
        print(f'  Error: manifest not found at {manifest_path}')
        return False
    if not docs_dir.exists():
        print(f'  Error: docs not found at {docs_dir}')
        return False

    print(f'\n  Building HTML: {version}')
    print(f'  Source: {src_dir}')

    manifest = Manifest(manifest_path)
    processor = VariableProcessor(placeholder='XXXX')
    processor.variables.update(manifest.get_variable_values())
    resolve = _build_resolve_variable(processor, manifest)
    bib_entries = load_bib(root_dir, version)
    citations = CitationCollector(bib_entries)
    if verbose:
        print(f'  Loaded {len(bib_entries)} bibliography entries')

    # Template macros for KaTeX (mirrors preview's expansion)
    macros: dict[str, str] = {}
    template_name = manifest.get_template_name() if manifest else 'article'
    for cand in (root_dir / 'templates' / f'{template_name}.tex',
                 root_dir / f'{template_name}.tex'):
        if cand.exists():
            macros = parse_macros(cand.read_text(encoding='utf-8'))
            break
    # KaTeX expects macros keyed with the leading backslash
    katex_macros = {f'\\{k}': v for k, v in macros.items()}

    # Render each section. Rewrite `../figures/` → `figures/` so paths
    # resolve from index.html (figures get copied into the same html/ dir).
    import re as _re
    _REWRITE_FIG_PATH = _re.compile(r'\.\./figures/')

    section_htmls: list[str] = []
    pseudo = {'_bibliography', '_toc'}
    for section_ref in manifest.sections:
        if section_ref in pseudo:
            # Bibliography/TOC are LaTeX artifacts; skip in HTML for now
            continue
        doc_path = src_dir / section_ref
        if not doc_path.exists():
            print(f'  WARNING: section not found: {section_ref}')
            continue
        md_text = doc_path.read_text(encoding='utf-8')
        md_text = _REWRITE_FIG_PATH.sub('figures/', md_text)
        body = md_to_html(md_text, resolve, resolve_citation=citations.resolve)
        section_htmls.append(_render_section_html(body))
        if verbose:
            print(f'    Rendered: {section_ref}')

    # Abstract (if present), rendered as an inline markdown snippet
    abstract_html = ''
    if manifest.metadata.abstract:
        abs_body = md_to_html(manifest.metadata.abstract, resolve,
                              resolve_citation=citations.resolve)
        abstract_html = f'<aside class="abstract"><h2>Abstract</h2>{abs_body}</aside>'

    # Bibliography section — appended after all cited sections so numbering
    # reflects first-appearance order (matches natbib unsrt convention).
    references_html = citations.render_bibliography_html()
    if references_html:
        section_htmls.append(references_html)

    title = manifest.metadata.title or 'Manuscript'

    sections_joined = '\n'.join(section_htmls)
    toc = _extract_toc(sections_joined)
    toc_html = _render_toc_html(toc)

    html = INDEX_TEMPLATE.format(
        title=title,
        authors_html=_render_authors_html(manifest),
        affiliations_html=_render_affiliations_html(manifest),
        abstract_html=abstract_html,
        sections_html=sections_joined,
        toc_html=toc_html,
        katex_macros_json=json.dumps(katex_macros),
    )

    # Write output
    html_dir = root_dir / 'out' / version / 'html'
    html_dir.mkdir(parents=True, exist_ok=True)
    index_path = html_dir / 'index.html'
    index_path.write_text(html, encoding='utf-8')

    # Copy figures so <img>/<iframe> paths resolve. Docs link ../figures/foo.png
    # relative to the doc, but in the HTML output the index.html sits at html/
    # and figures live at html/figures/. We rewrite the href layout accordingly
    # at the markdown level (see note below); for now we copy everything.
    n_copied = 0
    for src_fig, dest_fig in _compute_figures_copy_plan(src_dir, html_dir):
        dest_fig.parent.mkdir(parents=True, exist_ok=True)
        if not dest_fig.exists() or src_fig.stat().st_mtime > dest_fig.stat().st_mtime:
            shutil.copy2(src_fig, dest_fig)
            n_copied += 1

    print(f'  HTML written: {index_path}')
    print(f'  Figures copied: {n_copied}')

    if open_browser:
        import webbrowser
        webbrowser.open(f'file://{index_path}')

    return True
