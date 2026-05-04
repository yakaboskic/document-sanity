#!/usr/bin/env python3
"""
OOXML (WordprocessingML) string helpers.

Every function here produces a plain XML string. No DOM, no schema validation —
just concatenation. This mirrors word-builder/src/xml.ts so the output shape is
identical and template docs written by either tool look the same.

Terminology reminder:
  - size: half-points (22 = 11pt)
  - spacing before/after: twentieths of a point (200 = 10pt)
  - color: hex without '#'
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# ---- low-level escape ------------------------------------------------------

def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---- run / paragraph types -------------------------------------------------

@dataclass
class RichText:
    """A single run with inline formatting. Mirrors word-builder's RichText."""
    text: str
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    color: Optional[str] = None
    font: Optional[str] = None
    size: Optional[int] = None
    rstyle: Optional[str] = None  # character-style id (e.g. "Code")


def _pick(*vals):
    """First non-None value wins."""
    for v in vals:
        if v is not None:
            return v
    return None


def create_run_props(
    *,
    font: Optional[str] = None,
    size: Optional[int] = None,
    color: Optional[str] = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    rstyle: Optional[str] = None,
) -> str:
    parts: list[str] = []
    # rStyle goes first per OOXML schema order so Word resolves the
    # character style before applying any direct overrides on this run.
    if rstyle:
        parts.append(f'<w:rStyle w:val="{rstyle}"/>')
    if font:
        parts.append(f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>')
    if size:
        parts.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    if color:
        parts.append(f'<w:color w:val="{color}"/>')
    if bold:
        parts.append("<w:b/>")
    if italic:
        parts.append("<w:i/>")
    if not parts:
        return ""
    return f"<w:rPr>{''.join(parts)}</w:rPr>"


def create_run(text: str, **run_props: Any) -> str:
    """A <w:r> with optional rPr + a preserve-space <w:t>."""
    rpr = create_run_props(**run_props)
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape_xml(text)}</w:t></w:r>'


def create_para_props(
    *,
    style: Optional[str] = None,
    alignment: Optional[str] = None,
    spacing_before: Optional[int] = None,
    spacing_after: Optional[int] = None,
    bullet: bool = False,
    numbered: bool = False,
    suppress_numbering: bool = False,
) -> str:
    parts: list[str] = []
    if style:
        parts.append(f'<w:pStyle w:val="{style}"/>')
    if alignment:
        parts.append(f'<w:jc w:val="{alignment}"/>')
    if spacing_before is not None or spacing_after is not None:
        before = f' w:before="{spacing_before}"' if spacing_before is not None else ""
        after = f' w:after="{spacing_after}"' if spacing_after is not None else ""
        parts.append(f"<w:spacing{before}{after}/>")
    if bullet:
        parts.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')
    elif numbered:
        parts.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>')
    elif suppress_numbering:
        parts.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>')
    if not parts:
        return ""
    return f"<w:pPr>{''.join(parts)}</w:pPr>"


def create_paragraph(
    content: str | list[RichText],
    *,
    # run-level defaults (apply to all runs unless the RichText part overrides)
    font: Optional[str] = None,
    size: Optional[int] = None,
    color: Optional[str] = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    # paragraph-level
    style: Optional[str] = None,
    alignment: Optional[str] = None,
    spacing_before: Optional[int] = None,
    spacing_after: Optional[int] = None,
    bullet: bool = False,
    numbered: bool = False,
    suppress_numbering: bool = False,
) -> str:
    p_pr = create_para_props(
        style=style,
        alignment=alignment,
        spacing_before=spacing_before,
        spacing_after=spacing_after,
        bullet=bullet,
        numbered=numbered,
        suppress_numbering=suppress_numbering,
    )
    if isinstance(content, str):
        runs = create_run(
            content, font=font, size=size, color=color, bold=bold, italic=italic
        )
    else:
        parts: list[str] = []
        for part in content:
            parts.append(
                create_run(
                    part.text,
                    font=_pick(part.font, font),
                    size=_pick(part.size, size),
                    color=_pick(part.color, color),
                    bold=_pick(part.bold, bold),
                    italic=_pick(part.italic, italic),
                    rstyle=part.rstyle,
                )
            )
        runs = "".join(parts)
    return f"<w:p>{p_pr}{runs}</w:p>"


def create_page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


# ---- tables ----------------------------------------------------------------

