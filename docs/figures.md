# Figures

`latex-builder` chooses the right figure artifact per build target and
auto-crops whitespace from raster images during output.

## Directory layout

```
src/<ver>/figures/
    <figure-id>/
        <figure-id>.pdf        # vector for PDF prints
        <figure-id>.png        # raster fallback, used for previews
        <figure-id>.html       # interactive export (Plotly, Bokeh, etc.)
        <figure-id>.svg        # optional — another vector source
```

The resolver matches the directory name (`<figure-id>`) to the file stem
(`<figure-id>.ext`). Any subset of file formats is fine — missing formats
just aren't considered. A legacy flat layout (`figures/foo.png` with no
subdirectory) still works via the manifest `source:` field.

## Manifest entry

```yaml
figures:
  model_selection:                # id becomes the figure-id used by {{fig:...}}
    width: "\\textwidth"          # passed through to \includegraphics

  "4":                            # canva page mapping — {{canva:4}} resolves here
    source: figures/pigean-figure-3/pigean-figure-3.png   # optional target-agnostic fallback
    formats:                       # optional explicit per-target overrides
      pdf:     figures/pigean-figure-3/pigean-figure-3.pdf
      html:    figures/pigean-figure-3/pigean-figure-3.html
      preview: figures/pigean-figure-3/pigean-figure-3.png
```

- `source:` — a single path used for all targets when nothing else matches.
- `formats:` — an explicit per-target override map. Overrides win over
  both auto-scan and `source:`.
- `crop:` — boolean, default `true`. Set to `false` to skip whitespace
  trimming for this specific figure.
- Other fields (`width`, `caption_height`) pass through unchanged.

## Target preference order

When the manifest doesn't name a specific file, `resolve_figure()` scans
`figures/<id>/` and picks the first file that exists in the target's
preference order:

| Target | First-choice → last-choice |
|---|---|
| PDF build   | `pdf → eps → svg → png → jpg/jpeg` |
| HTML viewer | `html → svg → png → jpg/jpeg → pdf` |
| MD preview  | `png → jpg/jpeg → svg` |

Defined in `manifest.py::TARGET_PREFERENCES`. PDF prefers vector so print
output stays crisp; HTML prefers interactive over vector since a
self-contained `.html` figure beats a static SVG in the browser; MD
preview skips `pdf` / `html` because markdown viewers can't render them.

## Canva pages

The legacy pigean-manuscripts convention treats numeric figure IDs (`"2"`,
`"3"`, …) as Canva page numbers. `{{canva:3}}` in markdown looks up the
manifest entry keyed `"3"`. Use `source:` pointing into the figure's subdir
to wire Canva pages to the new directory layout:

```yaml
"3":
  source: figures/pigean-figure-2/pigean-figure-2.png
```

Add `formats.html` alongside if the figure also has an interactive version.

## Build-time copy + flatten

`build.py` (PDF) and `html_builder.py` (HTML) both walk `src/<ver>/figures/`
with `rglob` and copy every image file, but with a **flattened basename**
as the destination filename:

```
src/03302026/figures/suppfig1/suppfig1.pdf   →  out/03302026/latex/figures/suppfig1.pdf
src/03302026/figures/pigean-figure-3/
    pigean-figure-3.html                     →  out/03302026/html/figures/pigean-figure-3.html
```

This is why hardcoded paths in ```latex blocks that reference
`figures/suppfig1.pdf` (not `figures/suppfig1/suppfig1.pdf`) still work —
the build flattens the nested layout on the way out. It also means
**figure stems must be unique** across the tree (two files named
`plot.png` in different subdirs would collide on copy).

## Whitespace cropping

Raster figures (`.png`, `.jpg`, `.jpeg`) go through
`figure_crop.copy_with_crop()` on their way to the output. The function
finds the top and bottom rows with non-white pixels and crops away
everything outside that range plus 10 pixels of padding. Width is
preserved so `\includegraphics{width=\textwidth}` still fills the column.

- Threshold 250/255 — any row with a pixel below 250 intensity counts
  as content.
- 10 pixels of padding above and below the detected content bounds.
- Per-figure `crop: false` in the manifest opts out.
- Vector formats (`.pdf`, `.eps`, `.svg`) and interactive (`.html`) pass
  through unchanged.
- Requires Pillow + NumPy — soft-imported. Without them cropping is
  skipped, files copy verbatim.

The crop runs on every build, but `copy_with_crop` skips files whose
destination modification time is newer than the source's — so subsequent
builds are fast.

## Figure references in markdown

Three forms, in order of specificity:

```markdown
{{fig:model_selection}}      # named figure from the manifest
{{canva:4}}                  # numeric key (Canva page)
![caption](path/to/file.png) # raw markdown image — bypasses the manifest
```

The first two are rewritten to `\includegraphics[width=\textwidth]{path}`
during LaTeX build (with the right target-preferred artifact) and to
`<img>` / `<iframe>` during HTML build. The raw form passes through
directly.

## Related code

| File | Responsibility |
|---|---|
| `src/latex_builder/manifest.py::FigureEntry` + `resolve_figure()` | Resolution logic; `TARGET_PREFERENCES` constant lives here. |
| `src/latex_builder/variable_processor.py::_resolve_figure` | Rewrites `{{fig:...}}` / `{{canva:...}}` in LaTeX output to `\includegraphics` with the target-resolved path. |
| `src/latex_builder/build.py::copy_figures` | PDF-target crop + flatten copy. |
| `src/latex_builder/html_builder.py::_compute_figures_copy_plan` + `_upgrade_figure_path` | HTML-target copy; rewrites `![](…)` paths in markdown to HTML-preferred artifacts. |
| `src/latex_builder/figure_crop.py` | Whitespace detection + crop implementation (Pillow-backed). |
| `src/latex_builder/preview.py::figure_preview` + `_resolve_preview_path` | Markdown preview block generation, PDF→PNG sibling fallback. |
