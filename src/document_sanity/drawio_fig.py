#!/usr/bin/env python3
"""
Composed draw.io figures with re-importable source assets.

A multi-panel figure is authored as a .drawio file. Each source asset (a PNG
generated deterministically by e.g. a matplotlib script) is embedded as an
image cell wrapped in an <object> element carrying `ds-*` custom attributes —
draw.io's native "Edit Data" mechanism, so they are visible and editable in
the GUI and survive manual saves:

    <object id="ds-asset-roc" ds-source="assets/roc.png" ds-crop="40,10,800,600"
            ds-source-size="1200x900" ds-sha256="a1b2c3d4e5f60718">
      <mxCell style="shape=image;...;image=data:image/png,iVBOR..." vertex="1" parent="1">
        <mxGeometry x="120" y="80" width="400" height="300" as="geometry"/>
      </mxCell>
    </object>

Attribute contract:
  ds-source       (author-set) path to the source PNG; presence marks a managed
                  asset. Resolved relative to the .drawio file's directory,
                  then relative to the nearest ancestor holding manifest.yaml,
                  then as an absolute path.
  ds-crop         (author-set, optional) "x,y,w,h" rect in source pixel coords,
                  applied before embedding.
  ds-source-size  (sync-written) "WxH" of the source at last sync.
  ds-sha256       (sync-written) first 16 hex chars of the source file's SHA-256.

`sync_file` re-reads each asset's source, re-applies its crop, and re-embeds
the result — never touching mxGeometry, so manual layout (position, size,
added text/arrows) always wins. Cells without ds-source are never modified.
Syncing is deterministic: unchanged sources produce no write at all.

Pillow is a soft dependency (matching figure_crop.py); sync reports an error
per asset when it is unavailable. Exporting the composed PNG shells out to the
draw.io desktop app — the only function here that needs anything beyond stdlib.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import shutil
import subprocess
import urllib.parse
import zlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


SOURCE_ATTR = 'ds-source'
CROP_ATTR = 'ds-crop'
SIZE_ATTR = 'ds-source-size'
HASH_ATTR = 'ds-sha256'

_HASH_LEN = 16
_ASPECT_DRIFT_TOLERANCE = 0.01

_MACOS_DRAWIO_APP = '/Applications/draw.io.app/Contents/MacOS/draw.io'


@dataclass
class Asset:
    """A managed source asset: an <object ds-source=...> wrapping an image cell."""
    cell_id: str
    source: str
    crop: Optional[tuple[int, int, int, int]]
    recorded_size: Optional[tuple[int, int]]
    recorded_hash: Optional[str]
    geometry: Optional[tuple[float, float, float, float]]  # read-only: x, y, w, h
    obj: ET.Element
    cell: ET.Element


@dataclass
class SyncResult:
    asset_id: str
    action: str  # 'synced' | 'unchanged' | 'missing-source' | 'error'
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# mxfile parsing / serialization
# ---------------------------------------------------------------------------

def _inflate_diagram(text: str) -> str:
    """Decode draw.io's legacy compressed <diagram> payload to XML text."""
    data = base64.b64decode(text)
    inflated = zlib.decompress(data, -15)  # raw deflate
    return urllib.parse.unquote(inflated.decode('utf-8'))


def load_mxfile(text: str) -> ET.Element:
    """Parse .drawio content into an <mxfile> element tree.

    Accepts both plain-XML and compressed <diagram> payloads (inflated
    transparently); a bare <mxGraphModel> is wrapped in a single-page
    <mxfile>. Serialization always writes uncompressed XML.
    """
    root = ET.fromstring(text)

    if root.tag == 'mxGraphModel':
        mxfile = ET.Element('mxfile')
        diagram = ET.SubElement(mxfile, 'diagram', {'id': 'page-1', 'name': 'Page-1'})
        diagram.append(root)
        return mxfile

    if root.tag != 'mxfile':
        raise ValueError(f"Not a draw.io file: root element is <{root.tag}>")

    for diagram in root.findall('diagram'):
        if diagram.find('mxGraphModel') is not None:
            continue
        payload = (diagram.text or '').strip()
        if not payload:
            continue
        model = ET.fromstring(_inflate_diagram(payload))
        diagram.text = None
        diagram.append(model)
    return root


