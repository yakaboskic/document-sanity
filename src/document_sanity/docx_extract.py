#!/usr/bin/env python3
"""
Extract a StylesConfig dict from a .docx template.

Port of word-builder/src/extract-styles.ts. A .docx is just a zip; we pull
word/styles.xml (paragraph style definitions, incl. basedOn chains) and
word/theme/theme1.xml (theme accent colors) and map them onto our flat
StylesConfig shape.

The regex-based parsing is identical in intent to the TS version — stay
aligned with it so the same template produces the same JSON from either tool.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .docx_styles import default_styles


@dataclass
class _RawStyle:
    id: str
    name: str
    based_on: Optional[str] = None
    font: Optional[str] = None
    size: Optional[int] = None
    color: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    spacing_before: Optional[int] = None
    spacing_after: Optional[int] = None


@dataclass
class _ResolvedStyle:
    id: str
    name: str
    font: Optional[str] = None
    size: Optional[int] = None
    color: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    spacing_before: Optional[int] = None
    spacing_after: Optional[int] = None


@dataclass
class _DocDefaults:
    font: Optional[str] = None
    size: Optional[int] = None


_SYS_COLOR_FALLBACK = {"windowText": "000000", "window": "FFFFFF"}


def _parse_doc_defaults(styles_xml: str) -> _DocDefaults:
    m = re.search(r"<w:docDefaults>([\s\S]*?)</w:docDefaults>", styles_xml)
    if not m:
        return _DocDefaults()
    body = m.group(1)
    font_m = re.search(r'<w:rFonts[^>]*w:ascii="([^"]+)"', body)
    size_m = re.search(r'<w:sz\s+w:val="(\d+)"', body)
    return _DocDefaults(
        font=font_m.group(1) if font_m else None,
        size=int(size_m.group(1)) if size_m else None,
    )


def _parse_raw_styles(styles_xml: str) -> dict[str, _RawStyle]:
    styles: dict[str, _RawStyle] = {}
    pattern = re.compile(
        r'<w:style\s+w:type="paragraph"[^>]*w:styleId="([^"]+)"[^>]*>([\s\S]*?)</w:style>'
    )
    for match in pattern.finditer(styles_xml):
        sid = match.group(1)
        body = match.group(2)
        raw = _RawStyle(id=sid, name=sid)

        n = re.search(r'<w:name\s+w:val="([^"]+)"', body)
        if n:
            raw.name = n.group(1)

        b = re.search(r'<w:basedOn\s+w:val="([^"]+)"', body)
        if b:
            raw.based_on = b.group(1)

        f = re.search(r'<w:rFonts[^>]*w:ascii="([^"]+)"', body)
        if f:
            raw.font = f.group(1)

        sz = re.search(r'<w:sz\s+w:val="(\d+)"', body)
        if sz:
            raw.size = int(sz.group(1))

        c = re.search(r'<w:color\s+w:val="([^"]+)"', body)
        if c and c.group(1) != "auto":
            raw.color = c.group(1)

        if "<w:b/>" in body or '<w:b w:val="true"' in body:
            raw.bold = True
        if "<w:i/>" in body or '<w:i w:val="true"' in body:
            raw.italic = True

        sb = re.search(r'<w:spacing[^>]*w:before="(\d+)"', body)
        if sb:
            raw.spacing_before = int(sb.group(1))
        sa = re.search(r'<w:spacing[^>]*w:after="(\d+)"', body)
        if sa:
            raw.spacing_after = int(sa.group(1))

        styles[sid] = raw
    return styles


def _resolve_style(
    sid: str,
    raw_styles: dict[str, _RawStyle],
    defaults: _DocDefaults,
    seen: Optional[set[str]] = None,
) -> Optional[_ResolvedStyle]:
    if seen is None:
        seen = set()
    if sid in seen:
        return None
    seen.add(sid)
    raw = raw_styles.get(sid)
    if not raw:
        return None
    parent = _resolve_style(raw.based_on, raw_styles, defaults, seen) if raw.based_on else None
    return _ResolvedStyle(
        id=raw.id,
        name=raw.name,
        font=raw.font or (parent.font if parent else None) or defaults.font,
        size=raw.size or (parent.size if parent else None) or defaults.size,
        color=raw.color or (parent.color if parent else None),
        bold=raw.bold if raw.bold is not None else (parent.bold if parent else None),
        italic=raw.italic if raw.italic is not None else (parent.italic if parent else None),
        spacing_before=raw.spacing_before or (parent.spacing_before if parent else None),
        spacing_after=raw.spacing_after or (parent.spacing_after if parent else None),
    )


def _find_style_id(
    raw_styles: dict[str, _RawStyle], sid: str, alt_name: str
) -> Optional[str]:
    if sid in raw_styles:
        return sid
    lower = alt_name.lower()
    for k, v in raw_styles.items():
        if v.name.lower() == lower:
            return k
    return None


def _parse_theme_colors(theme_xml: str) -> dict[str, str]:
    out: dict[str, str] = {}
    scheme = re.search(r"<a:clrScheme[^>]*>([\s\S]*?)</a:clrScheme>", theme_xml)
    if not scheme:
        return out
    body = scheme.group(1)
    tags = [
        "dk1", "dk2", "lt1", "lt2",
        "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
        "hlink", "folHlink",
    ]
    for tag in tags:
        m = re.search(rf"<a:{tag}>([\s\S]*?)</a:{tag}>", body)
        if not m:
            continue
        inner = m.group(1)
        srgb = re.search(r'<a:srgbClr\s+val="([^"]+)"', inner)
        if srgb:
            out[tag] = srgb.group(1)
            continue
        sys_last = re.search(r'<a:sysClr[^>]*lastClr="([^"]+)"', inner)
        if sys_last:
            out[tag] = sys_last.group(1)
            continue
        sys_val = re.search(r'<a:sysClr[^>]*val="([^"]+)"', inner)
        if sys_val and sys_val.group(1) in _SYS_COLOR_FALLBACK:
            out[tag] = _SYS_COLOR_FALLBACK[sys_val.group(1)]
    return out


def extract_styles(template_path: Path | str) -> dict[str, Any]:
    styles = default_styles()

    with zipfile.ZipFile(template_path, "r") as z:
        theme_xml = _read_member(z, "word/theme/theme1.xml")
        styles_xml = _read_member(z, "word/styles.xml")

    theme_colors = _parse_theme_colors(theme_xml) if theme_xml else {}

    if not styles_xml:
        return styles

    defaults = _parse_doc_defaults(styles_xml)
    raw_styles = _parse_raw_styles(styles_xml)

    def resolve(sid: str, alt: str) -> Optional[_ResolvedStyle]:
        found = _find_style_id(raw_styles, sid, alt)
        return _resolve_style(found, raw_styles, defaults) if found else None

    title = resolve("Title", "Title")
    h1 = resolve("Heading1", "Heading 1")
    h2 = resolve("Heading2", "Heading 2")
    h3 = resolve("Heading3", "Heading 3")
    normal = resolve("Normal", "Normal")

    colors = styles["colors"]
    if theme_colors.get("accent1"):
        colors["primary"] = theme_colors["accent1"]
    if theme_colors.get("accent2"):
        colors["secondary"] = theme_colors["accent2"]
    if theme_colors.get("accent3"):
        colors["accent"] = theme_colors["accent3"]
    if normal and normal.color:
        colors["text"] = normal.color
    elif theme_colors.get("dk1"):
        colors["text"] = theme_colors["dk1"]
    if theme_colors.get("lt1"):
        colors["background"] = theme_colors["lt1"]

    if h1 and h1.color:
        colors["heading1"] = h1.color
    elif theme_colors.get("accent1"):
        colors["heading1"] = theme_colors["accent1"]
    if h2 and h2.color:
        colors["heading2"] = h2.color
    elif theme_colors.get("accent2"):
        colors["heading2"] = theme_colors["accent2"]
    if h3 and h3.color:
        colors["heading3"] = h3.color

    heading_font = (
        (h1.font if h1 else None)
        or (title.font if title else None)
        or (normal.font if normal else None)
        or defaults.font
    )
    body_font = (normal.font if normal else None) or defaults.font
    if heading_font:
        styles["fonts"]["heading"] = heading_font
    if body_font:
        styles["fonts"]["body"] = body_font

    fs = styles["fontSizes"]
    if title and title.size:
        fs["title"] = title.size
    if h1 and h1.size:
        fs["h1"] = h1.size
    if h2 and h2.size:
        fs["h2"] = h2.size
    if h3 and h3.size:
        fs["h3"] = h3.size
    body_size = (normal.size if normal else None) or defaults.size
    if body_size:
        fs["body"] = body_size
        fs["label"] = body_size
        fs["small"] = round(body_size * 0.9)
        fs["caption"] = round(body_size * 0.8)

    sp = styles["spacing"]
    if normal and normal.spacing_after is not None:
        sp["paragraph"]["after"] = normal.spacing_after
    if h1 and h1.spacing_before is not None:
        sp["heading"]["h1"]["before"] = h1.spacing_before
    if h1 and h1.spacing_after is not None:
        sp["heading"]["h1"]["after"] = h1.spacing_after
    if h2 and h2.spacing_before is not None:
        sp["heading"]["h2"]["before"] = h2.spacing_before
    if h2 and h2.spacing_after is not None:
        sp["heading"]["h2"]["after"] = h2.spacing_after
    if h3 and h3.spacing_before is not None:
        sp["heading"]["h3"]["before"] = h3.spacing_before
    if h3 and h3.spacing_after is not None:
        sp["heading"]["h3"]["after"] = h3.spacing_after

    body_font_val = styles["fonts"]["body"]
    body_size_val = styles["fontSizes"]["body"]
    for kind in ("bullet", "numbered"):
        styles["listStyles"][kind]["font"] = body_font_val
        styles["listStyles"][kind]["size"] = body_size_val
        styles["listStyles"][kind]["color"] = styles["colors"]["text"]

    td = styles["tableStyles"]["default"]
    td["headerBackground"] = styles["colors"]["primary"]
    td["headerFont"] = body_font_val
    td["headerSize"] = body_size_val
    td["bodyFont"] = body_font_val
    td["bodySize"] = body_size_val
    td["bodyTextColor"] = styles["colors"]["text"]
    td["rowOdd"] = styles["colors"]["backgroundAlt"]

    ts = styles["tableStyles"]["subtle"]
    ts["headerFont"] = body_font_val
    ts["headerSize"] = body_size_val
    ts["bodyFont"] = body_font_val
    ts["bodySize"] = body_size_val
    ts["bodyTextColor"] = styles["colors"]["text"]
    ts["headerTextColor"] = styles["colors"]["text"]

    return styles


def _read_member(z: zipfile.ZipFile, name: str) -> Optional[str]:
    try:
        return z.read(name).decode("utf-8")
    except KeyError:
        return None
