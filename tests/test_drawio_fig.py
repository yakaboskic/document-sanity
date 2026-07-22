"""Composed draw.io figures: ds-* asset contract, sync determinism, and the
guarantee that manual layout (mxGeometry) is never touched by sync."""

import base64
import io
import urllib.parse
import zlib
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from document_sanity.drawio_fig import (
    Asset,
    add_asset,
    build_export_command,
    find_assets,
    load_mxfile,
    asset_status,
    resolve_source,
    serialize_mxfile,
    sync_file,
    sync_asset,
    _get_style_value,
    _set_style_value,
)
from document_sanity.manifest import FigureEntry, resolve_figure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png(path, w, h, color=(200, 30, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (w, h), color).save(path)
    return path


def _make_drawio(path, body):
    """Write a minimal uncompressed mxfile whose page root contains `body`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<mxfile host="test"><diagram id="p1" name="Page-1"><mxGraphModel>'
        '<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'{body}'
        '</root></mxGraphModel></diagram></mxfile>',
        encoding='utf-8',
    )
    return path


def _asset_xml(asset_id='ds-asset-a', source='assets/a.png', crop=None,
               extra_attrs='', style='shape=image;', x=10, y=20, w=100, h=50):
    crop_attr = f' ds-crop="{crop}"' if crop else ''
    return (
        f'<object id="{asset_id}" label="" ds-source="{source}"{crop_attr}{extra_attrs}>'
        f'<mxCell style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
        f'</mxCell></object>'
    )


def _embedded_image(drawio_path, asset_id):
    """Decode the asset's embedded style data-URI back into a Pillow image."""
    root = load_mxfile(drawio_path.read_text())
    asset = next(p for p in find_assets(root) if p.cell_id == asset_id)
    uri = _get_style_value(asset.cell.get('style', ''), 'image')
    assert uri is not None and uri.startswith('data:image/png,')
    data = base64.b64decode(uri[len('data:image/png,'):])
    return Image.open(io.BytesIO(data))


# ---------------------------------------------------------------------------
# mxfile load / serialize
# ---------------------------------------------------------------------------

def test_load_uncompressed_mxfile(tmp_path):
    f = _make_drawio(tmp_path / 'fig.drawio', _asset_xml())
    root = load_mxfile(f.read_text())
    assert root.tag == 'mxfile'
    assert len(find_assets(root)) == 1


def test_load_compressed_diagram_inflates():
    model = ('<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
             + _asset_xml() + '</root></mxGraphModel>')
    compressor = zlib.compressobj(wbits=-15)
    deflated = (compressor.compress(urllib.parse.quote(model, safe='').encode())
                + compressor.flush())
    payload = base64.b64encode(deflated).decode()
    text = f'<mxfile><diagram id="p1" name="Page-1">{payload}</diagram></mxfile>'
    root = load_mxfile(text)
    assert root.find('diagram/mxGraphModel') is not None
    assert len(find_assets(root)) == 1


def test_serialize_always_uncompressed():
    text = '<mxfile><diagram id="p1" name="P"><mxGraphModel><root><mxCell id="0"/></root></mxGraphModel></diagram></mxfile>'
    out = serialize_mxfile(load_mxfile(text))
    assert '<mxGraphModel>' in out
    assert out.endswith('\n')


def test_load_bare_mxgraphmodel_is_wrapped():
    root = load_mxfile('<mxGraphModel><root><mxCell id="0"/></root></mxGraphModel>')
    assert root.tag == 'mxfile'
    assert root.find('diagram/mxGraphModel') is not None


def test_load_rejects_non_drawio():
    with pytest.raises(ValueError, match='Not a draw.io file'):
        load_mxfile('<svg/>')


# ---------------------------------------------------------------------------
# Asset discovery
# ---------------------------------------------------------------------------

def test_find_assets_ignores_cells_without_ds_source(tmp_path):
    body = (
        _asset_xml()
        + '<mxCell id="txt" value="Asset A" style="text;" vertex="1" parent="1">'
          '<mxGeometry x="0" y="0" width="40" height="20" as="geometry"/></mxCell>'
        + '<object id="plain" label="note"><mxCell style="shape=image;" vertex="1" parent="1">'
          '<mxGeometry x="5" y="5" width="10" height="10" as="geometry"/></mxCell></object>'
    )
    f = _make_drawio(tmp_path / 'fig.drawio', body)
    assets = find_assets(load_mxfile(f.read_text()))
    assert [p.cell_id for p in assets] == ['ds-asset-a']


def test_find_assets_parses_attrs():
    root = load_mxfile('<mxfile><diagram id="p" name="P"><mxGraphModel><root>'
                       + _asset_xml(crop='40,10,80,60',
                                    extra_attrs=' ds-source-size="120x90" ds-sha256="abcd"')
                       + '</root></mxGraphModel></diagram></mxfile>')
    p = find_assets(root)[0]
    assert p.crop == (40, 10, 80, 60)
    assert p.recorded_size == (120, 90)
    assert p.recorded_hash == 'abcd'
    assert p.geometry == (10.0, 20.0, 100.0, 50.0)


def test_find_assets_malformed_crop_names_asset():
    root = load_mxfile('<mxfile><diagram id="p" name="P"><mxGraphModel><root>'
                       + _asset_xml(crop='40,10') + '</root></mxGraphModel></diagram></mxfile>')
    with pytest.raises(ValueError, match='ds-asset-a'):
        find_assets(root)


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------

def test_resolve_source_prefers_drawio_dir_then_manifest_root(tmp_path):
    ver = tmp_path / 'src' / 'v1'
    (ver / 'manifest.yaml').parent.mkdir(parents=True)
    (ver / 'manifest.yaml').write_text('')
    drawio = ver / 'figures' / 'f1' / 'f1.drawio'
    drawio.parent.mkdir(parents=True)
    drawio.write_text('')

    near = _make_png(drawio.parent / 'assets' / 'a.png', 4, 4)
    assert resolve_source('assets/a.png', drawio) == near

    far = _make_png(ver / 'shared' / 'b.png', 4, 4)
    assert resolve_source('shared/b.png', drawio) == far

    assert resolve_source('nope.png', drawio) is None


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def test_set_style_value_preserves_other_segments():
    style = 'shape=image;imageAspect=0;image=data:image/png,OLD;aspect=fixed;'
    out = _set_style_value(style, 'image', 'data:image/png,NEW')
    assert out == 'shape=image;imageAspect=0;image=data:image/png,NEW;aspect=fixed;'


def test_set_style_value_appends_before_trailing_semicolon():
    assert _set_style_value('shape=image;', 'image', 'X') == 'shape=image;image=X;'
    assert _set_style_value('shape=image', 'image', 'X') == 'shape=image;image=X'


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def _figure_dir(tmp_path, w=120, h=90, crop=None, style='shape=image;'):
    """A figures/f1/ dir with f1.drawio (one asset) + assets/a.png source."""
    fig_dir = tmp_path / 'figures' / 'f1'
    _make_png(fig_dir / 'assets' / 'a.png', w, h)
    drawio = _make_drawio(fig_dir / 'f1.drawio', _asset_xml(crop=crop, style=style))
    return drawio


def test_sync_embeds_source_and_preserves_geometry(tmp_path):
    drawio = _figure_dir(tmp_path)
    results = sync_file(drawio)
    assert [r.action for r in results] == ['synced']
    img = _embedded_image(drawio, 'ds-asset-a')
    assert img.size == (120, 90)
    root = load_mxfile(drawio.read_text())
    assert find_assets(root)[0].geometry == (10.0, 20.0, 100.0, 50.0)


def test_sync_applies_crop(tmp_path):
    drawio = _figure_dir(tmp_path, crop='40,10,60,30')
    sync_file(drawio)
    assert _embedded_image(drawio, 'ds-asset-a').size == (60, 30)


def test_sync_updates_size_and_hash_attrs(tmp_path):
    drawio = _figure_dir(tmp_path)
    sync_file(drawio)
    p = find_assets(load_mxfile(drawio.read_text()))[0]
    assert p.recorded_size == (120, 90)
    assert p.recorded_hash and len(p.recorded_hash) == 16


def test_sync_unchanged_hash_is_noop(tmp_path):
    drawio = _figure_dir(tmp_path)
    sync_file(drawio)
    before = drawio.read_bytes()
    mtime = drawio.stat().st_mtime_ns
    results = sync_file(drawio)
    assert [r.action for r in results] == ['unchanged']
    assert drawio.read_bytes() == before
    assert drawio.stat().st_mtime_ns == mtime


def test_sync_twice_is_deterministic(tmp_path):
    drawio = _figure_dir(tmp_path, crop='0,0,50,50')
    sync_file(drawio)
    first = drawio.read_bytes()
    sync_file(drawio, force=True)
    assert drawio.read_bytes() == first


def test_sync_picks_up_regenerated_source(tmp_path):
    drawio = _figure_dir(tmp_path)
    sync_file(drawio)
    _make_png(drawio.parent / 'assets' / 'a.png', 120, 90, color=(0, 0, 255))
    results = sync_file(drawio)
    assert [r.action for r in results] == ['synced']
    r, g, b = _embedded_image(drawio, 'ds-asset-a').getpixel((0, 0))[:3]
    assert (r, g, b) == (0, 0, 255)


def test_sync_missing_source_reports_and_preserves_asset(tmp_path):
    drawio = _make_drawio(tmp_path / 'figures' / 'f1' / 'f1.drawio',
                          _asset_xml(style='shape=image;image=data:image/png,KEEP;'))
    before = drawio.read_bytes()
    results = sync_file(drawio)
    assert [r.action for r in results] == ['missing-source']
    assert drawio.read_bytes() == before


def test_crop_out_of_bounds_clamped_with_warning(tmp_path):
    drawio = _figure_dir(tmp_path, w=100, h=80, crop='60,50,100,100')
    results = sync_file(drawio)
    assert results[0].action == 'synced'
    assert any('clamped' in w for w in results[0].warnings)
    assert _embedded_image(drawio, 'ds-asset-a').size == (40, 30)


def test_source_size_change_warns(tmp_path):
    drawio = _figure_dir(tmp_path)
    sync_file(drawio)
    _make_png(drawio.parent / 'assets' / 'a.png', 200, 90)
    results = sync_file(drawio)
    assert any('size changed 120x90 -> 200x90' in w for w in results[0].warnings)


def test_aspect_drift_warning(tmp_path):
    # Embedded 120x90 (4:3) vs geometry 100x50 (2:1) — well past 1% drift.
    drawio = _figure_dir(tmp_path)
    results = sync_file(drawio)
    assert any('drifts' in w for w in results[0].warnings)


def test_sync_never_touches_unmanaged_cells(tmp_path):
    fig_dir = tmp_path / 'figures' / 'f1'
    _make_png(fig_dir / 'assets' / 'a.png', 20, 20)
    body = (_asset_xml()
            + '<mxCell id="txt" value="A" style="text;" vertex="1" parent="1">'
              '<mxGeometry x="1" y="2" width="3" height="4" as="geometry"/></mxCell>')
    drawio = _make_drawio(fig_dir / 'f1.drawio', body)
    sync_file(drawio)
    out = drawio.read_text()
    assert '<mxCell id="txt" value="A" style="text;" vertex="1" parent="1">' in out


# ---------------------------------------------------------------------------
# add_asset
# ---------------------------------------------------------------------------

def test_add_asset_creates_object_with_geometry_from_crop(tmp_path):
    src = _make_png(tmp_path / 'a.png', 100, 80)
    root = load_mxfile('<mxfile><diagram id="p" name="P"><mxGraphModel><root>'
                       '<mxCell id="0"/><mxCell id="1" parent="0"/>'
                       '</root></mxGraphModel></diagram></mxfile>')
    asset = add_asset(root, 'a.png', src, crop=(0, 0, 50, 25),
                      at=(30.0, 40.0), width=200.0)
    assert asset.cell_id == 'ds-asset-a'
    geo = asset.cell.find('mxGeometry')
    assert (geo.get('x'), geo.get('y')) == ('30', '40')
    assert (geo.get('width'), geo.get('height')) == ('200', '100')  # 2:1 crop aspect
    assert asset.obj.get('ds-crop') == '0,0,50,25'
    assert asset.obj.get('ds-sha256')
    assert _get_style_value(asset.cell.get('style'), 'image').startswith('data:image/png,')


def test_add_asset_id_collision_suffixing(tmp_path):
    src = _make_png(tmp_path / 'a.png', 10, 10)
    root = load_mxfile('<mxfile><diagram id="p" name="P"><mxGraphModel><root>'
                       '<mxCell id="0"/><mxCell id="1" parent="0"/>'
                       '</root></mxGraphModel></diagram></mxfile>')
    p1 = add_asset(root, 'a.png', src)
    p2 = add_asset(root, 'a.png', src)
    assert p1.cell_id == 'ds-asset-a'
    assert p2.cell_id == 'ds-asset-a-2'


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_asset_status_lifecycle(tmp_path):
    drawio = _figure_dir(tmp_path)

    def status():
        p = find_assets(load_mxfile(drawio.read_text()))[0]
        return asset_status(p, drawio)

    assert status() == 'never-synced'
    sync_file(drawio)
    assert status() == 'fresh'
    _make_png(drawio.parent / 'assets' / 'a.png', 120, 90, color=(1, 2, 3))
    assert status() == 'stale'
    _make_png(drawio.parent / 'assets' / 'a.png', 300, 90)
    assert status() == 'size-changed'
    (drawio.parent / 'assets' / 'a.png').unlink()
    assert status() == 'missing'


# ---------------------------------------------------------------------------
# Export command (pure construction — no app invocation in tests)
# ---------------------------------------------------------------------------

def test_build_export_command_uses_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv('DRAWIO_APP', '/opt/drawio')
    cmd = build_export_command(tmp_path / 'f.drawio', tmp_path / 'f.png')
    assert cmd == ['/opt/drawio', '-x', '-f', 'png', '-o',
                   str(tmp_path / 'f.png'), str(tmp_path / 'f.drawio')]


def test_build_export_command_explicit_arg_wins(tmp_path, monkeypatch):
    monkeypatch.setenv('DRAWIO_APP', '/opt/drawio')
    cmd = build_export_command(tmp_path / 'f.drawio', tmp_path / 'f.png',
                               app='/custom/bin')
    assert cmd[0] == '/custom/bin'


# ---------------------------------------------------------------------------
# Integration guard: exported PNG flows through the existing figure pipeline
# ---------------------------------------------------------------------------

def test_html_copy_plan_skips_asset_sources(tmp_path):
    from document_sanity.html_builder import _compute_figures_copy_plan
    src = tmp_path / 'src'
    _make_png(src / 'figures' / 'f1' / 'f1.png', 8, 8)
    _make_png(src / 'figures' / 'f1' / 'assets' / 'a.png', 8, 8)
    pairs = _compute_figures_copy_plan(src, tmp_path / 'html')
    copied = {p[0].name for p in pairs if p[0].suffix == '.png'}
    assert copied == {'f1.png'}


def test_exported_png_location_resolves_for_all_targets(tmp_path):
    figs = tmp_path / 'src' / 'figures'
    fig_dir = figs / 'f1'
    fig_dir.mkdir(parents=True)
    (fig_dir / 'f1.drawio').write_text('<mxfile/>')
    _make_png(fig_dir / 'f1.png', 8, 8)
    entry = FigureEntry(id='f1')
    for target in ('pdf', 'html', 'preview', 'word'):
        resolved = resolve_figure(entry, target, figs)
        assert resolved is not None and resolved.name == 'f1.png'
