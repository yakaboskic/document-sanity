"""Figure resolution: the extension-search feature and the restored
TARGET_PREFERENCES that keep jpeg/eps/gif/bmp resolvable."""

from document_sanity.manifest import (
    FigureEntry,
    TARGET_PREFERENCES,
    resolve_figure,
    _find_file_with_extensions,
)


def _make_figures_dir(tmp_path, filenames):
    src = tmp_path / "src"
    figs = src / "figures"
    figs.mkdir(parents=True)
    for fn in filenames:
        (figs / fn).write_bytes(b"x")
    return figs


def test_extension_search_finds_pdf_from_extensionless_source(tmp_path):
    figs = _make_figures_dir(tmp_path, ["fig_1.pdf"])
    entry = FigureEntry(id="fig_1", source="figures/fig_1")  # no extension
    resolved = resolve_figure(entry, "pdf", figs)
    assert resolved is not None
    assert resolved.name == "fig_1.pdf"


def test_extension_search_prefers_html_for_html_target(tmp_path):
    figs = _make_figures_dir(tmp_path, ["fig_1.pdf", "fig_1.html"])
    entry = FigureEntry(id="fig_1", source="figures/fig_1")
    assert resolve_figure(entry, "html", figs).name == "fig_1.html"
    assert resolve_figure(entry, "pdf", figs).name == "fig_1.pdf"


def test_find_file_with_extensions_direct(tmp_path):
    figs = _make_figures_dir(tmp_path, ["chart.jpeg"])
    found = _find_file_with_extensions(figs / "chart", ("png", "jpg", "jpeg"))
    assert found is not None and found.name == "chart.jpeg"


def test_restored_formats_are_present():
    # Regression guard: the falcon branch had silently narrowed these lists.
    assert "jpeg" in TARGET_PREFERENCES["pdf"]
    assert "eps" in TARGET_PREFERENCES["pdf"]
    assert set(("jpeg", "gif", "bmp")).issubset(TARGET_PREFERENCES["word"])
    assert "htm" in TARGET_PREFERENCES["html"]
    # svg must stay LAST for pdf (pdflatex can't include svg natively).
    assert TARGET_PREFERENCES["pdf"][-1] == "svg"


def test_word_resolves_jpeg(tmp_path):
    figs = _make_figures_dir(tmp_path, ["photo.jpeg"])
    entry = FigureEntry(id="photo", source="figures/photo")
    resolved = resolve_figure(entry, "word", figs)
    assert resolved is not None and resolved.name == "photo.jpeg"
