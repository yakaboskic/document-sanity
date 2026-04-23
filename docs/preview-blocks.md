# Preview blocks

`document-sanity preview` inserts markdown-renderable approximations of
```latex fenced blocks so GitHub / VSCode / Obsidian / Cursor show
something meaningful when browsing the sources. The ```latex block stays
the source of truth for LaTeX compilation; the preview block next to it
is derived, hash-tagged, and regenerable.

## Shape

```markdown
```latex
\begin{figure}[h!]
    \centering
    {{canva:3}}
    \caption{Conceptual overview of the PIGEAN framework.}
    \label{fig:pigean-method}
\end{figure}
```

<!-- document-sanity:preview:begin hash=a1b2c3d4 -->
![Conceptual overview of the PIGEAN framework.](../figures/pigean-figure-2/pigean-figure-2.png)
<!-- document-sanity:preview:end -->
```

The `hash=a1b2c3d4` is a SHA-256 prefix of the surrounding ```latex
block's normalized content. `preview --check` uses it to detect drift:
if the block changes but its preview wasn't refreshed, the command
returns a non-zero exit code (CI-friendly).

### Legacy marker compatibility

Paper repos authored against the previous tool name (`latex-builder`) use
`<!-- latex-builder:preview:begin/end -->` markers. The parser accepts
both forms, so existing `.md` files keep building without edits; the
next `document-sanity preview` run rewrites old markers to the current
`document-sanity:*` form.

## What gets a preview

| ```latex block contains | Preview becomes |
|---|---|
| `\begin{figure*?}` | `![caption](path/to/image.png)` with caption from `\caption{}`. PDF paths fall back to a sibling `.png` if one exists (markdown viewers can't render PDF). |
| `\begin{table*?\|longtable}` | Markdown pipe-table parsed from the `\begin{tabular}`. `\textbf`, `\href`, `\texttt` are converted; `\multicolumn` collapses span, `\cmidrule`/`\hline` are dropped. |
| `\begin{align*?\|equation*?\|eqnarray*?\|gather*?\|multline*?}` | `$$…$$` per row — `\\` row separators split, `&` alignment tabs stripped. |
| Anything else | No preview emitted. Existing preview block (if any) left untouched — respects hand-authored previews for edge-case passthrough. |

## Template macro expansion

`preview` reads `\newcommand{\name}{body}` definitions from the template
(`templates/<name>.tex`) and expands those macros inside any `$…$`,
`$$…$$`, `\[…\]`, or `\(…\)` math *before* emitting the preview. So
`$p = \prob(x)$` in the source becomes `$p = \text{Pr}(x)$` in the
markdown — KaTeX-based previewers can render it.

Opt out with `--no-expand-macros`. Macros with arguments
(`\newcommand{\foo}[1]{…}`) are skipped; only zero-arg definitions are
expanded.

Expansions are **word-boundary aware**: `\prob` replaces `\prob` but
leaves `\probability` alone.

## Paths

Image paths in the preview are computed relative to the `.md` file,
which lives in `src/<ver>/docs/`. That produces paths like
`../figures/foo.png` — they resolve correctly when GitHub or VSCode
renders the doc.

For HTML builds, the path gets rewritten again (`../figures/` →
`figures/`) because the HTML output sits at `out/<ver>/html/index.html`
with figures flattened into `html/figures/`.

## Commands

```bash
document-sanity preview                # regenerate all preview blocks
document-sanity preview --check        # error if any are stale (CI)
document-sanity preview --verbose      # per-file summary of changes
document-sanity preview --no-expand-macros   # skip \newcommand expansion
```

## Idempotency + drift detection

- First run inserts a new preview block next to each qualifying ```latex
  block.
- Subsequent runs regenerate the body verbatim — a stable hash means no
  diff.
- `preview --check` computes what *would* be written and compares hashes;
  returns exit 1 if anything's drifted. Used in CI to block PRs that
  edit a ```latex block without refreshing preview.

Hand-edits between `preview:begin` and `preview:end` markers get
**overwritten** on the next `preview` run. Edit the source ```latex
block instead.

## Build integration

`md2latex.py` strips everything between `<!-- document-sanity:preview:begin
… -->` and `<!-- document-sanity:preview:end -->` during build, so
preview blocks never leak into the compiled LaTeX output. They're purely
a reading-the-source aid.

The HTML viewer *does* use preview blocks — it strips the ```latex
fence and keeps the preview content (an image / markdown table / math
$$…$$) as the HTML figure body. See [html-viewer.md](./html-viewer.md)
for the interaction.

## Lossiness

Preview blocks are approximations:

- `\multicolumn` spans collapse to single cells — merged headers
  flatten.
- `\cmidrule(lr){1-2}` style rules aren't rendered — markdown tables
  only have one header separator.
- Subfigures become a single image (the first one found); secondary
  panels disappear in the preview.
- Complex equation layouts (multi-line aligned `aligned`, `cases` inside
  `equation`, etc.) may simplify awkwardly.

For anything where fidelity matters more than the preview read, the
```latex block stays canonical and the preview is aspirational — that's
why previews are auto-generated and dismissable.

## Related code

| File | Responsibility |
|---|---|
| `src/document_sanity/preview.py::rewrite_doc` | Core loop over a single doc. |
| `src/document_sanity/preview.py::figure_preview / table_preview / math_preview` | Per-kind renderers. |
| `src/document_sanity/preview.py::_resolve_preview_path` | PDF→PNG sibling fallback. |
| `src/document_sanity/preview.py::hash_block` | Stable normalized-whitespace SHA-256 prefix. |
| `src/document_sanity/md2latex.py::_PREVIEW_BLOCK_RE` | Strips preview from markdown before LaTeX conversion. |