def serialize_mxfile(root: ET.Element) -> str:
    """Serialize back to uncompressed XML text ending in a single newline."""
    return ET.tostring(root, encoding='unicode') + '\n'


# ---------------------------------------------------------------------------
# Asset discovery
# ---------------------------------------------------------------------------

def _parse_crop(value: str, asset_id: str) -> tuple[int, int, int, int]:
    try:
        parts = tuple(int(p.strip()) for p in value.split(','))
        if len(parts) != 4:
            raise ValueError
        return parts
    except ValueError:
        raise ValueError(
            f"Asset '{asset_id}': invalid {CROP_ATTR}={value!r} (expected 'x,y,w,h')"
        ) from None


def _parse_size(value: str, asset_id: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split('x')
        return int(w), int(h)
    except ValueError:
        raise ValueError(
            f"Asset '{asset_id}': invalid {SIZE_ATTR}={value!r} (expected 'WxH')"
        ) from None


def find_assets(root: ET.Element) -> list[Asset]:
    """Return managed assets: <object> elements carrying ds-source."""
    assets = []
    for obj in root.iter('object'):
        source = obj.get(SOURCE_ATTR)
        if not source:
            continue
        asset_id = obj.get('id', '<no-id>')
        cell = obj.find('mxCell')
        if cell is None:
            raise ValueError(f"Asset '{asset_id}': <object> has no inner <mxCell>")

        crop_raw = obj.get(CROP_ATTR)
        size_raw = obj.get(SIZE_ATTR)
        geometry = None
        geo = cell.find('mxGeometry')
        if geo is not None:
            geometry = (
                float(geo.get('x', 0)), float(geo.get('y', 0)),
                float(geo.get('width', 0)), float(geo.get('height', 0)),
            )
        assets.append(Asset(
            cell_id=asset_id,
            source=source,
            crop=_parse_crop(crop_raw, asset_id) if crop_raw else None,
            recorded_size=_parse_size(size_raw, asset_id) if size_raw else None,
            recorded_hash=obj.get(HASH_ATTR),
            geometry=geometry,
            obj=obj,
            cell=cell,
        ))
    return assets


def resolve_source(source: str, drawio_path: Path) -> Optional[Path]:
    """Resolve a ds-source path.

    Order: (1) relative to the .drawio file's directory, (2) relative to the
    nearest ancestor directory containing manifest.yaml (the src/<ver>/ root),
    (3) as an absolute path. Returns None if nothing exists.
    """
    p = Path(source)
    if p.is_absolute():
        return p if p.exists() else None

    candidate = drawio_path.parent / p
    if candidate.exists():
        return candidate

    for ancestor in drawio_path.resolve().parents:
        if (ancestor / 'manifest.yaml').exists():
            candidate = ancestor / p
            if candidate.exists():
                return candidate
            break
    return None


# ---------------------------------------------------------------------------
# Style string helpers
# ---------------------------------------------------------------------------

def _get_style_value(style: str, key: str) -> Optional[str]:
    for segment in style.split(';'):
        if segment.startswith(key + '='):
            return segment[len(key) + 1:]
    return None


def _set_style_value(style: str, key: str, value: str) -> str:
    """Replace or append `key=value`, preserving all other segments in order."""
    segments = style.split(';')
    for i, segment in enumerate(segments):
        if segment.startswith(key + '='):
            segments[i] = f'{key}={value}'
            return ';'.join(segments)
    # Append before a trailing empty segment (style ending in ';') if present.
    if segments and segments[-1] == '':
        segments.insert(len(segments) - 1, f'{key}={value}')
    else:
        segments.append(f'{key}={value}')
    return ';'.join(segments)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def _file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:_HASH_LEN]