def create_table(
    headers: list[str],
    rows: list[list[str]],
    styles: dict[str, Any],
    style_name: str = "default",
) -> str:
    tbl_style = styles["tableStyles"][style_name]

    header_rpr = (
        f'<w:rFonts w:ascii="{tbl_style["headerFont"]}" w:hAnsi="{tbl_style["headerFont"]}"/>'
        f'<w:sz w:val="{tbl_style["headerSize"]}"/><w:szCs w:val="{tbl_style["headerSize"]}"/>'
        f'<w:color w:val="{tbl_style["headerTextColor"]}"/>'
        + ("<w:b/>" if tbl_style["headerBold"] else "")
    )
    body_rpr = (
        f'<w:rFonts w:ascii="{tbl_style["bodyFont"]}" w:hAnsi="{tbl_style["bodyFont"]}"/>'
        f'<w:sz w:val="{tbl_style["bodySize"]}"/><w:szCs w:val="{tbl_style["bodySize"]}"/>'
        f'<w:color w:val="{tbl_style["bodyTextColor"]}"/>'
    )

    header_cells = "".join(
        f'<w:tc><w:tcPr><w:shd w:val="clear" w:fill="{tbl_style["headerBackground"]}"/></w:tcPr>'
        f'<w:p><w:r><w:rPr>{header_rpr}</w:rPr><w:t>{escape_xml(h)}</w:t></w:r></w:p></w:tc>'
        for h in headers
    )
    header_row = f"<w:tr>{header_cells}</w:tr>"

    data_rows_parts: list[str] = []
    for idx, row in enumerate(rows):
        fill = tbl_style["rowEven"] if idx % 2 == 0 else tbl_style["rowOdd"]
        cells = "".join(
            f'<w:tc><w:tcPr><w:shd w:val="clear" w:fill="{fill}"/></w:tcPr>'
            f'<w:p><w:r><w:rPr>{body_rpr}</w:rPr><w:t>{escape_xml(cell)}</w:t></w:r></w:p></w:tc>'
            for cell in row
        )
        data_rows_parts.append(f"<w:tr>{cells}</w:tr>")
    data_rows = "".join(data_rows_parts)

    sz = tbl_style["borderWidth"]
    border = tbl_style["border"]
    borders = (
        f'<w:top w:val="single" w:sz="{sz}" w:color="{border}"/>'
        f'<w:left w:val="single" w:sz="{sz}" w:color="{border}"/>'
        f'<w:bottom w:val="single" w:sz="{sz}" w:color="{border}"/>'
        f'<w:right w:val="single" w:sz="{sz}" w:color="{border}"/>'
        f'<w:insideH w:val="single" w:sz="{sz}" w:color="{border}"/>'
        f'<w:insideV w:val="single" w:sz="{sz}" w:color="{border}"/>'
    )

    return (
        "<w:tbl>"
        '<w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
        f"<w:tblBorders>{borders}</w:tblBorders></w:tblPr>"
        f"{header_row}{data_rows}"
        "</w:tbl>"
    )


# ---- inline image drawing --------------------------------------------------

# OOXML sizes inline drawings in EMUs (English Metric Units).
# 914400 EMU = 1 inch; Word's default print area is ~6 inches wide.
EMU_PER_INCH = 914400


def create_inline_drawing(
    *,
    rel_id: str,
    pic_id: int,
    filename: str,
    width_emu: int,
    height_emu: int,
    alt_text: str = "",
) -> str:
    """An inline `<w:drawing>` referencing a picture via the given relationship id.

    The rel_id must point to an image relationship in
    word/_rels/document.xml.rels; the caller is responsible for creating it.
    """
    safe_alt = escape_xml(alt_text)
    safe_name = escape_xml(filename)
    return (
        "<w:p>"
        '<w:pPr><w:jc w:val="center"/></w:pPr>'
        "<w:r><w:drawing>"
        f'<wp:inline distT="0" distB="0" distL="0" distR="0" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        f'<wp:extent cx="{width_emu}" cy="{height_emu}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{pic_id}" name="Picture {pic_id}" descr="{safe_alt}"/>'
        "<wp:cNvGraphicFramePr>"
        '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'noChangeAspect="1"/>'
        "</wp:cNvGraphicFramePr>"
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        "<pic:nvPicPr>"
        f'<pic:cNvPr id="{pic_id}" name="{safe_name}" descr="{safe_alt}"/>'
        "<pic:cNvPicPr/>"
        "</pic:nvPicPr>"
        "<pic:blipFill>"
        f'<a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'r:embed="{rel_id}"/>'
        '<a:stretch><a:fillRect/></a:stretch>'
        "</pic:blipFill>"
        "<pic:spPr>"
        '<a:xfrm>'
        '<a:off x="0" y="0"/>'
        f'<a:ext cx="{width_emu}" cy="{height_emu}"/>'
        "</a:xfrm>"
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</pic:spPr>"
        "</pic:pic>"
        "</a:graphicData>"
        "</a:graphic>"
        "</wp:inline>"
        "</w:drawing></w:r>"
        "</w:p>"
    )


# ---- numbering.xml (bullets + decimal) -------------------------------------

def create_numbering_xml(styles: dict[str, Any]) -> str:
    bullet = styles["listStyles"]["bullet"]
    num = styles["listStyles"]["numbered"]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml">\n'
        '  <w:abstractNum w:abstractNumId="0">\n'
        '    <w:multiLevelType w:val="hybridMultilevel"/>\n'
        '    <w:lvl w:ilvl="0">\n'
        '      <w:start w:val="1"/>\n'
        '      <w:numFmt w:val="bullet"/>\n'
        '      <w:lvlText w:val="&#8226;"/>\n'
        '      <w:lvlJc w:val="left"/>\n'
        '      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>\n'
        f'      <w:rPr><w:rFonts w:ascii="{bullet["font"]}" w:hAnsi="{bullet["font"]}" w:hint="default"/>'
        f'<w:sz w:val="{bullet["size"]}"/><w:szCs w:val="{bullet["size"]}"/>'
        f'<w:color w:val="{bullet["color"]}"/></w:rPr>\n'
        '    </w:lvl>\n'
        '  </w:abstractNum>\n'
        '  <w:abstractNum w:abstractNumId="1">\n'
        '    <w:multiLevelType w:val="hybridMultilevel"/>\n'
        '    <w:lvl w:ilvl="0">\n'
        '      <w:start w:val="1"/>\n'
        '      <w:numFmt w:val="decimal"/>\n'
        '      <w:lvlText w:val="%1."/>\n'
        '      <w:lvlJc w:val="left"/>\n'
        '      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>\n'
        f'      <w:rPr><w:rFonts w:ascii="{num["font"]}" w:hAnsi="{num["font"]}" w:hint="default"/>'
        f'<w:sz w:val="{num["size"]}"/><w:szCs w:val="{num["size"]}"/>'
        f'<w:color w:val="{num["color"]}"/></w:rPr>\n'
        '    </w:lvl>\n'
        '  </w:abstractNum>\n'
        '  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>\n'
        '  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>\n'
        '</w:numbering>\n'
    )
