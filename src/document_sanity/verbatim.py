#!/usr/bin/env python3
"""
Code every target renders verbatim: inline `code` spans and fenced blocks
other than ```latex.

The builders run regex passes over whole documents (\\cite, \\ref, \\label,
{{VAR}}, HTML comments, image paths). None of them may reach into code, or a
document can't show `\\cite{key}` as syntax. mask_code swaps each piece of
code for a sentinel those passes can't match and unmask_code puts it back;
blank_code spaces it out instead, for scanners that only need to skip it.
Both keep every newline, so line numbers reported in between stay right.

A ```latex fence isn't code here: it's the document's own LaTeX, and its
\\label{}s number the figures and equations.
"""

from __future__ import annotations

import re
from typing import Callable

# From the opening line to the first line starting with the same backticks,
# the way the builders' block loops read a fence.
_FENCE_RE = re.compile(r'^[ \t]*(`{3,})([^\n]*)\n.*?^[ \t]*\1[^\n]*$', re.M | re.S)
_LATEX_INFO_RE = re.compile(r'\s*latex\b')
# One line at most, so a stray backtick can't pair with one paragraphs away.
_INLINE_RE = re.compile(r'(?<!`)`[^`\n]+`(?!`)')
_HELD_RE = re.compile(r'\x0e(\d+)\n*\x0f')


def _sub_code(text: str, repl: Callable[[str], str]) -> str:
    """`text` with repl(code) in place of each inline span and non-LaTeX fence."""
    out: list[str] = []
    pos = 0
    for m in _FENCE_RE.finditer(text):
        out.append(_INLINE_RE.sub(lambda c: repl(c.group(0)), text[pos:m.start()]))
        out.append(m.group(0) if _LATEX_INFO_RE.match(m.group(2)) else repl(m.group(0)))
        pos = m.end()
    out.append(_INLINE_RE.sub(lambda c: repl(c.group(0)), text[pos:]))
    return ''.join(out)


def mask_code(text: str) -> tuple[str, list[str]]:
    """(text with each piece of code held out as a sentinel, the held code)."""
    held: list[str] = []

    def hold(code: str) -> str:
        held.append(code)
        return f'\x0e{len(held) - 1}' + '\n' * code.count('\n') + '\x0f'

    return _sub_code(text, hold), held


def unmask_code(text: str, held: list[str]) -> str:
    """Put mask_code's held code back."""
    return _HELD_RE.sub(lambda m: held[int(m.group(1))], text)


def blank_code(text: str) -> str:
    """`text` with code replaced by spaces, offsets and line breaks kept."""
    return _sub_code(text, lambda code: re.sub(r'[^\n]', ' ', code))