def sync_asset(asset: Asset, src_path: Path, *, force: bool = False) -> SyncResult:
    """Re-import one asset's source: crop, embed, update ds-* bookkeeping.

    Never writes mxGeometry — manual layout wins.
    """
    result = SyncResult(asset_id=asset.cell_id, action='synced')
    data = src_path.read_bytes()
    digest = _file_hash(data)

    style = asset.cell.get('style', '')
    embedded = _get_style_value(style, 'image')
    if digest == asset.recorded_hash and embedded and not force:
        result.action = 'unchanged'
        return result

    if not _PIL_AVAILABLE:
        result.action = 'error'
        result.warnings.append('Pillow not installed — cannot embed image')
        return result

    img = Image.open(io.BytesIO(data))
    src_w, src_h = img.size

    if asset.recorded_size and (src_w, src_h) != asset.recorded_size:
        rw, rh = asset.recorded_size
        result.warnings.append(
            f'source size changed {rw}x{rh} -> {src_w}x{src_h}; crop rect unchanged'
        )

    if asset.crop:
        x, y, w, h = asset.crop
        cx = min(max(x, 0), src_w)
        cy = min(max(y, 0), src_h)
        cw = min(w, src_w - cx)
        ch = min(h, src_h - cy)
        if (cx, cy, cw, ch) != (x, y, w, h):
            result.warnings.append(
                f'crop {x},{y},{w},{h} exceeds source {src_w}x{src_h}; '
                f'clamped to {cx},{cy},{cw},{ch}'
            )
        if cw <= 0 or ch <= 0:
            result.action = 'error'
            result.warnings.append('crop rect has no overlap with source image')
            return result
        img = img.crop((cx, cy, cx + cw, cy + ch))

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=False)
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    # draw.io style data-URIs omit ';base64' — ';' is the style delimiter.
    asset.cell.set('style', _set_style_value(style, 'image', f'data:image/png,{b64}'))

    asset.obj.set(SIZE_ATTR, f'{src_w}x{src_h}')
    asset.obj.set(HASH_ATTR, digest)

    if asset.geometry:
        _, _, gw, gh = asset.geometry
        emb_w, emb_h = img.size
        if gw > 0 and gh > 0 and emb_h > 0:
            drift = abs(emb_w / emb_h - gw / gh) / (gw / gh)
            if drift > _ASPECT_DRIFT_TOLERANCE:
                result.warnings.append(
                    f'embedded aspect {emb_w}x{emb_h} drifts {drift:.0%} from '
                    f'cell geometry {gw:g}x{gh:g} (layout preserved; resize in '
                    f'draw.io if it looks stretched)'
                )
    return result


def sync_file(drawio_path: Path, *, force: bool = False) -> list[SyncResult]:
    """Sync every managed asset in a .drawio file; write back only on change."""
    text = drawio_path.read_text(encoding='utf-8')
    root = load_mxfile(text)
    baseline = serialize_mxfile(load_mxfile(text))

    results = []
    for asset in find_assets(root):
        src = resolve_source(asset.source, drawio_path)
        if src is None:
            results.append(SyncResult(
                asset_id=asset.cell_id,
                action='missing-source',
                warnings=[f'source not found: {asset.source}'],
            ))
            continue
        results.append(sync_asset(asset, src, force=force))

    serialized = serialize_mxfile(root)
    if serialized != baseline:
        drawio_path.write_text(serialized, encoding='utf-8')
    return results


# ---------------------------------------------------------------------------
# Asset creation
# ---------------------------------------------------------------------------

_ASSET_STYLE = ('shape=image;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;'
                'verticalAlign=top;')


