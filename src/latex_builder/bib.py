#!/usr/bin/env python3
"""
Minimal BibTeX parser — just enough to render references in HTML.

Handles:
    @article{key, field = {value}, field = "value", field = value, ... }
with balanced-brace field values and basic LaTeX-in-value unescaping
(\\'{e}, \\~{n}, ``…'', `…', --, ---).

Only fields we need for rendering are extracted: author, title, journal,
booktitle, year, volume, number, pages, doi, url, publisher, editor, month.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BibEntry:
    key: str
    type: str
    fields: dict[str, str] = field(default_factory=dict)


_ENTRY_START_RE = re.compile(r'@(\w+)\s*\{\s*([^,\s}]+)\s*,', re.MULTILINE)


def _find_entry_end(text: str, start: int) -> int:
    """Return the index of the `}` that closes the entry opened just before `start`."""
    depth = 1
    i = start
    in_quote = False
    while i < len(text):
        c = text[i]
        if c == '\\' and i + 1 < len(text):
            i += 2
            continue
        if c == '"' and not in_quote:
            in_quote = True
        elif c == '"' and in_quote:
            in_quote = False
        elif not in_quote:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _parse_fields(body: str) -> dict[str, str]:
    """Parse the `field = value, field = value, ...` part of a bib entry."""
    fields: dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        # Skip whitespace and leading commas
        while i < n and body[i] in ' \t\n,':
            i += 1
        if i >= n:
            break
        # Read field name
        m = re.match(r'([A-Za-z][A-Za-z0-9_-]*)\s*=\s*', body[i:])
        if not m:
            break
        name = m.group(1).lower()
        i += m.end()
        if i >= n:
            break
        # Read value: {...} | "..." | bareword
        if body[i] == '{':
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                c = body[j]
                if c == '\\' and j + 1 < n:
                    j += 2
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                j += 1
            value = body[i + 1: j - 1]
            i = j
        elif body[i] == '"':
            j = i + 1
            while j < n and body[j] != '"':
                if body[j] == '\\' and j + 1 < n:
                    j += 2
                    continue
                j += 1
            value = body[i + 1: j]
            i = j + 1
        else:
            m2 = re.match(r'[^,\s]+', body[i:])
            if not m2:
                break
            value = m2.group(0)
            i += m2.end()
        fields[name] = value.strip()
        # Skip trailing whitespace/comma before next field
        while i < n and body[i] in ' \t\n':
            i += 1
        if i < n and body[i] == ',':
            i += 1
    return fields


def parse_bib(content: str) -> dict[str, BibEntry]:
    """Parse a .bib file and return {key: BibEntry}."""
    entries: dict[str, BibEntry] = {}
    for m in _ENTRY_START_RE.finditer(content):
        entry_type = m.group(1).lower()
        if entry_type in ('comment', 'preamble', 'string'):
            continue
        key = m.group(2)
        body_start = m.end()
        body_end = _find_entry_end(content, body_start)
        if body_end == -1:
            continue
        body = content[body_start:body_end]
        entries[key] = BibEntry(
            key=key, type=entry_type,
            fields=_parse_fields(body),
        )
    return entries


_INLINE_TEX_UNESCAPES = [
    ('\\&', '&'), ('\\%', '%'), ('\\_', '_'), ('\\#', '#'), ('\\$', '$'),
    ('\\{', '{'), ('\\}', '}'),
    ("``", '\u201c'), ("''", '\u201d'), ('`', '\u2018'), ("'", '\u2019'),
    ('---', '\u2014'), ('--', '\u2013'), ('~', ' '),
]


def _clean_tex(s: str) -> str:
    """Strip LaTeX markup we can't render and normalize whitespace."""
    # Accents: \'{e} -> é, \"{o} -> ö, etc. (simplified; covers the common ones)
    accents = {
        "'": '\u0301',  # acute
        '`': '\u0300',  # grave
        '"': '\u0308',  # umlaut
        '^': '\u0302',  # circumflex
        '~': '\u0303',  # tilde
        '.': '\u0307',  # dot above
        'c': '\u0327',  # cedilla
    }

    def _accent(m: re.Match) -> str:
        marker, ch = m.group(1), m.group(2)
        import unicodedata
        if marker in accents and ch:
            return unicodedata.normalize('NFC', ch + accents[marker])
        return ch

    s = re.sub(r"\\([`'\"\^~\.c])\{?(\w?)\}?", _accent, s)
    # \textit{x} etc. → x
    s = re.sub(r'\\text(?:bf|it|rm|sf|tt|sc)\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\emph\{([^{}]*)\}', r'\1', s)
    # Strip remaining braces
    s = re.sub(r'[{}]', '', s)
    # Common TeX-isms
    for a, b in _INLINE_TEX_UNESCAPES:
        s = s.replace(a, b)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _format_authors(raw: str) -> str:
    """`Smith, J. and Doe, J. and Other, A.` → `J. Smith, J. Doe, A. Other`."""
    authors = [a.strip() for a in re.split(r'\s+and\s+', raw)]
    out = []
    for a in authors:
        a = _clean_tex(a)
        if ',' in a:
            last, first = [x.strip() for x in a.split(',', 1)]
            out.append(f'{first} {last}' if first else last)
        else:
            out.append(a)
    if len(out) > 8:
        out = out[:8] + ['et al.']
    return ', '.join(out)


