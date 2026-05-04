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

        # Extract the <w:body> content.
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

        # Multi-section support: templates may have multiple <w:sectPr> blocks
        # (e.g. title page, TOC, then body). We preserve all pre-sections and
        # only replace the content of the final section.
        sect_prs = list(re.finditer(r"<w:sectPr[\s\S]*?</w:sectPr>", existing))

        if len(sect_prs) >= 2:
            # Keep everything up to and including the second-to-last sectPr
            # (title page + TOC sections), then inject our content before the
            # final sectPr.
            #
            # Section-break sectPr elements sit inside a paragraph:
            #   <w:p><w:pPr><w:sectPr>...</w:sectPr></w:pPr></w:p>
            # We must include the closing </w:pPr></w:p> to keep valid XML.
            last_sect = sect_prs[-1]
            second_last_sect = sect_prs[-2]
            cut_pos = second_last_sect.end()
            # The sectPr lives inside a parent <w:p>. After </w:sectPr> the
            # template may have </w:pPr>, then bookmarks / runs / etc., before
            # the matching </w:p> that closes the paragraph. We must include
            # everything up to and including that </w:p> in the prefix —
            # otherwise the inserted content gets nested inside an unclosed
            # paragraph and the resulting XML is invalid.
            tail = existing[cut_pos:]
            p_close = tail.find("</w:p>")
            if p_close != -1:
                cut_pos += p_close + len("</w:p>")
            prefix = existing[:cut_pos]
            final_sect_pr = last_sect.group(0)
            new_body = (
                f"{body_open}\n{prefix}\n"
                f"{self.content.to_xml()}\n"
                f"{final_sect_pr}\n{body_close}"
            )
        else:
            # Single section: original behaviour.
            sect_pr = sect_prs[0].group(0) if sect_prs else ""
            new_body = (
                f"{body_open}\n{self.content.to_xml()}\n{sect_pr}\n{body_close}"
            )

        new_doc_xml = doc_xml_str.replace(body_match.group(0), new_body)

        # Replace [DOCUMENT TITLE] placeholder in the generated body.
        title = self.config.title or ""
        if title:
            new_doc_xml = new_doc_xml.replace("[DOCUMENT TITLE]", title)

        members["word/document.xml"] = new_doc_xml.encode("utf-8")

        # Replace [DOCUMENT TITLE] in header files too.
        if title:
            for name in list(members.keys()):
                if name.startswith("word/header") and name.endswith(".xml"):
                    hdr = members[name].decode("utf-8")
                    if "[DOCUMENT TITLE]" in hdr:
                        members[name] = hdr.replace(
                            "[DOCUMENT TITLE]", title
                        ).encode("utf-8")

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

        # Find the highest existing image number in the template's media/
        # so we don't overwrite template images (logos, watermarks, etc.).
        max_existing = 0
        for name in members:
            m = re.match(r"word/media/image(\d+)\.", name)
            if m:
                max_existing = max(max_existing, int(m.group(1)))

        rels_name = "word/_rels/document.xml.rels"
        rels = members.get(rels_name, b"").decode("utf-8") or (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            "</Relationships>"
        )

        # Also update the document XML so inline drawings use the new names.
        doc_key = "word/document.xml"
        doc_xml = members[doc_key].decode("utf-8") if doc_key in members else ""

        for img in images:
            # Offset the image number to avoid collisions.
            new_num = max_existing + img.pic_id
            old_media = img.media_name
            new_media = f"image{new_num}{Path(old_media).suffix}"

            media_path = f"word/media/{new_media}"
            members[media_path] = Path(img.source_path).read_bytes()

            # Rewrite references in doc XML from old name to new name.
            if old_media != new_media:
                doc_xml = doc_xml.replace(old_media, new_media)

            # Add a relationship.
            if f'Id="{img.rel_id}"' not in rels:
                rel_frag = (
                    f'<Relationship Id="{img.rel_id}" '
                    f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                    f'Target="media/{new_media}"/>'
                )
                rels = rels.replace("</Relationships>", f"{rel_frag}</Relationships>")

        if doc_xml:
            members[doc_key] = doc_xml.encode("utf-8")
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
