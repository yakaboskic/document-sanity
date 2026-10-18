"""The Word layout pass (docx_layout) and its place in `document-sanity word`."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

from document_sanity import docx_layout
from document_sanity import init_project as ip
from document_sanity.cli import main
from document_sanity.docx_builder import WordBuilder

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
)


def document(body: str) -> bytes:
    return f'<?xml version="1.0"?><w:document {NS}><w:body>{body}</w:body></w:document>'.encode()


def layout(body: str, body_size: int = 22) -> tuple[str, docx_layout.LayoutStats]:
    xml, stats = docx_layout.layout_document_xml(document(body), body_size)
    return xml.decode(), stats


def para(text: str, ppr: str = "") -> str:
    return f"<w:p>{f'<w:pPr>{ppr}</w:pPr>' if ppr else ''}<w:r><w:t>{text}</w:t></w:r></w:p>"


def row(*cells: str, extra: str = "") -> str:
    return f"<w:tr>{extra}" + "".join(f"<w:tc>{para(c)}</w:tc>" for c in cells) + "</w:tr>"


IMAGE = '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing/></w:r></w:p>'


# ── tables ───────────────────────────────────────────────────────────────────

def test_rows_dont_split_and_the_first_repeats_as_a_header() -> None:
    xml, stats = layout(f"<w:tbl>{row('Name', 'Value')}{row('a', '1')}{row('b', '2')}</w:tbl>")
    assert stats.rows == 3
    assert xml.count('<w:cantSplit w:val="1"/>') == 3
    assert xml.count('<w:tblHeader w:val="1"/>') == 1
    header, body = xml.split("</w:tr>", 1)
    assert "tblHeader" in header and "tblHeader" not in body
    # The header row's paragraphs keep with the first body row.
    assert header.count('<w:keepNext w:val="1"/>') == 2 and "keepNext" not in body


def test_row_properties_follow_table_property_exceptions() -> None:
    xml, _ = layout(f"<w:tbl>{row('x', extra='<w:tblPrEx/>')}</w:tbl>")
    assert "<w:tblPrEx/><w:trPr><w:cantSplit" in xml


def test_existing_row_properties_are_kept() -> None:
    xml, _ = layout(f"<w:tbl>{row('x', extra='<w:trPr><w:cantSplit w:val=\"0\"/><w:jc w:val=\"center\"/></w:trPr>')}</w:tbl>")
    assert xml.count("<w:trPr>") == 1
    assert '<w:cantSplit w:val="1"/><w:jc w:val="center"/><w:tblHeader w:val="1"/>' in xml


# ── headings and figures ─────────────────────────────────────────────────────

def test_headings_keep_with_the_next_paragraph_in_schema_order() -> None:
    xml, _ = layout(para("Methods", '<w:pStyle w:val="Heading2"/><w:spacing w:after="120"/>') + para("Body."))
    assert ('<w:pStyle w:val="Heading2"/><w:keepNext w:val="1"/><w:keepLines w:val="1"/>'
            '<w:spacing w:after="120"/>') in xml
    assert xml.count("keepNext") == 1  # the body paragraph is untouched


def test_figures_keep_with_their_captions() -> None:
    xml, stats = layout(IMAGE + para("Figure 2: Overview.") + para("Text."))
    assert stats.figures == 1
    image, caption, text = xml.split("</w:p>")[:3]
    assert '<w:pPr><w:keepNext w:val="1"/><w:jc w:val="center"/></w:pPr>' in image
    assert '<w:keepLines w:val="1"/>' in caption
    assert "keep" not in text


def test_caption_style_counts_as_a_caption() -> None:
    _, stats = layout(IMAGE + para("An unnumbered caption", '<w:pStyle w:val="Caption"/>'))
    assert stats.figures == 1


def test_an_image_without_a_caption_is_left_alone() -> None:
    xml, stats = layout(IMAGE + para("Just a paragraph."))
    assert stats.figures == 0 and "keep" not in xml


# ── equations ────────────────────────────────────────────────────────────────

FRACTION = (
    "<m:oMath><m:f><m:num><m:r><m:rPr><m:sty m:val=\"p\"/></m:rPr><m:t>a</m:t></m:r></m:num>"
    "<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath>"
)


def test_math_takes_the_body_size() -> None:
    xml, stats = layout(f"<w:p>{FRACTION}</w:p>", body_size=24)
    assert stats.math == 1
    size = '<w:sz w:val="24"/><w:szCs w:val="24"/>'
    # The paragraph mark, both runs (after any m:rPr) and the fraction's control.
    assert f"<w:pPr><w:rPr>{size}</w:rPr></w:pPr>" in xml
    assert f'<m:rPr><m:sty m:val="p"/></m:rPr><w:rPr>{size}</w:rPr><m:t>a</m:t>' in xml
    assert f"<m:r><w:rPr>{size}</w:rPr><m:t>b</m:t>" in xml
    assert f"<m:f><m:fPr><m:ctrlPr><w:rPr>{size}</w:rPr></m:ctrlPr></m:fPr><m:num>" in xml


def test_math_follows_a_paragraph_that_sets_its_own_size() -> None:
    sized = '<w:r><w:rPr><w:b/><w:sz w:val="18"/></w:rPr><w:t>Note</w:t></w:r>'
    xml, _ = layout(f"<w:p>{sized}{FRACTION}</w:p>", body_size=24)
    assert 'w:val="24"' not in xml
    assert xml.count('<w:sz w:val="18"/><w:szCs w:val="18"/>') == 4  # mark, 2 math runs, ctrl
    assert sized in xml  # the text run itself is left as it was


def test_math_run_sizes_go_before_later_run_properties() -> None:
    run = '<m:r><w:rPr><w:i/><w:lang w:val="en-US"/></w:rPr><m:t>x</m:t></m:r>'
    xml, _ = layout(f"<w:p><m:oMath>{run}</m:oMath></w:p>")
    assert '<w:i/><w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="en-US"/>' in xml


def test_paragraphs_without_math_keep_their_size() -> None:
    xml, stats = layout(para("No math here."))
    assert stats.math == 0 and "w:sz" not in xml


# ── the whole pass ───────────────────────────────────────────────────────────

def test_the_pass_is_idempotent() -> None:
    body = (para("Results", '<w:pStyle w:val="Heading1"/>') + IMAGE + para("Figure 1: A.")
            + f"<w:tbl>{row('h')}{row('v')}</w:tbl><w:p>{FRACTION}</w:p>")
    once, first = docx_layout.layout_document_xml(document(body), 22)
    twice, second = docx_layout.layout_document_xml(once, 22)
    assert once == twice and first == second


@pytest.mark.parametrize("size", [0, -2, 11.5, "22", True])
def test_layout_docx_wants_a_positive_half_point_size(tmp_path: Path, size) -> None:
    with pytest.raises(ValueError, match="fontSizes.body"):
        docx_layout.layout_docx(tmp_path / "missing.docx", size)


# ── in the Word build ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def template_project(tmp_path_factory) -> Path:
    """A project made by `init` from the bundled template (no skill)."""
    dest = tmp_path_factory.mktemp("layout") / "proj"
    ip.create_project(dest, ip.Answers(
        slug="proj", title="Demo", author="Ada", email="ada@example.org",
        description="Demo", starters="both",
    ), skills=False)
    return dest


def members(path: Path) -> dict[str, bytes]:
    with ZipFile(path) as z:
        return {info.filename: z.read(info) for info in z.infolist()}


def build(root: Path, doc: str, **kwargs) -> tuple[WordBuilder, dict[str, bytes]]:
    builder = WordBuilder(root_dir=root, version=doc, **kwargs)
    assert builder.build()
    return builder, members(builder.out_docx)


@pytest.mark.parametrize("doc", ["manuscript", "proposal"])
def test_word_lays_out_what_it_builds(template_project: Path, doc: str, tmp_path: Path) -> None:
    raw_builder, raw = build(template_project, doc, layout=False)
    assert raw_builder.layout_stats is None
    assert b"cantSplit" not in raw["word/document.xml"]
    shutil.copy(raw_builder.out_docx, tmp_path / "raw.docx")

    builder, laid_out = build(template_project, doc)
    assert builder.layout_stats.rows > 0 and builder.layout_stats.figures == 1
    assert b"cantSplit" in laid_out["word/document.xml"]
    # Only document.xml changes, and it is what the pass makes of the raw build.
    assert laid_out.keys() == raw.keys()
    assert {k for k in raw if raw[k] != laid_out[k]} == {"word/document.xml"}
    body = yaml.safe_load((builder.out_dir / "styles.yaml").read_text())["fontSizes"]["body"]
    stats = docx_layout.layout_docx(tmp_path / "raw.docx", body)
    assert members(tmp_path / "raw.docx") == laid_out and stats == builder.layout_stats


def test_cli_no_layout(template_project: Path, capsys) -> None:
    docx = template_project / "out/manuscript/word/main.docx"
    args = ["word", "--root", str(template_project), "-V", "manuscript"]
    assert main(args) == 0
    assert re.search(r"Word layout: \d+ table rows", capsys.readouterr().out)
    assert b"cantSplit" in members(docx)["word/document.xml"]
    assert main([*args, "--no-layout"]) == 0
    assert "Word layout: skipped (--no-layout)" in capsys.readouterr().out
    assert b"cantSplit" not in members(docx)["word/document.xml"]


LEGACY = Path(ip.__file__).parent / "template" / "scripts" / "finalize_word_layout.py"


@pytest.mark.skipif(not LEGACY.is_file(), reason="the bundled template no longer ships the script")
def test_an_old_projects_script_changes_nothing(template_project: Path) -> None:
    """`make word` in an older project runs scripts/finalize_word_layout.py
    after `document-sanity word`: on the laid-out .docx it's a no-op."""
    builder, before = build(template_project, "manuscript")
    proc = subprocess.run(
        [sys.executable, str(LEGACY), "--root", str(template_project), "--version", "manuscript"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert re.search(r"\d+ table rows, 1 figure/caption pairs, \d+ math paragraphs", proc.stdout)
    assert members(builder.out_docx) == before
