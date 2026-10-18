"""LaTeX math -> Office Math (OMML) for the Word build, through pandoc.

Word renders equations only as Office Math Markup (OMML). Pandoc's TeX math
reader (texmath) writes OMML natively, so every math snippet of a section goes
through one pandoc run (markdown in, docx out), and each paragraph's
<m:oMathPara> (display) or <m:oMath> (inline) is read back in order.

Pandoc is an optional external tool. Without it, or when a snippet does not
convert, `convert` returns None for that snippet and the caller falls back to
the LaTeX source as plain text, as the Word build did before.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

Snippet = tuple[str, bool]  # (LaTeX source without delimiters, display?)

_PARA_RE = re.compile(r"<w:p[ >][\s\S]*?</w:p>")
_MATH_PARA_RE = re.compile(r"<m:oMathPara>[\s\S]*?</m:oMathPara>")
_MATH_RE = re.compile(r"<m:oMath>[\s\S]*?</m:oMath>")

# Display math: $$ ... $$ (one or more lines). Inline math follows pandoc's
# rules so prose dollars stay prose: no backslash-escaped $, no space just
# inside either delimiter, and no digit right after the closing $ ("$5 and $6").
DISPLAY_RE = re.compile(r"\$\$([\s\S]+?)\$\$")
INLINE_RE = re.compile(r"(?<![\\$])\$(?![$\s])([^$\n]+?)(?<![\s\\])\$(?![$\d])")


def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def normalize(tex: str) -> str:
    """LaTeX as pandoc's math reader wants it: align -> aligned, no labels or
    numbering commands, no blank lines (they would end the markdown paragraph)."""
    tex = tex.strip()
    tex = re.sub(r"\\begin\{(align|gather|multline|eqnarray)\*?\}", r"\\begin{aligned}", tex)
    tex = re.sub(r"\\end\{(align|gather|multline|eqnarray)\*?\}", r"\\end{aligned}", tex)
    tex = re.sub(r"\\begin\{equation\*?\}|\\end\{equation\*?\}", "", tex)
    tex = re.sub(r"\\label\{[^{}]*\}", "", tex)
    tex = tex.replace(r"\nonumber", "").replace(r"\notag", "")
    tex = re.sub(r"\n\s*\n", "\n", tex)
    return tex.strip()


def _markdown(snippets: list[Snippet]) -> str:
    paras = []
    for tex, display in snippets:
        t = normalize(tex)
        paras.append(f"$$\n{t}\n$$" if display else f"${t}$")
    return "\n\n".join(paras) + "\n"


def _run_pandoc(md: str) -> Optional[list[str]]:
    """Paragraph XML of the docx pandoc writes for `md`, or None on failure."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "math.docx"
        try:
            proc = subprocess.run(
                ["pandoc", "-f", "markdown", "-t", "docx", "-o", str(out)],
                input=md, text=True, capture_output=True, timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0 or not out.exists():
            return None
        with zipfile.ZipFile(out) as z:
            xml = z.read("word/document.xml").decode("utf-8")
    body = re.search(r"<w:body>([\s\S]*)</w:body>", xml)
    return _PARA_RE.findall(body.group(1)) if body else None


def _extract(para: str, display: bool) -> Optional[str]:
    m = (_MATH_PARA_RE if display else _MATH_RE).search(para)
    if m:
        return m.group(0)
    if display:  # pandoc may write display math as a bare oMath; wrap it
        m = _MATH_RE.search(para)
        if m:
            return f"<m:oMathPara>{m.group(0)}</m:oMathPara>"
    return None


def convert(snippets: list[Snippet]) -> list[Optional[str]]:
    """OMML for each (latex, display) snippet, in order; None where it failed.

    One pandoc run for the whole batch. If the output does not line up one
    paragraph per snippet (a snippet pandoc could not read as math can split
    or merge paragraphs), each snippet is converted on its own instead.
    """
    if not snippets:
        return []
    if not pandoc_available():
        return [None] * len(snippets)
    paras = _run_pandoc(_markdown(snippets))
    if paras is not None and len(paras) == len(snippets):
        return [_extract(p, d) for p, (_, d) in zip(paras, snippets)]
    out: list[Optional[str]] = []
    for snip in snippets:
        one = _run_pandoc(_markdown([snip]))
        out.append(_extract(one[0], snip[1]) if one and len(one) == 1 else None)
    return out


class MathCache:
    """OMML by (latex, display), filled in batches; misses convert on demand."""

    def __init__(self) -> None:
        self._omml: dict[Snippet, Optional[str]] = {}

    def prefetch(self, snippets: list[Snippet]) -> None:
        todo = list(dict.fromkeys(s for s in snippets if s not in self._omml))
        for snip, omml in zip(todo, convert(todo)):
            self._omml[snip] = omml

    def get(self, tex: str, display: bool) -> Optional[str]:
        key = (tex, display)
        if key not in self._omml:
            self.prefetch([key])
        return self._omml[key]


def scan(text: str) -> list[Snippet]:
    """Every display and inline math snippet in markdown text, display first."""
    found: list[Snippet] = [(m.group(1), True) for m in DISPLAY_RE.finditer(text)]
    rest = DISPLAY_RE.sub(" ", text)
    found += [(m.group(1), False) for m in INLINE_RE.finditer(rest)]
    return found
