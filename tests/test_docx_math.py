"""LaTeX math -> Office Math in the Word build (docx_math, md2docx)."""

import pytest

from document_sanity import docx_math
from document_sanity.docx_content import ContentBuilder
from document_sanity.docx_styles import default_styles
from document_sanity.md2docx import render_markdown

needs_pandoc = pytest.mark.skipif(not docx_math.pandoc_available(), reason="pandoc not installed")


def _builder() -> ContentBuilder:
    return ContentBuilder(default_styles())


def test_scan_keeps_prose_dollars_as_prose():
    text = r"It costs \$5 and \$6, or $5 and $6. Rate $\lambda_i$ and $$\max_x c^\top x$$."
    assert docx_math.scan(text) == [(r"\max_x c^\top x", True), (r"\lambda_i", False)]


def test_normalize_turns_align_into_aligned_and_drops_labels():
    tex = "\\begin{align}a &= b \\label{eq:x}\\\\\n\nc &= d\\nonumber\\end{align}"
    out = docx_math.normalize(tex)
    assert "\\begin{aligned}" in out and "\\end{aligned}" in out
    assert "label" not in out and "nonumber" not in out and "\n\n" not in out


def test_convert_without_pandoc_returns_none(monkeypatch):
    monkeypatch.setattr(docx_math.shutil, "which", lambda _: None)
    assert docx_math.convert([("x", False), ("y", True)]) == [None, None]


@needs_pandoc
def test_convert_gives_inline_and_display_office_math():
    inline, display = docx_math.convert([(r"N_{k} \sim \mathrm{Poisson}(\Lambda)", False), (r"\sum_k x_k", True)])
    assert inline.startswith("<m:oMath>") and "<m:sSub>" in inline and "Λ" in inline
    assert display.startswith("<m:oMathPara>")


@needs_pandoc
def test_render_markdown_writes_office_math_for_display_and_inline():
    b = _builder()
    render_markdown("The rate $\\lambda_i$ is fitted.\n\n$$\n\\max_x \\sum_k c_k x_k\n$$\n\nDone.", b)
    xml = b.to_xml()
    assert xml.count("<m:oMathPara>") == 1
    assert xml.count("<m:oMath>") >= 2  # the inline one and the one inside the paragraph
    assert "$" not in xml
    assert "The rate " in xml and " is fitted." in xml


@needs_pandoc
def test_math_inside_bold_keeps_the_math():
    b = _builder()
    render_markdown("**Event size $\\Lambda$.** Text.", b)
    xml = b.to_xml()
    assert "<m:oMath>" in xml and "\x02" not in xml


@needs_pandoc
def test_equation_environment_in_a_latex_fence_converts():
    b = _builder()
    render_markdown("```latex\n\\begin{align}\na &= b \\\\\nc &= d\n\\end{align}\n```\n", b)
    assert "<m:oMathPara>" in b.to_xml()


def test_fallback_writes_the_latex_source(monkeypatch):
    monkeypatch.setattr(docx_math.shutil, "which", lambda _: None)
    b = _builder()
    render_markdown("$$\n\\max_x c x\n$$\n\nRate $\\lambda$.", b)
    xml = b.to_xml()
    assert "\\max_x c x" in xml and "\\lambda" in xml and "<m:oMath" not in xml


def test_figure_caption_keeps_bold_title_math_and_stays_with_its_figure(tmp_path):
    from PIL import Image

    fig = tmp_path / "figures" / "x" / "x.png"
    fig.parent.mkdir(parents=True)
    Image.new("RGB", (40, 20), "white").save(fig)
    md = (
        "```latex\n\\begin{figure}[h!]\n\\centering\n\\includegraphics{figures/x.png}\n"
        "\\caption{\\textbf{The finding.} \\textbf{a}, Rate $\\lambda$ at 80\\%.}\n\\label{fig:x}\n\\end{figure}\n```\n\n"
        "<!-- document-sanity:preview:begin hash=abc -->\n![The finding. a, Rate at 80%.](../figures/x/x.png)\n"
        "<!-- document-sanity:preview:end -->\n"
    )
    b = _builder()
    render_markdown(md, b, figures_dir=tmp_path / "figures", labels={"fig:x": ("Figure", 1)})
    xml = b.to_xml()
    assert "<w:keepNext/>" in xml
    assert "The finding." in xml and "<w:b/>" in xml
    assert "\\textbf" not in xml and "\x03" not in xml
    if docx_math.pandoc_available():
        assert "<m:oMath>" in xml
