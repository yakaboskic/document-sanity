# draw.io composed figures

Multi-panel scientific figures are usually composed by hand: source images
(matplotlib/R exports) get imported into a layout tool, cropped, positioned,
and decorated with labels and arrows. When results change, the figure has to
be re-massaged manually. `document-sanity drawio` removes that step: the
import/post-processing transforms are recorded **inside the .drawio file
itself**, so re-running `sync` re-imports every source image exactly the way
it was imported the first time — while preserving all manual layout.

Terminology: a **figure** contains one or more **panels** (the A/B/C regions
of the composition), and each panel is built from one or more **assets** —
the deterministically generated source images plus whatever text/arrows you
add by hand. The managed unit here is the asset: any image cell with a
`ds-source` attribute is a *managed asset* that `sync` can re-import.

## Workflow

```
1. Generate asset PNGs deterministically (fixed size/dpi):
     python scripts/plot_roc.py -o src/<ver>/figures/fig2/assets/roc.png

2. Import each asset into the composition:
     document-sanity drawio add-asset src/<ver>/figures/fig2/fig2.drawio \
         --source assets/roc.png --crop 40,10,800,600 --at 40,40 --width 400

3. Massage in the draw.io GUI: arrange panels, move/resize assets, add
   text, arrows, panel letters — anything. Manual layout is never touched
   by sync.

4. When results change, regenerate the asset PNG (step 1) and:
     document-sanity drawio sync fig2
   Every managed asset is re-imported with its recorded crop, and the
   composed figure is re-exported to figures/fig2/fig2.png.

5. Commit both fig2.drawio and fig2.png. The exported PNG is what the
   PDF/HTML/Word builds pick up — builds never need draw.io installed.
```

`sync` and `status` accept either a `.drawio` path or a figure id (resolved
to `src/<ver>/figures/<id>/<id>.drawio` via `--root`/`--version`, with the
usual latest-version auto-detection).

## The `ds-*` attribute contract

A managed asset is an `<object>` element carrying `ds-*` custom attributes —
draw.io's native "Edit Data" mechanism (select a cell, `Cmd+M`), so the
metadata is visible and editable in the GUI and survives manual saves:

```xml
<object id="ds-asset-roc" label=""
        ds-source="assets/roc.png"
        ds-crop="40,10,800,600"
        ds-source-size="1200x900"
        ds-sha256="a1b2c3d4e5f60718">
  <mxCell style="shape=image;...;image=data:image/png,iVBOR..." vertex="1" parent="1">
    <mxGeometry x="40" y="40" width="400" height="300" as="geometry"/>
  </mxCell>
</object>
```

| Attribute | Set by | Meaning |
|---|---|---|
| `ds-source` | you | Path to the source PNG. Resolved relative to the `.drawio` file's directory, then relative to the nearest ancestor containing `manifest.yaml` (i.e. `src/<ver>/`), then as an absolute path. Presence of this attribute is what makes a cell a managed asset. |
| `ds-crop` | you (optional) | `"x,y,w,h"` crop rect in **source-image pixel coordinates**, applied before embedding. Omit for no crop. |
| `ds-source-size` | sync | `"WxH"` of the source at last sync — powers the size-change warning when a regenerated source comes back a different size. |
| `ds-sha256` | sync | First 16 hex chars of the source file's SHA-256 — powers `status` and lets `sync` skip unchanged assets. |

You don't need `add-asset` to create a managed asset: drag any image into
draw.io, right-click → Edit Data, and add a `ds-source` (and optionally
`ds-crop`) attribute. The next `sync` adopts it.

Rules the tooling guarantees:

- **`mxGeometry` is never written by sync** — position and display size are
  yours. If the embedded image's aspect drifts >1% from the cell geometry
  (e.g. you changed the crop rect), sync warns but never resizes.
- Cells without `ds-source` (text, arrows, hand-placed images) are never
  modified.
- Syncing is deterministic: unchanged sources produce **no write at all**;
  syncing twice produces byte-identical files.
- Compressed .drawio files are read transparently; writes are always
  uncompressed XML (the modern draw.io default), which keeps diffs sane.

## Commands

```
document-sanity drawio sync <target> [--root R] [--version V]
    [--no-export]     # skip the draw.io PNG export step
    [--force]         # re-embed even when the source hash is unchanged
    [--app PATH]      # draw.io binary override (or set $DRAWIO_APP)

document-sanity drawio add-asset <drawio-path> --source img.png
    [--crop x,y,w,h] [--at x,y] [--width W] [--page N]

document-sanity drawio status <target> [--root R] [--version V]
    # per-asset: fresh | stale | size-changed | never-synced | missing
    # plus freshness of the exported PNG; exit 1 if anything is stale
    # (CI-friendly, like `preview --check`)
```

## Export & build integration

`sync` exports the composed figure to `<stem>.png` next to the `.drawio`
file — i.e. `figures/<id>/<id>.png` — which the existing per-target figure
resolution picks up for all four targets with **zero build changes**. The
export shells out to the draw.io desktop app (found via `--app`,
`$DRAWIO_APP`, `drawio` on PATH, or the standard macOS install location).
Builds themselves never invoke draw.io: the exported PNG is a committed
artifact, and `drawio status` is the staleness check.

`figures/<id>/assets/` is the blessed home for source asset PNGs. Both build
copy passes (`build.py::copy_figures`, `html_builder.py::_compute_figures_copy_plan`)
skip `assets/` directories, so asset sources are never flattened into `out/`
(where their stems could collide with real figures).

Limitations (v1): PNG export only (no vector PDF of the composition);
multi-page files sync assets on all pages but export draw.io's default page.

## Regenerating sources

`sync` never runs your plotting scripts — regenerate assets yourself, then
sync. Record the command in the figure's `provenance:` block in
`manifest.yaml` (see [variables & provenance](./variables-and-provenance.md))
so it's documented next to the figure:

```yaml
figures:
  fig2:
    provenance:
      data: ["data/validation_results.csv"]
      command: "python scripts/plot_roc.py -o figures/fig2/assets/roc.png"
```

## Related code

| File | Responsibility |
|---|---|
| `src/document_sanity/drawio_fig.py` | The whole contract: mxfile parse/serialize (incl. compressed), asset discovery, sync, add-asset, status, draw.io export. |
| `src/document_sanity/cli.py::cmd_drawio` | `drawio sync / add-asset / status` wiring. |
| `tests/test_drawio_fig.py` | Contract tests: geometry preservation, determinism, crop clamping, status lifecycle. |
