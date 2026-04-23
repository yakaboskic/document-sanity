#!/usr/bin/env python3
"""
Word (.docx) style configuration — mirrors word-builder's StylesConfig.

The shape is deliberately a flat JSON-friendly dict tree so the extracted
styles can be hand-edited between extract and build without touching Python.

Sizes are half-points (22 -> 11pt). Spacing values are twentieths of a point
(200 -> 10pt). Colors are hex strings without '#'.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ---- nested value types ----------------------------------------------------

@dataclass
class ListStyle:
    font: str = "Calibri"
    size: int = 22
    color: str = "000000"


@dataclass
class TableStyle:
    headerBackground: str = "1F4E79"
    headerTextColor: str = "FFFFFF"
    headerFont: str = "Calibri"
    headerSize: int = 22
    headerBold: bool = True
    bodyTextColor: str = "000000"
    bodyFont: str = "Calibri"
    bodySize: int = 22
    rowEven: str = "FFFFFF"
    rowOdd: str = "F2F2F2"
    border: str = "D9D9D9"
    borderWidth: int = 4


@dataclass
class NoteStyle:
    background: str = "FFF3CD"
    borderColor: str = "FFC107"


# ---- defaults --------------------------------------------------------------

DEFAULT_STYLES: dict[str, Any] = {
    "colors": {
        "primary": "1F4E79",
        "secondary": "2E75B6",
        "accent": "5B9BD5",
        "text": "000000",
        "textLight": "666666",
        "textMuted": "999999",
        "background": "FFFFFF",
        "backgroundAlt": "F2F2F2",
        "backgroundMuted": "F5F5F5",
        "border": "D9D9D9",
        "borderLight": "E5E5E5",
        "success": "28A745",
        "warning": "FFC107",
        "warningBg": "FFF3CD",
        "error": "DC3545",
        "info": "17A2B8",
        "heading1": "1F4E79",
        "heading2": "2E75B6",
        "heading3": "000000",
    },
    "fonts": {
        "heading": "Calibri Light",
        "body": "Calibri",
        "mono": "Consolas",
    },
    "fontSizes": {
        "title": 52,
        "h1": 32,
        "h2": 26,
        "h3": 24,
        "body": 22,
        "small": 20,
        "caption": 18,
        "label": 22,
    },
    "spacing": {
        "paragraph": {"after": 200, "afterSmall": 120, "afterLarge": 400},
        "heading": {
            "h1": {"before": 400, "after": 200},
            "h2": {"before": 300, "after": 150},
            "h3": {"before": 200, "after": 100},
        },
        "lineHeight": 276,
        "lineHeightTight": 240,
    },
    "listStyles": {
        "bullet": {"font": "Calibri", "size": 22, "color": "000000"},
        "numbered": {"font": "Calibri", "size": 22, "color": "000000"},
    },
    "tableStyles": {
        "default": asdict(TableStyle()),
        "subtle": asdict(TableStyle(
            headerBackground="F2F2F2",
            headerTextColor="000000",
            headerBold=True,
            rowOdd="FFFFFF",
            border="E5E5E5",
        )),
    },
    "noteStyles": {
        "warning": asdict(NoteStyle()),
        "info": asdict(NoteStyle(background="E7F3FE", borderColor="17A2B8")),
        "success": asdict(NoteStyle(background="D4EDDA", borderColor="28A745")),
        "error": asdict(NoteStyle(background="F8D7DA", borderColor="DC3545")),
    },
}


def default_styles() -> dict[str, Any]:
    """Return a deep-copy of the default styles tree — safe to mutate."""
    return copy.deepcopy(DEFAULT_STYLES)


def load_styles(path: Path | str) -> dict[str, Any]:
    """Load a styles JSON file. Missing keys fall back to defaults via merge."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _deep_merge(default_styles(), data)


def save_styles(path: Path | str, styles: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(styles, f, indent=2)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins at the leaves."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
