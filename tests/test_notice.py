"""metadata.notice: a legend set apart above the first section — centered,
italic, small — in the Word and LaTeX outputs."""

import re

from document_sanity.build import ManuscriptBuilder
from document_sanity.docx_content import ContentBuilder
from document_sanity.docx_styles import default_styles
from document_sanity.manifest import Manifest
from document_sanity.md2docx import render_notice

NOTICE = "This proposal includes data that shall not be disclosed—in whole or in part.\n"


def _project(tmp_path, notice=NOTICE):
    ver = tmp_path / "src" / "v1"
    (ver / "docs").mkdir(parents=True)
    (ver / "docs" / "intro.md").write_text("# 1. Introduction\n\nBody.\n")
    meta = "metadata:\n  title: T\n  render: false\n"
    if notice is not None:
        meta += "  notice: |\n" + "".join(f"    {line}\n" for line in notice.splitlines())
    (ver / "manifest.yaml").write_text(meta + "sections:\n  - docs/intro.md\n")
    return tmp_path


def test_manifest_reads_notice(tmp_path):
    root = _project(tmp_path)
    manifest = Manifest(root / "src" / "v1" / "manifest.yaml")

    assert manifest.metadata.notice == NOTICE


def test_word_notice_is_centered_italic_small():
    builder = ContentBuilder(default_styles())
    render_notice("First paragraph & more.\n\nSecond *paragraph*.", builder)
    paras = re.findall(r"<w:p>.*?</w:p>", builder.to_xml(), re.S)
    small = default_styles()["fontSizes"]["small"]

    assert len(paras) == 2
    for p in paras:
        assert '<w:jc w:val="center"/>' in p
        assert "<w:i/>" in p
        assert f'<w:sz w:val="{small}"/>' in p
    assert "First paragraph &amp; more." in paras[0]


def test_latex_notice_opens_the_body_centered_small_italic(tmp_path):
    root = _project(tmp_path)
    block = ManuscriptBuilder(root, "v1")._build_notice_block()

    assert block.startswith("\\begin{center}\n\\small\\itshape\n")
    assert "shall not be disclosed—in whole or in part." in block
    assert block.endswith("\\end{center}")


def test_no_notice_no_block(tmp_path):
    root = _project(tmp_path, notice=None)

    assert ManuscriptBuilder(root, "v1")._build_notice_block() == ""
