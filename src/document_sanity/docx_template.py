#!/usr/bin/env python3
"""
Load a template .docx, replace its <w:body> content with what a ContentBuilder
produced, and save to a new file.

Body-preservation model (from word-builder):
  - Everything inside the template's <w:body>...</w:body> is discarded except
    for the final <w:sectPr>, which carries header/footer/margin refs.
  - numbering.xml is rewritten from styles so bullet + numbered lists render.
  - Any pending images from the ContentBuilder are packed into word/media/,
    relationships are added, and [Content_Types].xml picks up png/jpg defaults.

Everything else in the template — theme, styles, headers, footers, the
numbering.xml reference in Content_Types — is left alone.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .docx_content import ContentBuilder, PendingImage
from .docx_xml import create_numbering_xml


_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


@dataclass
class TemplateDocumentConfig:
    template_path: Path
    styles: dict[str, Any]
    title: Optional[str] = None
    date: Optional[str] = None
    author: Optional[str] = None


class TemplateDocument:
    """Wraps a template .docx; owns a ContentBuilder for body composition."""

    def __init__(self, config: TemplateDocumentConfig):
        self.config = config
        self.content = ContentBuilder(config.styles)
        # We defer opening the zip until save() — saves on I/O and lets callers
        # discard a TemplateDocument without penalty.

    # ---- title page convenience ------------------------------------------

    def add_title_page(self) -> "TemplateDocument":
        c = self.content
        c.spacer().spacer().spacer()
        c.title(self.config.title or "Document")
        c.subtitle(self.config.date or "")
        c.spacer().spacer()
        if self.config.author:
            c.labeled_para("Prepared by: ", self.config.author)
        c.page_break()
        return self

    # ---- save ------------------------------------------------------------

    def save(self, output_path: Path | str) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Read template into memory, then write a fresh zip (round-tripping
        # through zipfile is safer than editing a copy in-place).
        with zipfile.ZipFile(self.config.template_path, "r") as zin:
            members = {name: zin.read(name) for name in zin.namelist()}

        doc_xml = members.get("word/document.xml")
        if doc_xml is None:
            raise RuntimeError("template missing word/document.xml")
        doc_xml_str = doc_xml.decode("utf-8")

        # Splice body: keep <w:sectPr> only.
        body_match = re.search(
            r"(<w:body[^>]*>)([\s\S]*?)(</w:body>)", doc_xml_str
        )
        if not body_match:
            raise RuntimeError("template missing <w:body>")
        body_open, existing, body_close = (
            body_match.group(1),
            body_match.group(2),
            body_match.group(3),
        )
        sect_pr_match = re.search(r"<w:sectPr[\s\S]*?</w:sectPr>", existing)
        sect_pr = sect_pr_match.group(0) if sect_pr_match else ""

        new_body = (
            f"{body_open}\n{self.content.to_xml()}\n{sect_pr}\n{body_close}"
        )
        new_doc_xml = doc_xml_str.replace(body_match.group(0), new_body)
        members["word/document.xml"] = new_doc_xml.encode("utf-8")

        # Numbering for bullet + ordered lists.
        members["word/numbering.xml"] = create_numbering_xml(
            self.config.styles
        ).encode("utf-8")

        # Images — add media files and relationships.
        images = self.content.pending_images
        members = self._pack_images(members, images)

        # Content types — ensure numbering and image extensions are declared.
        members = self._ensure_content_types(members, images)

        # Relationships — add numbering rel if absent.
        members = self._ensure_numbering_rel(members)

        # Write out.
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in members.items():
                zout.writestr(name, data)

    # ---- helpers ---------------------------------------------------------

    def _pack_images(
        self,
        members: dict[str, bytes],
        images: list[PendingImage],
    ) -> dict[str, bytes]:
        if not images:
            return members

        rels_name = "word/_rels/document.xml.rels"
        rels = members.get(rels_name, b"").decode("utf-8") or (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            "</Relationships>"
        )

        for img in images:
            # Add the image file itself.
            media_path = f"word/media/{img.media_name}"
            members[media_path] = Path(img.source_path).read_bytes()

            # Add a relationship — target is relative to word/.
            if f'Id="{img.rel_id}"' not in rels:
                rel_frag = (
                    f'<Relationship Id="{img.rel_id}" '
                    f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                    f'Target="media/{img.media_name}"/>'
                )
                rels = rels.replace("</Relationships>", f"{rel_frag}</Relationships>")

        members[rels_name] = rels.encode("utf-8")
        return members

    def _ensure_content_types(
        self,
        members: dict[str, bytes],
        images: list[PendingImage],
    ) -> dict[str, bytes]:
        ct_name = "[Content_Types].xml"
        ct = members.get(ct_name, b"").decode("utf-8")
        if not ct:
            return members

        # Numbering override.
        if "/word/numbering.xml" not in ct:
            ct = ct.replace(
                "</Types>",
                '  <Override PartName="/word/numbering.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
                "\n</Types>",
            )

        # Image Default entries for each extension we packed.
        for ext in {Path(img.media_name).suffix.lower() for img in images}:
            if ext not in _IMAGE_CONTENT_TYPES:
                continue
            bare = ext.lstrip(".")
            if f'Extension="{bare}"' in ct:
                continue
            frag = (
                f'  <Default Extension="{bare}" '
                f'ContentType="{_IMAGE_CONTENT_TYPES[ext]}"/>\n'
            )
            ct = ct.replace("</Types>", f"{frag}</Types>")
        members[ct_name] = ct.encode("utf-8")
        return members

    def _ensure_numbering_rel(
        self, members: dict[str, bytes]
    ) -> dict[str, bytes]:
        rels_name = "word/_rels/document.xml.rels"
        rels = members.get(rels_name, b"").decode("utf-8") or (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            "</Relationships>"
        )
        if "numbering.xml" in rels:
            members[rels_name] = rels.encode("utf-8")
            return members

        max_id = 0
        for m in re.finditer(r'Id="rId(\d+)"', rels):
            max_id = max(max_id, int(m.group(1)))
        new_rid = f"rId{max_id + 1}"
        rel_frag = (
            f'<Relationship Id="{new_rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" '
            f'Target="numbering.xml"/>'
        )
        rels = rels.replace("</Relationships>", f"{rel_frag}</Relationships>")
        members[rels_name] = rels.encode("utf-8")
        return members
