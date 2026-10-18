"""Apply pagination and math sizing to document-sanity's Word output.

Only pagination and native-math font properties in word/document.xml change.
All other ZIP members, including media, styles, headers and footers, are kept.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import tempfile
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


def children(element: minidom.Element, name: str) -> list[minidom.Element]:
    return [
        node for node in element.childNodes
        if node.nodeType == Node.ELEMENT_NODE
        and node.namespaceURI == W and node.localName == name
    ]


def properties(element: minidom.Element, name: str) -> minidom.Element:
    existing = children(element, name)
    if existing:
        return existing[0]
    result = element.ownerDocument.createElementNS(W, f"w:{name}")
    # A row's optional table-property exceptions precede its row properties.
    exceptions = children(element, "tblPrEx") if name == "trPr" else []
    before = exceptions[0].nextSibling if exceptions else element.firstChild
    element.insertBefore(result, before)
    return result


def enable(properties_node: minidom.Element, name: str) -> None:
    existing = children(properties_node, name)
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


def run_properties(element: minidom.Element) -> minidom.Element:
    existing = children(element, "rPr")
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


def set_font_size(element: minidom.Element, half_points: int) -> None:
    rpr = run_properties(element)
    # w:sz and w:szCs precede these later run properties in OOXML.
    following = {
        "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign",
        "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish",
        "oMath", "rPrChange",
    }
    for name in ("sz", "szCs"):
        existing = children(rpr, name)
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


def paragraph_font_size(paragraph: minidom.Element, body_size: int) -> int:
    # The exporter sizes heading/caption text directly, rather than by style.
    candidates = children(paragraph, "pPr") + children(paragraph, "r")
    for candidate in candidates:
        for rpr in children(candidate, "rPr"):
            sizes = children(rpr, "sz")
            if sizes:
                value = sizes[0].getAttributeNS(W, "val")
                if value.isdecimal() and int(value) > 0:
                    return int(value)
    return body_size


def size_math(paragraph: minidom.Element, body_size: int) -> bool:
    math_runs = paragraph.getElementsByTagNameNS(M, "r")
    if not math_runs:
        return False
    size = paragraph_font_size(paragraph, body_size)
    set_font_size(properties(paragraph, "pPr"), size)
    for run in math_runs:
        set_font_size(run, size)
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
        set_font_size(control, size)
    return True


def finalize_xml(xml: bytes, body_size: int) -> tuple[bytes, int, int, int]:
    document = minidom.parseString(xml)
    body = document.getElementsByTagNameNS(W, "body")[0]
    row_count = 0
    for table in body.getElementsByTagNameNS(W, "tbl"):
        rows = children(table, "tr")
        for row in rows:
            enable(properties(row, "trPr"), "cantSplit")
            row_count += 1
        if rows:
            enable(properties(rows[0], "trPr"), "tblHeader")
            for paragraph in rows[0].getElementsByTagNameNS(W, "p"):
                enable(properties(paragraph, "pPr"), "keepNext")

    figure_count = 0
    math_count = 0
    for paragraph in body.getElementsByTagNameNS(W, "p"):
        math_count += size_math(paragraph, body_size)
        styles = paragraph.getElementsByTagNameNS(W, "pStyle")
        if any(re.fullmatch(r"Heading[1-9]", style.getAttributeNS(W, "val")) for style in styles):
            enable(properties(paragraph, "pPr"), "keepNext")
            enable(properties(paragraph, "pPr"), "keepLines")
        if not (paragraph.getElementsByTagNameNS(W, "drawing")
                or paragraph.getElementsByTagNameNS(W, "pict")):
            continue
        # The exporter emits an image paragraph immediately before its caption.
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
        enable(properties(paragraph, "pPr"), "keepNext")
        enable(properties(caption, "pPr"), "keepLines")
        figure_count += 1

    return document.toxml(encoding="UTF-8"), row_count, figure_count, math_count


def finalize(path: Path, body_size: int) -> tuple[int, int, int]:
    with ZipFile(path) as source:
        xml, rows, figures, math = finalize_xml(source.read("word/document.xml"), body_size)
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
    return rows, figures, math


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--version", help="Same version selection as document-sanity word")
    args = parser.parse_args()
    version = args.version
    if not version:
        from document_sanity.docx_builder import find_latest_version

        version = find_latest_version(args.root)
    path = args.root / "out" / version / "word" / "main.docx"
    # PyYAML is already a dependency of the exporter that writes this file.
    import yaml

    styles = yaml.safe_load(path.with_name("styles.yaml").read_text(encoding="utf-8"))
    body_size = styles["fontSizes"]["body"]
    if isinstance(body_size, bool) or not isinstance(body_size, int) or body_size <= 0:
        raise ValueError("Resolved fontSizes.body must be a positive integer in half-points")
    rows, figures, math = finalize(path, body_size)
    print(f"  Word layout: {rows} table rows, {figures} figure/caption pairs, {math} math paragraphs ({version})")


if __name__ == "__main__":
    main()