def render_entry_html(entry: BibEntry, number: int) -> str:
    """Render one BibEntry as an HTML list item with exactly two children:
    the `[N]` number span and a single `.bib-body` span holding the prose.
    Keeping two children is required by our grid layout."""
    f = entry.fields
    segments: list[str] = []
    if 'author' in f:
        segments.append(
            f'<span class="bib-author">{_html.escape(_format_authors(f["author"]))}</span>.'
        )
    if 'title' in f:
        title = _clean_tex(f['title'])
        segments.append(
            f'<span class="bib-title">{_html.escape(title)}</span>.'
        )
    venue = f.get('journal') or f.get('booktitle') or f.get('publisher')
    if venue:
        # Combine venue + volume/number/pages/year on a single line
        venue_parts = [f'<em class="bib-venue">{_html.escape(_clean_tex(venue))}</em>']
        if 'volume' in f:
            venue_parts.append(f' <strong>{_html.escape(f["volume"])}</strong>')
        if 'number' in f:
            venue_parts.append(f'({_html.escape(f["number"])})')
        if 'pages' in f:
            pages = f['pages'].replace('--', '\u2013')
            venue_parts.append(f', {_html.escape(pages)}')
        if 'year' in f:
            venue_parts.append(f' ({_html.escape(f["year"])})')
        venue_parts.append('.')
        segments.append(''.join(venue_parts))
    elif 'year' in f:
        segments.append(f'({_html.escape(f["year"])}).')
    link = None
    if 'doi' in f:
        doi = f['doi']
        link = f'https://doi.org/{doi}' if not doi.startswith('http') else doi
    elif 'url' in f:
        link = f['url']
    if link:
        segments.append(
            f'<a href="{_html.escape(link)}" target="_blank" rel="noopener">'
            f'{_html.escape(link)}</a>'
        )
    body = ' '.join(segments)
    return (f'<li id="ref-{_html.escape(entry.key)}" value="{number}">'
            f'<span class="bib-number">[{number}]</span>'
            f'<span class="bib-body">{body}</span></li>')


def load_bib(root_dir: Path, version: str) -> dict[str, BibEntry]:
    """Locate and parse references.bib from the project (version-level then root)."""
    for candidate in [
        root_dir / 'src' / version / 'references.bib',
        root_dir / 'references.bib',
    ]:
        if candidate.exists():
            return parse_bib(candidate.read_text(encoding='utf-8'))
    return {}
