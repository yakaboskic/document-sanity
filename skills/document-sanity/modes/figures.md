# figures: one folder per figure, the right file per target

## Layout

```
src/<doc>/figures/<id>/
    <id>.pdf      # vector, for the PDF
    <id>.png      # raster: Word, previews, fallback
    <id>.svg      # another vector option
    <id>.html     # interactive (Plotly, Bokeh, …) for the HTML viewer
```

The folder name and the file stem must both be the figure id. Any subset of
formats works. Each target picks the first that exists:

| Target | Prefers |
|---|---|
| PDF | pdf → eps → svg → png → jpg |
| HTML viewer | html → svg → png → jpg → pdf |
| Word | png → jpg → gif → bmp (Word has no PDF or SVG) |
| markdown preview | png → jpg → svg |

So a figure authored as `.pdf` needs a sibling `.png` for Word and previews.
Builds flatten `figures/<id>/<id>.png` to `figures/<id>.png`, so **stems must
be unique** across the document.

## Register it

```yaml
figures:
  overview:
    width: "\\textwidth"      # passed to \includegraphics
    # source: figures/overview/overview.png   # optional explicit fallback
    # formats: {pdf: …, html: …, preview: …}   # optional per-target override
    # crop: false                              # skip whitespace trimming
    provenance:
      data: ["data/results.csv"]
      command: "python scripts/plot_overview.py -o figures/overview/overview.png"
```

Raster figures are cropped of top/bottom whitespace on the way into `out/`
(Pillow). `crop: false` opts one out.

## Use it

- A numbered float with a caption (the usual case):
  ````markdown
  ```latex
  \begin{figure}[h!]
      \centering
      {{fig:overview}}
      \caption{What the reader should take from it.}
      \label{fig:overview}
  \end{figure}
  ```
  ````
  Then `preview -V <doc>`: it writes the `![caption](…)` stand-in under the
  block, which the HTML and Word builds read.
- A one-off inline image: `![alt](../figures/overview/overview.png)`.

Refer to it as `Figure \ref{fig:overview}` (see `cite` mode for labels).

## Regenerating

The build never runs plotting scripts. When results change, the user (or
you, if they ask) reruns the command in the figure's `provenance:`, then
rebuild. Record that command when you add a figure.

## draw.io compositions (multi-panel figures)

A figure composed in draw.io from generated panels keeps its import recipe
inside the `.drawio` file, so regenerated panels drop back into the layout
untouched. Panel sources live in `figures/<id>/assets/` (never copied into
`out/`).

```bash
# once per panel: import it as a managed, re-syncable asset
uv run document-sanity drawio add-asset src/<doc>/figures/fig2/fig2.drawio \
  --source assets/roc.png --crop 40,10,800,600 --at 40,40 --width 400

# the user arranges panels, labels and arrows in the draw.io app

# whenever a panel's PNG is regenerated:
uv run document-sanity drawio sync fig2 -V <doc>     # re-import + export fig2.png
uv run document-sanity drawio status fig2 -V <doc>   # exit 1 if anything is stale
```

- `sync` never touches positions, sizes, text or arrows: only cells with a
  `ds-source` attribute are re-imported. Never edit the `ds-*` attributes'
  values by hand except `ds-source` and `ds-crop`.
- The PNG export needs the draw.io desktop app (`--app`, `$DRAWIO_APP`, or
  the standard install). Without it, `sync --no-export` re-imports and the
  user exports from the app.
- Commit both `fig2.drawio` and `fig2.png`: builds use the PNG and never need
  draw.io.
- `check` doesn't run draw.io. When a composed figure's panels changed, run
  `drawio status` too.
