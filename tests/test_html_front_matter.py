"""metadata.render: false — the HTML viewer leaves out the auto title/authors/
abstract block (the document owns its front matter, as in LaTeX and Word), but
the page <title> and the sidebar TOC still work."""

from document_sanity.html_builder import build_html


def _build(tmp_path, render):
    ver = tmp_path / "src" / "v1"
    (ver / "docs").mkdir(parents=True)
    (ver / "docs" / "0_cover.md").write_text("# 1.0 Cover Sheet\n\nTopic: regolith.\n")
    meta = (
        "metadata:\n"
        "  title: Regolith Sintering\n"
        "  authors:\n"
        "    - name: Pat Investigator\n"
        "      affiliations: [1]\n"
        "  affiliations:\n"
        "    1:\n"
        "      institution: Example Institute\n"
        "  abstract: We sinter regolith.\n"
        "  notice: Do not disclose.\n"
    )
    if not render:
        meta += "  render: false\n"
    (ver / "manifest.yaml").write_text(meta + "sections:\n  - docs/0_cover.md\n")

    assert build_html(tmp_path, "v1")
    return (tmp_path / "out" / "v1" / "html" / "index.html").read_text()


def test_render_false_drops_the_title_block(tmp_path):
    html = _build(tmp_path, render=False)

    assert 'class="paper-header"' not in html
    assert "Pat Investigator" not in html
    assert "Example Institute" not in html
    assert 'class="abstract"' not in html
    # The page still opens with the document's own front matter...
    assert "Cover Sheet" in html
    # ...keeps metadata.title as the browser title, its TOC and the notice.
    assert "<title>Regolith Sintering</title>" in html
    assert '<nav class="toc">' in html and "1.0 Cover Sheet</a>" in html
    assert 'class="notice"' in html


def test_render_default_keeps_the_title_block(tmp_path):
    html = _build(tmp_path, render=True)

    assert '<div id="top" class="paper-title">Regolith Sintering</div>' in html
    assert "Pat Investigator" in html
    assert "Example Institute" in html
    assert '<aside class="abstract">' in html
    assert "<title>Regolith Sintering</title>" in html
