#!/usr/bin/env python3
"""
Auto-crop vertical whitespace from figure images during the build.

Ported from pigean-manuscripts/scripts/crop_figure_whitespace.py. Designed for
figures authored at a standardized width (e.g., Canva exports at textwidth):
detects the first and last rows with non-white content and crops away the
top/bottom whitespace while preserving the image's full width. Drop-in
width=\\textwidth usage in LaTeX and `<img>` in HTML then renders cleanly
without hand-tuning heights.

Used by build.py and html_builder.py as a copy-time pass:
    src/<ver>/figures/foo/foo.png  -->  out/.../figures/foo.png  (cropped)

Pillow is a soft dependency — if not installed, we fall back to a plain copy.
PDF cropping additionally requires pdf2image + poppler; skipped silently if
unavailable.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    import numpy as np
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


# File extensions that benefit from raster cropping. Vector formats (.svg, .eps)
# and interactive .html are passed through unchanged.
_RASTER_EXTS = {'.png', '.jpg', '.jpeg'}


def _detect_content_bounds(image_array, padding: int, threshold: int):
    """Return (top, bottom) row indices bounding non-whitespace content."""
    if len(image_array.shape) == 3:
        gray = image_array.mean(axis=2)
    else:
        gray = image_array
    non_white_rows = (gray < threshold).any(axis=1)
    content_rows = non_white_rows.nonzero()[0]
    if len(content_rows) == 0:
        return 0, image_array.shape[0]
    top = max(0, int(content_rows[0]) - padding)
    bottom = min(image_array.shape[0], int(content_rows[-1]) + 1 + padding)
    return top, bottom


def crop_image_file(
    src: Path,
    dest: Path,
    *,
    padding: int = 10,
    threshold: int = 250,
) -> tuple[bool, Optional[str]]:
    """Crop vertical whitespace from src, write to dest.

    Returns (did_crop, info_msg). `did_crop=False` if the file wasn't an image
    we could handle — caller should fall back to plain copy.
    """
    if not _PIL_AVAILABLE:
        return False, 'Pillow not installed'

    ext = src.suffix.lower()
    if ext not in _RASTER_EXTS:
        return False, f'unsupported extension {ext}'

    img = Image.open(src)
    img_array = np.array(img)
    orig_h, orig_w = img_array.shape[0], img_array.shape[1]
    top, bot = _detect_content_bounds(img_array, padding, threshold)
    if top == 0 and bot == orig_h:
        # Nothing to crop — just copy to preserve timestamps
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True, f'{orig_w}x{orig_h} (no whitespace to trim)'
    cropped = img.crop((0, top, orig_w, bot))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dest)
    return True, f'{orig_w}x{orig_h} -> {orig_w}x{bot - top}'


def copy_with_crop(
    src: Path,
    dest: Path,
    *,
    crop: bool = True,
    padding: int = 10,
    threshold: int = 250,
) -> tuple[str, Optional[str]]:
    """Copy src -> dest, cropping whitespace when applicable.

    Returns (mode, info) where mode is one of:
      'cropped'  — content bounds detected and trimmed
      'copied'   — file wasn't an image we crop (vector/html/pdf) or crop=False
      'skipped'  — dest is newer than src (no-op)
    """
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return 'skipped', None
    if crop and _PIL_AVAILABLE and src.suffix.lower() in _RASTER_EXTS:
        did, info = crop_image_file(src, dest, padding=padding, threshold=threshold)
        if did:
            return 'cropped', info
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return 'copied', None


def pillow_available() -> bool:
    return _PIL_AVAILABLE
