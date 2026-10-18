from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

PYPROJECT = """\
[project]
name = "paper"
version = "0.1.0"
description = "A small paper"
dependencies = [
    "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.0",
]
"""

MANIFEST = """\
metadata:
  title: "A Small Paper"
  authors:
    - name: "Ada"
sections:
  - docs/intro.md
  - _bibliography
variables:
  N: 42
"""

INTRO = """\
# Introduction

We saw {{N}} things \\cite{smith2020} (Section \\ref{sec:intro}).
<!-- \\label{sec:intro} -->
"""

BIB = "@article{smith2020, title={A thing}, author={Smith, J.}, year={2020}, journal={J}}\n"


@pytest.fixture
def write(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Write {relative path: content} under tmp_path and return tmp_path."""

    def _write(files: dict[str, str]) -> Path:
        for rel, content in files.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return tmp_path

    return _write


@pytest.fixture
def project(write: Callable[[dict[str, str]], Path]) -> Path:
    """A one-document project that builds cleanly (no templates/: built-in LaTeX)."""
    return write({
        "pyproject.toml": PYPROJECT,
        "uv.lock": "",
        "src/paper/manifest.yaml": MANIFEST,
        "src/paper/docs/intro.md": INTRO,
        "src/paper/references.bib": BIB,
    })
