# References & labels

`latex-builder`'s HTML viewer auto-numbers figures, tables, equations, and
sections based on the **prefix of the `\label{…}` key**. Use consistent
prefixes and the renderer generates "Figure 3", "Table 2", clickable
hyperlinks, and anchor targets for you — no `\newlabel` or `.aux` file
needed.

## Prefix convention

| Prefix | Renders as | Typical use |
|---|---|---|
| `fig:` | `Figure N` | `\label{fig:validation-genetics}` |
| `tab:` | `Table N` | `\label{tab:common-validation-traits}` |
| `eq:` or `eqn:` | `Eq. N` | `\label{eq:rs-phase}` |
| `sec:` | `Section N` | `\label{sec:methods-rs}` |
| `app:` | `Appendix N` | `\label{app:derivations}` |
| `alg:` | `Algorithm N` | `\label{alg:gibbs-sampler}` |

An unknown prefix falls through to `Section N` numbering.

The kind map lives in `html_builder.py::_LABEL_KIND_NAMES` — add entries
there to support new prefixes.

## Numbering scheme

One counter per prefix, incremented in document order across **all**
sections in the order listed in `manifest.sections`. That is:

- Every new `\label{fig:…}` gets the next figure number (1, 2, 3, …).
- Every new `\label{tab:…}` gets the next table number (1, 2, 3, …).
- The counters are independent — Figure 3 is whatever the 3rd figure is,
  regardless of table numbering.

Labels are harvested BEFORE section rendering begins, so a
`\ref{fig:something}` in the introduction can refer to a figure that only
appears (with `\label{fig:something}`) in an appendix — both numbering
passes are over the whole manifest.

## Where labels may appear

Valid locations for `\label{key}`:

- Inside a ```latex fenced block (the normal case — figure/table env).
- Trailing a markdown heading: `## Methods <!-- \label{sec:methods} -->`.
- Raw `\label{key}` on a line by itself outside any fence.

**Duplicate labels**: the first occurrence wins. Collisions are silently
ignored (no warning — may be worth adding if it bites).

## What the HTML emits

```markdown
```latex
\begin{table}[h]
    ...
    \label{tab:common-validation-traits}
\end{table}
```
```

→

```html
<a id="tab:common-validation-traits"></a>
```

The original ```latex block is stripped from the HTML output (it's
LaTeX-only), but each `\label{}` inside becomes an `<a id>` anchor at
that same position so `\ref{}` links can land there.

And for a reference:

```markdown
See Table \ref{tab:common-validation-traits}.
```

→

```html
See Table <a class="ref" href="#tab:common-validation-traits">Table 4</a>.
```

You'll notice the duplication — "Table Table 4". That's because
`\ref{tab:...}` now renders the *type* and the *number*, so the
leading "Table" you wrote in prose gets doubled. Choose one style:

- **LaTeX-idiomatic (doubled in HTML)**: write `Table \ref{tab:x}` — in
  the PDF `\ref` produces just the number, in HTML it produces
  "Table N". Lives with a small aesthetic bug in HTML.
- **HTML-friendly (clean in HTML, verbose in PDF)**: write just `\ref{tab:x}`
  — in the PDF you'd get "3" alone, in HTML "Table 3". Add `~\ref{}`
  (non-breaking space) in LaTeX to keep the number tied to its kind word.
- **Change the renderer**: edit `_make_resolve_ref` in
  `html_builder.py` to return just the number, matching LaTeX's `\ref`
  convention.

The default today is the LaTeX-idiomatic style — `\ref` renders the full
"Table N" so the HTML reads naturally on its own.

## Undefined labels

`\ref{tab:nonexistent}` with no matching `\label` renders as the raw
label in italic with a dead `#tab:nonexistent` href. Clicking does
nothing useful but the text preserves the intent so it's visible in
review. No build warning is emitted today; that would be a reasonable
follow-up.

## Building the map

`html_builder._collect_labels(manifest, src_dir)` does one pass over
every section file, finds every `\label{key}`, classifies by prefix,
and returns `{key: (kind_name, number)}`. The map is passed to
`md_to_html` as a `resolve_ref(key) → (display, href)` callable.

## PDF output

The PDF path uses native LaTeX `\label` / `\ref` — the HTML
numbering machinery is bypassed entirely. So PDF numbers and HTML numbers
may differ if, say, your LaTeX template introduces counter resets (e.g.,
`\setcounter{figure}{0}` at the start of supplementary) that the HTML
renderer doesn't know about. The HTML renderer always numbers globally
1, 2, 3, … within each prefix.

## Related code

| File | Responsibility |
|---|---|
| `src/latex_builder/html_builder.py::_collect_labels` | Single-pass label harvest across all sections. |
| `src/latex_builder/html_builder.py::_make_resolve_ref` | Returns the `(display, href)` callable. |
| `src/latex_builder/html_builder.py::_LABEL_KIND_NAMES` | Prefix → kind-name map. |
| `src/latex_builder/md2html.py::_ref` / `_label` / `_anchor` | Per-line ref rendering and anchor protection. |
| `src/latex_builder/md2html.py::_replace_latex_fence` | Pulls `\label{}` out of stripped ```latex blocks and emits anchors. |
