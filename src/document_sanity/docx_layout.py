"""Pagination and equation sizing for the Word build's finished .docx.

`WordBuilder.build()` runs this over `out/<doc>/word/main.docx` after saving
it (`document-sanity word --no-layout` skips it):

- table rows don't split across pages, and a table's first row repeats as
  its header on every page (and keeps with the row after it);
- headings keep with the paragraph that follows them, and don't split;
- a figure's image keeps with its caption, and the caption doesn't split;
- native equations (OMML) take their paragraph's font size, which is the
  body size unless the paragraph sets its own, instead of Word's default.

Only word/document.xml changes; every other ZIP member (media, styles,
headers, footers) is copied as is. The pass is idempotent, so running it
again on its own output, as a project's old `scripts/finalize_word_layout.py`
does after `make word`, changes nothing.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from xml.dom import Node, minidom
from zipfile import ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"

# These OMML structures permit a final ctrlPr child in their property element.
MATH_STRUCTURES = {
    "acc", "bar", "borderBox", "box", "d", "eqArr", "f", "func",
    "groupChr", "limLow", "limUpp", "m", "nary", "phant", "rad",
    "sPre", "sSub", "sSubSup", "sSup",
}


@dataclass
class LayoutStats:
    rows: int = 0
    figures: int = 0
    math: int = 0

    def __str__(self) -> str:
        return (f"{self.rows} table rows, {self.figures} figure/caption pairs, "
                f"{self.math} math paragraphs")


def _children(element: minidom.Element, name: str) -> list[minidom.Element]:
    return [
        node for node in element.childNodes
        if node.nodeType == Node.ELEMENT_NODE
        and node.namespaceURI == W and node.localName == name
    ]


def _properties(element: minidom.Element, name: str) -> minidom.Element:
    existing = _children(element, name)
    if existing:
        return existing[0]
    result = element.ownerDocument.createElementNS(W, f"w:{name}")
    # A row's optional table-property exceptions precede its row properties.
    exceptions = _children(element, "tblPrEx") if name == "trPr" else []
    before = exceptions[0].nextSibling if exceptions else element.firstChild
    element.insertBefore(result, before)
    return result


def _enable(properties_node: minidom.Element, name: str) -> None:
    existing = _children(properties_node, name)
    if existing:
        existing[0].setAttributeNS(W, "w:val", "1")
        return
    prop = properties_node.ownerDocument.createElementNS(W, f"w:{name}")
    prop.setAttributeNS(W, "w:val", "1")
    if properties_node.localName == "pPr":
        # Keep the schema order: pStyle, keepNext, keepLines, other properties.
        predecessors = {"pStyle"}
        if name == "keepLines":
            predecessors.add("keepNext")
        before = next((
            node for node in properties_node.childNodes
            if node.nodeType == Node.ELEMENT_NODE
            and node.localName not in predecessors
        ), None)
        properties_node.insertBefore(prop, before)
    else:
        properties_node.appendChild(prop)


def _run_properties(element: minidom.Element) -> minidom.Element:
    existing = _children(element, "rPr")
    if existing:
        return existing[0]
    result = element.ownerDocument.createElementNS(W, "w:rPr")
    if element.namespaceURI == W and element.localName == "pPr":
        # Paragraph-mark formatting follows ordinary paragraph properties.
        before = next((
            node for node in element.childNodes
            if node.nodeType == Node.ELEMENT_NODE
            and node.namespaceURI == W and node.localName in {"sectPr", "pPrChange"}
        ), None)
    elif element.namespaceURI == M and element.localName == "r":
        # An OMML run is m:rPr?, w:rPr?, m:t.
        math_props = [node for node in element.childNodes
                      if node.nodeType == Node.ELEMENT_NODE
                      and node.namespaceURI == M and node.localName == "rPr"]
        before = math_props[0].nextSibling if math_props else element.firstChild
    else:
        before = element.firstChild
    element.insertBefore(result, before)
    return result


def _set_font_size(element: minidom.Element, half_points: int) -> None:
    rpr = _run_properties(element)
    # w:sz and w:szCs precede these later run properties in OOXML.
    following = {
        "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign",
        "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish",
        "oMath", "rPrChange",
    }
    for name in ("sz", "szCs"):
        existing = _children(rpr, name)
        prop = existing[0] if existing else element.ownerDocument.createElementNS(W, f"w:{name}")
        prop.setAttributeNS(W, "w:val", str(half_points))
        if not existing:
            later = following | ({"szCs"} if name == "sz" else set())
            before = next((
                node for node in rpr.childNodes
                if node.nodeType == Node.ELEMENT_NODE
                and node.namespaceURI == W and node.localName in later
            ), None)
            rpr.insertBefore(prop, before)


def _paragraph_font_size(paragraph: minidom.Element, body_size: int) -> int:
    # The builder sizes heading/caption text directly, rather than by style.
    candidates = _children(paragraph, "pPr") + _children(paragraph, "r")
    for candidate in candidates:
        for rpr in _children(candidate, "rPr"):
            sizes = _children(rpr, "sz")
            if sizes:
                value = sizes[0].getAttributeNS(W, "val")
                if value.isdecimal() and int(value) > 0:
                    return int(value)
    return body_size


def _size_math(paragraph: minidom.Element, body_size: int) -> bool:
    math_runs = paragraph.getElementsByTagNameNS(M, "r")
    if not math_runs:
        return False
    size = _paragraph_font_size(paragraph, body_size)
    _set_font_size(_properties(paragraph, "pPr"), size)
    for run in math_runs:
        _set_font_size(run, size)
    # Operators and delimiters use control properties instead of text runs.
    for structure in list(paragraph.getElementsByTagNameNS(M, "*")):
        if structure.localName not in MATH_STRUCTURES:
            continue
        prop_name = structure.localName + "Pr"
        existing = [node for node in structure.childNodes
                    if node.nodeType == Node.ELEMENT_NODE
                    and node.namespaceURI == M and node.localName == prop_name]
        if existing:
            math_props = existing[0]
        else:
            math_props = structure.ownerDocument.createElementNS(M, "m:" + prop_name)
            structure.insertBefore(math_props, structure.firstChild)
        controls = [node for node in math_props.childNodes
                    if node.nodeType == Node.ELEMENT_NODE
                    and node.namespaceURI == M and node.localName == "ctrlPr"]
        if controls:
            control = controls[0]
        else:
            control = structure.ownerDocument.createElementNS(M, "m:ctrlPr")
            math_props.appendChild(control)
        _set_font_size(control, size)
    return True


def layout_document_xml(xml: bytes, body_size: int) -> tuple[bytes, LayoutStats]:
    """word/document.xml with the layout pass applied, and what it touched."""
    document = minidom.parseString(xml)
    body = document.getElementsByTagNameNS(W, "body")[0]
    stats = LayoutStats()
    for table in body.getElementsByTagNameNS(W, "tbl"):
        rows = _children(table, "tr")
        for row in rows:
            _enable(_properties(row, "trPr"), "cantSplit")
            stats.rows += 1
        if rows:
            _enable(_properties(rows[0], "trPr"), "tblHeader")
            for paragraph in rows[0].getElementsByTagNameNS(W, "p"):
                _enable(_properties(paragraph, "pPr"), "keepNext")

    for paragraph in body.getElementsByTagNameNS(W, "p"):
        stats.math += _size_math(paragraph, body_size)
        styles = paragraph.getElementsByTagNameNS(W, "pStyle")
        if any(re.fullmatch(r"Heading[1-9]", style.getAttributeNS(W, "val")) for style in styles):
            _enable(_properties(paragraph, "pPr"), "keepNext")
            _enable(_properties(paragraph, "pPr"), "keepLines")
        if not (paragraph.getElementsByTagNameNS(W, "drawing")
                or paragraph.getElementsByTagNameNS(W, "pict")):
            continue
        # The builder emits an image paragraph immediately before its caption.
        caption = paragraph.nextSibling
        while caption is not None and caption.nodeType != Node.ELEMENT_NODE:
            caption = caption.nextSibling
        if caption is None or caption.namespaceURI != W or caption.localName != "p":
            continue
        text = "".join(
            node.firstChild.data if node.firstChild is not None else ""
            for node in caption.getElementsByTagNameNS(W, "t")
        )
        styles = caption.getElementsByTagNameNS(W, "pStyle")
        is_caption = any(style.getAttributeNS(W, "val") == "Caption" for style in styles)
        if not is_caption and not re.match(r"^Figure\s+\d+[.:]", text):
            continue
        _enable(_properties(paragraph, "pPr"), "keepNext")
        _enable(_properties(caption, "pPr"), "keepLines")
        stats.figures += 1

    return document.toxml(encoding="UTF-8"), stats


def layout_docx(path: Path, body_size: int) -> LayoutStats:
    """Apply the layout pass to the .docx at `path`, in place.

    `body_size` is the body font size in half-points (styles fontSizes.body).
    """
    if isinstance(body_size, bool) or not isinstance(body_size, int) or body_size <= 0:
        raise ValueError(
            f"fontSizes.body must be a positive integer in half-points, not {body_size!r}"
        )
    with ZipFile(path) as source:
        xml, stats = layout_document_xml(source.read("word/document.xml"), body_size)
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".docx", delete=False) as tmp:
            temporary = Path(tmp.name)
        try:
            with ZipFile(temporary, "w") as output:
                output.comment = source.comment
                for member in source.infolist():
                    data = xml if member.filename == "word/document.xml" else source.read(member)
                    output.writestr(member, data)
            temporary.chmod(path.stat().st_mode)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return stats