def add_asset(root: ET.Element, source: str, src_path: Path, *,
              crop: Optional[tuple[int, int, int, int]] = None,
              at: tuple[float, float] = (40.0, 40.0),
              width: Optional[float] = None,
              page_index: int = 0) -> Asset:
    """Create a managed asset on a page and embed its source image.

    Display geometry defaults to the (cropped) pixel size, or `width` with
    height derived from the cropped aspect ratio.
    """
    if not _PIL_AVAILABLE:
        raise RuntimeError('Pillow is required to add assets (pip install Pillow)')

    diagrams = root.findall('diagram')
    if not diagrams:
        raise ValueError('draw.io file has no pages')
    if page_index >= len(diagrams):
        raise ValueError(f'page {page_index} does not exist ({len(diagrams)} page(s))')
    model = diagrams[page_index].find('mxGraphModel')
    if model is None:
        raise ValueError(f'page {page_index} has no mxGraphModel')
    cell_root = model.find('root')
    if cell_root is None:
        raise ValueError(f'page {page_index} has no <root>')

    img = Image.open(src_path)
    src_w, src_h = img.size
    px_w, px_h = (crop[2], crop[3]) if crop else (src_w, src_h)
    disp_w = width if width is not None else float(px_w)
    disp_h = disp_w * (px_h / px_w)

    existing_ids = {el.get('id') for el in root.iter() if el.get('id')}
    asset_id = f'ds-asset-{Path(source).stem}'
    n = 1
    while asset_id in existing_ids:
        n += 1
        asset_id = f'ds-asset-{Path(source).stem}-{n}'

    obj = ET.SubElement(cell_root, 'object', {'id': asset_id, 'label': '',
                                              SOURCE_ATTR: source})
    if crop:
        obj.set(CROP_ATTR, ','.join(str(v) for v in crop))
    cell = ET.SubElement(obj, 'mxCell', {'style': _ASSET_STYLE,
                                         'vertex': '1', 'parent': '1'})
    ET.SubElement(cell, 'mxGeometry', {
        'x': f'{at[0]:g}', 'y': f'{at[1]:g}',
        'width': f'{disp_w:g}', 'height': f'{disp_h:g}', 'as': 'geometry',
    })

    asset = Asset(cell_id=asset_id, source=source, crop=crop,
                  recorded_size=None, recorded_hash=None,
                  geometry=(at[0], at[1], disp_w, disp_h), obj=obj, cell=cell)
    result = sync_asset(asset, src_path)
    if result.action == 'error':
        raise RuntimeError(f"Asset '{asset_id}': {'; '.join(result.warnings)}")
    return asset


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def asset_status(asset: Asset, drawio_path: Path) -> str:
    """'fresh' | 'stale' | 'size-changed' | 'missing' | 'never-synced'."""
    src = resolve_source(asset.source, drawio_path)
    if src is None:
        return 'missing'
    if not asset.recorded_hash:
        return 'never-synced'
    if _file_hash(src.read_bytes()) == asset.recorded_hash:
        return 'fresh'
    if _PIL_AVAILABLE and asset.recorded_size:
        with Image.open(src) as img:
            if img.size != asset.recorded_size:
                return 'size-changed'
    return 'stale'


# ---------------------------------------------------------------------------
# Export (the only draw.io-app-dependent path)
# ---------------------------------------------------------------------------

def find_drawio_app(app: Optional[str] = None) -> Optional[str]:
    """Locate the draw.io binary: arg -> $DRAWIO_APP -> PATH -> macOS app."""
    for candidate in (app, os.environ.get('DRAWIO_APP')):
        if candidate:
            return candidate
    found = shutil.which('drawio')
    if found:
        return found
    if Path(_MACOS_DRAWIO_APP).exists():
        return _MACOS_DRAWIO_APP
    return None


def build_export_command(drawio_path: Path, out_path: Path,
                         app: Optional[str] = None) -> Optional[list[str]]:
    binary = find_drawio_app(app)
    if binary is None:
        return None
    return [binary, '-x', '-f', 'png', '-o', str(out_path), str(drawio_path)]


def export_png(drawio_path: Path, out_path: Path, *,
               app: Optional[str] = None) -> bool:
    """Export the composed figure to PNG via the draw.io desktop app."""
    cmd = build_export_command(drawio_path, out_path, app)
    if cmd is None:
        print('  Error: draw.io app not found — install draw.io desktop or set '
              'DRAWIO_APP to its binary path')
        return False
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        print(f'  Error: draw.io export failed (exit {proc.returncode})')
        if proc.stderr.strip():
            print(f'  {proc.stderr.strip()}')
        return False
    return True
