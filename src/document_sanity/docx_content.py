#!/usr/bin/env python3
"""
Fluent API for building a Word document body.

Port of word-builder/src/content-builder.ts. Each method appends one or more
paragraphs/tables to an internal list; call .to_xml() for the body fragment.

The builder also holds a registry of images to embed and a list of citation
keys as they are encountered, so the containing TemplateDocument can pack
media files and produce a references section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .docx_xml import (
    RichText,
    create_inline_drawing,
    create_page_break,
    create_paragraph,
    create_table,
    EMU_PER_INCH,
)


@dataclass
class TextStyle:
    """Per-call style override. All fields optional; None means 'use default'."""
    font: Optional[str] = None
    size: Optional[int] = None
    color: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    alignment: Optional[str] = None  # left | center | right | both
    spacing_before: Optional[int] = None
    spacing_after: Optional[int] = None


@dataclass
class PendingImage:
    """Image queued for embedding; resolved by TemplateDocument.save()."""
    rel_id: str                 # rIdN assigned by the template
    pic_id: int                 # monotonic 1..N id used inside <w:drawing>
    source_path: Path
    media_name: str             # e.g. "image1.png" in word/media/
    alt_text: str
    width_emu: int
    height_emu: int


def _or_(a, b):
    return b if a is None else a


class ContentBuilder:
    """Fluent builder for Word document body content."""

    def __init__(self, styles: dict[str, Any]):
        self.styles = styles
        self._items: list[str] = []
        self._images: list[PendingImage] = []
        # Citation keys in order of first appearance; used for numbering.
        self._cite_keys: list[str] = []

    # ---- headings ---------------------------------------------------------

    def title(self, text: str, override: TextStyle | None = None) -> "ContentBuilder":
        o = override or TextStyle()
        s = self.styles
        self._items.append(create_paragraph(
            text,
            alignment=_or_(o.alignment, "center"),
            font=_or_(o.font, s["fonts"]["heading"]),
            size=_or_(o.size, s["fontSizes"]["title"]),
            color=_or_(o.color, s["colors"]["primary"]),
            bold=_or_(o.bold, True),
            italic=o.italic,
            spacing_before=o.spacing_before,
            spacing_after=o.spacing_after,
            suppress_numbering=True,
        ))
        return self

    def subtitle(self, text: str, override: TextStyle | None = None) -> "ContentBuilder":
        o = override or TextStyle()
        s = self.styles
        self._items.append(create_paragraph(
            text,
            alignment=_or_(o.alignment, "center"),
            font=_or_(o.font, s["fonts"]["body"]),
            size=_or_(o.size, s["fontSizes"]["body"] + 6),
            color=_or_(o.color, s["colors"]["textLight"]),
            bold=o.bold,
            italic=o.italic,
            spacing_before=o.spacing_before,
            spacing_after=_or_(o.spacing_after, s["spacing"]["paragraph"]["afterLarge"]),
        ))
        return self

    def _heading(self, text: str, level: int, override: TextStyle | None) -> "ContentBuilder":
        o = override or TextStyle()
        s = self.styles
        size = {1: s["fontSizes"]["h1"], 2: s["fontSizes"]["h2"], 3: s["fontSizes"]["h3"]}[level]
        color = {1: s["colors"]["heading1"], 2: s["colors"]["heading2"], 3: s["colors"]["heading3"]}[level]
        spacing = s["spacing"]["heading"][f"h{level}"]
        self._items.append(create_paragraph(
            text,
            style=f"Heading{level}",
            alignment=o.alignment,
            font=_or_(o.font, s["fonts"]["heading"]),
            size=_or_(o.size, size),
            color=_or_(o.color, color),
            bold=_or_(o.bold, True),
            italic=o.italic,
            spacing_before=_or_(o.spacing_before, spacing["before"]),
            spacing_after=_or_(o.spacing_after, spacing["after"]),
            suppress_numbering=True,
        ))
        return self

    def h1(self, text: str, override: TextStyle | None = None) -> "ContentBuilder":
        return self._heading(text, 1, override)

    def h2(self, text: str, override: TextStyle | None = None) -> "ContentBuilder":
        return self._heading(text, 2, override)

    def h3(self, text: str, override: TextStyle | None = None) -> "ContentBuilder":
        return self._heading(text, 3, override)

    # ---- prose ------------------------------------------------------------

    def p(self, content: str | list[RichText], override: TextStyle | None = None) -> "ContentBuilder":
        o = override or TextStyle()
        s = self.styles
        self._items.append(create_paragraph(
            content,
            alignment=o.alignment,
            font=_or_(o.font, s["fonts"]["body"]),
            size=_or_(o.size, s["fontSizes"]["body"]),
            color=_or_(o.color, s["colors"]["text"]),
            bold=o.bold,
            italic=o.italic,
            spacing_before=o.spacing_before,
            spacing_after=_or_(o.spacing_after, s["spacing"]["paragraph"]["after"]),
        ))
        return self

    def labeled_para(self, label: str, text: str, override: TextStyle | None = None) -> "ContentBuilder":
        return self.p([RichText(text=label, bold=True), RichText(text=text)], override)

    def label(self, text: str, override: TextStyle | None = None) -> "ContentBuilder":
        o = override or TextStyle()
        s = self.styles
        self._items.append(create_paragraph(
            text,
            alignment=o.alignment,
            font=_or_(o.font, s["fonts"]["body"]),
            size=_or_(o.size, s["fontSizes"]["label"]),
            color=_or_(o.color, s["colors"]["text"]),
            bold=_or_(o.bold, True),
            italic=o.italic,
            spacing_before=o.spacing_before,
            spacing_after=_or_(o.spacing_after, s["spacing"]["paragraph"]["afterSmall"]),
        ))
        return self

    # ---- lists ------------------------------------------------------------

    def _list_item(
        self,
        text: str | list[RichText],
        *,
        ordered: bool,
        bold_prefix: Optional[str],
        override: TextStyle | None,
    ) -> "ContentBuilder":
        o = override or TextStyle()
        s = self.styles
        list_style = s["listStyles"]["numbered" if ordered else "bullet"]
        base = dict(
            alignment=o.alignment,
            font=_or_(o.font, list_style["font"]),
            size=_or_(o.size, list_style["size"]),
            color=_or_(o.color, list_style["color"]),
            italic=o.italic,
            spacing_before=o.spacing_before,
            spacing_after=_or_(o.spacing_after, s["spacing"]["paragraph"]["afterSmall"]),
        )
        if ordered:
            base["numbered"] = True
        else:
            base["bullet"] = True
        if bold_prefix and isinstance(text, str):
            content = [RichText(text=bold_prefix, bold=True), RichText(text=text)]
            self._items.append(create_paragraph(content, **base))
        else:
            self._items.append(create_paragraph(text, **base, bold=o.bold))
        return self

    def bullet(
        self,
        text: str | list[RichText],
        bold_prefix: Optional[str] = None,
        override: TextStyle | None = None,
    ) -> "ContentBuilder":
        return self._list_item(text, ordered=False, bold_prefix=bold_prefix, override=override)

    def numbered(
        self,
        text: str | list[RichText],
        bold_prefix: Optional[str] = None,
        override: TextStyle | None = None,
    ) -> "ContentBuilder":
        return self._list_item(text, ordered=True, bold_prefix=bold_prefix, override=override)

    # ---- notes / callouts -------------------------------------------------

    def note(
        self,
        text: str,
        type_: str = "warning",  # warning | info | success | error
        label: str = "Note: ",
        override: TextStyle | None = None,
    ) -> "ContentBuilder":
        o = override or TextStyle()
        s = self.styles
        # Type is used by the original word-builder for background colors;
        # we mirror the italic-Note-prefix rendering for now.
        _ = type_
        self._items.append(create_paragraph(
            [
                RichText(text=label, bold=True, italic=True),
                RichText(text=text, italic=_or_(o.italic, True)),
            ],
            alignment=o.alignment,
            font=_or_(o.font, s["fonts"]["body"]),
            size=_or_(o.size, s["fontSizes"]["body"]),
            color=_or_(o.color, s["colors"]["text"]),
            spacing_before=o.spacing_before,
            spacing_after=_or_(o.spacing_after, s["spacing"]["paragraph"]["after"]),
        ))
        return self

    # ---- figures ----------------------------------------------------------

    def image_placeholder(
        self,
        caption: str,
        description: str,
        override: TextStyle | None = None,
    ) -> "ContentBuilder":
        """Render a caption-only placeholder (no embedded bitmap)."""
        o = override or TextStyle()
        s = self.styles
        self._items.append(create_paragraph(
            f"[{caption}]",
            alignment=_or_(o.alignment, "center"),
            font=_or_(o.font, s["fonts"]["body"]),
            size=_or_(o.size, s["fontSizes"]["body"]),
            color=_or_(o.color, s["colors"]["textLight"]),
            bold=o.bold,
            italic=_or_(o.italic, True),
            spacing_before=o.spacing_before,
            spacing_after=s["spacing"]["paragraph"]["afterSmall"],
        ))
        self._items.append(create_paragraph(
            description,
            alignment="center",
            font=s["fonts"]["body"],
            size=s["fontSizes"]["caption"],
            color=s["colors"]["textMuted"],
            italic=True,
            spacing_after=_or_(o.spacing_after, s["spacing"]["paragraph"]["after"]),
        ))
        return self

    def image(
        self,
        source: Path,
        *,
        caption: Optional[str] = None,
        alt_text: str = "",
        max_width_inches: float = 6.0,
    ) -> "ContentBuilder":
        """Embed an image file inline, centered. Caller supplies a real path.

        The image file is packed into word/media/ by TemplateDocument.save();
        here we only queue a PendingImage and emit the drawing XML.
        """
        width_emu, height_emu = _image_dimensions_emu(source, max_width_inches)
        pic_id = len(self._images) + 1
        rel_id = f"rIdImg{pic_id}"
        media_name = f"image{pic_id}{source.suffix.lower()}"
        self._images.append(PendingImage(
            rel_id=rel_id,
            pic_id=pic_id,
            source_path=source,
            media_name=media_name,
            alt_text=alt_text,
            width_emu=width_emu,
            height_emu=height_emu,
        ))
        self._items.append(create_inline_drawing(
            rel_id=rel_id,
            pic_id=pic_id,
            filename=media_name,
            width_emu=width_emu,
            height_emu=height_emu,
            alt_text=alt_text,
        ))
        if caption:
            s = self.styles
            self._items.append(create_paragraph(
                caption,
                alignment="center",
                font=s["fonts"]["body"],
                size=s["fontSizes"]["caption"],
                color=s["colors"]["textMuted"],
                italic=True,
                spacing_after=s["spacing"]["paragraph"]["after"],
            ))
        return self

    # ---- tables / misc ----------------------------------------------------

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        style_name: str = "default",
    ) -> "ContentBuilder":
        self._items.append(create_table(headers, rows, self.styles, style_name))
        self._items.append(create_paragraph(
            "", spacing_after=self.styles["spacing"]["paragraph"]["after"]
        ))
        return self

    def spacer(self) -> "ContentBuilder":
        self._items.append(create_paragraph(
            "", spacing_after=self.styles["spacing"]["paragraph"]["after"]
        ))
        return self

    def page_break(self) -> "ContentBuilder":
        self._items.append(create_page_break())
        return self

    # ---- citation tracking -----------------------------------------------

    def register_citation(self, key: str) -> int:
        """Assign (or look up) a number for this citation key. Returns 1-based index."""
        if key not in self._cite_keys:
            self._cite_keys.append(key)
        return self._cite_keys.index(key) + 1

    @property
    def citation_keys(self) -> list[str]:
        return list(self._cite_keys)

    @property
    def pending_images(self) -> list[PendingImage]:
        return list(self._images)

    # ---- raw emit --------------------------------------------------------

    def raw(self, xml: str) -> "ContentBuilder":
        """Append a raw XML fragment. Used for rare pass-through cases."""
        self._items.append(xml)
        return self

    def to_xml(self) -> str:
        return "\n".join(self._items)


# ---- image sizing helpers --------------------------------------------------

def _image_dimensions_emu(path: Path, max_width_inches: float) -> tuple[int, int]:
    """Compute (width_emu, height_emu) preserving aspect ratio, capped at max.

    Falls back to a square at max width if Pillow can't open the file.
    """
    try:
        from PIL import Image
        with Image.open(path) as im:
            w_px, h_px = im.size
            dpi = im.info.get("dpi", (96, 96))
            dpi_x = dpi[0] if isinstance(dpi, tuple) else 96
            dpi_y = dpi[1] if isinstance(dpi, tuple) else 96
            w_in = w_px / max(dpi_x, 1)
            h_in = h_px / max(dpi_y, 1)
    except Exception:
        w_in, h_in = max_width_inches, max_width_inches

    if w_in > max_width_inches:
        scale = max_width_inches / w_in
        w_in *= scale
        h_in *= scale
    return int(w_in * EMU_PER_INCH), int(h_in * EMU_PER_INCH)
