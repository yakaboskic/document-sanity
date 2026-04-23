# Variables & provenance

Every number in the paper can be a template variable with an attached
chain of custody — the data files it came from, the command that
computed it, a human description, and a last-updated date. In the HTML
viewer, those variables are clickable: the side panel opens and shows
the provenance graph.

## Syntax

In any `.md`, ``.tex``, or manifest `abstract:` field:

```
We analyzed {{NUM_SAMPLES:,}} samples.
The p-value was $p = {{PVAL:.2e}}$.
The R-squared was {{R2:.2f}}.
```

Supported format specs (Python-style, after the colon):

| Spec | Effect | Example |
|---|---|---|
| `:,` | thousands separator | `1,234,567` |
| `:.Nf` | fixed decimal places | `0.87` |
| `:.Ne` | scientific notation | `3.4e-05` (in HTML rewritten to `$3.4 \times 10^{-5}$`) |
| `:.N%` | percentage | `87.0%` |
| `:fmt` | any Python `format()` spec | `"03d"` → `042` |

Variable names are `[A-Za-z_][A-Za-z0-9_]*` — mixed case works (useful
for computed identifiers like `NUM_PIGEAN_AT_RS_eq_OTG_INDIRECT`).

Undefined variables render as `XXXX` (configurable via `--placeholder`)
and are listed in the build summary so you can see what still needs a
value.

## Declaring a variable

Two forms in `manifest.yaml`:

**Simple** — just the value:

```yaml
variables:
  NUM_SAMPLES: 1000
  PVAL: 0.0087
```

**Full** — value plus provenance. Every field is optional; included
fields drive the HTML viewer's side panel:

```yaml
variables:
  PIGEAN_COMBINED_RS_ALL:
    value: 1.90
    provenance:
      description: >
        Relative success of PIGEAN combined support across all
        therapeutic areas, computed against the Pharmaprojects trials
        database.
      source: data/pigean_combined_posteriors.parquet
      data:
        - data/pharmaprojects_outcomes.parquet
        - data/minikel_otg_curation.tsv
      command: python scripts/compute_rs.py --evidence combined --target pharmaprojects
      updated: "2026-03-28"
```

| Field | HTML role |
|---|---|
| `description` | Muted paragraph at the top of the provenance panel. |
| `source` | Shown as the "source" input in the graph (used when `data` is empty). |
| `data` | List of input files rendered in the blue "inputs" node. If present, `source` is hidden from the graph. |
| `command` | The shell command in the amber "command" node. |
| `updated` | Right-aligned timestamp under the graph. |

## HTML rendering

Every `{{VAR}}` in the source becomes:

```html
<span class="var var-has-provenance"
      data-var="NUM_SAMPLES"
      data-fmt=","
      data-provenance='{"description":"…","source":"…","command":"…",…}'>1,000</span>
```

The `.var-has-provenance` class adds the dotted underline and cursor hint.
Clicking opens the right-side panel (see
[html-viewer.md](./html-viewer.md#provenance-panel)) with the inputs →
command → output graph.

Undefined variables get `class="var var-undefined"` — red background so
you can spot them during review.

## Math-mode rewriting

Inside `$…$` or `$$…$$` / `\[…\]`, Python-formatted scientific notation
(`8.65e-09`) gets rewritten to `$8.65 \times 10^{-9}$` so KaTeX renders
it as a proper exponent. Done at HTML render time by
`md2html._prettify_sci_in_math`. Purely for the HTML viewer — PDF keeps
the raw format since `8.65 \times 10^{-9}` already parses in LaTeX
math mode without modification.

## PDF rendering

`\includegraphics` aside, variables resolve via `VariableProcessor`:

```
\begin{abstract}
We analyzed \var{NUM_SAMPLES:,} samples.    →    We analyzed 1{,}000 samples.
\end{abstract}
```

No provenance metadata leaks into the PDF — the `provenance:` block is
only consumed by the HTML builder. The PDF gets the value, full stop.

## Scope and priority

One `variables:` block per version in `manifest.yaml`. The top-level
`shared.json` file (legacy from pigean-manuscripts) is still loaded for
back-compat: values from `manifest.yaml` override values from
`shared.json` which override the default placeholder.

Changing a variable's value without changing how it's displayed is a
one-line diff in `manifest.yaml` — the sections themselves don't need
editing. Keeps prose and data decoupled.

## Related code

| File | Responsibility |
|---|---|
| `src/document_sanity/variable_processor.py` | Core `{{…}}` expansion, used for LaTeX output. |
| `src/document_sanity/manifest.py::VariableEntry` / `Provenance` | Data classes + YAML parsing. |
| `src/document_sanity/html_builder.py::_build_resolve_variable` | Builds the `(name, fmt) → (display, provenance, is_defined)` callable that `md_to_html` uses. |
| `src/document_sanity/md2html.py::_render_variable_span` | Emits the `<span class="var">` with its `data-provenance` JSON attribute. |
| `src/document_sanity/md2html.py::_prettify_sci_in_math` | Scientific-notation math rewrite. |
