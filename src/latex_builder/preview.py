#!/usr/bin/env python3
"""
Generate markdown-preview blocks next to LaTeX pass-through blocks so docs
render meaningful figures/equations in GitHub, VSCode, Obsidian, etc.

The ```latex fenced block stays the source of truth for PDF compilation.
A preview block is inserted immediately after it, bracketed by HTML comment
markers and tagged with a content hash of the source latex block:

    ```latex
    \\begin{figure}[h!]
        \\centering
        \\includegraphics[width=\\textwidth]{figures/foo.png}
        \\caption{A figure.}
    \\end{figure}
    ```
    <!-- latex-builder:preview:begin hash=abcd1234 -->
    ![A figure.](figures/foo.png)
    <!-- latex-builder:preview:end -->

`preview` rewrites (or creates) these blocks; hand-edits between the
markers get overwritten. `preview --check` reports stale/missing blocks
without writing anything.
"""

import hashlib
import re
from pathlib import Path
from typing import Optional


PREVIEW_BEGIN_RE = re.compile(
    r'<!--\s*latex-builder:preview:begin(?:\s+hash=([0-9a-f]+))?\s*-->'
)
PREVIEW_END_RE = re.compile(r'<!--\s*latex-builder:preview:end\s*-->')

# Parse \newcommand{\name}{body} and \providecommand{\name}{body} with NO args.
# Multi-arg forms like \newcommand{\foo}[1]{...} are skipped (too lossy to expand safely).
_NEWCMD_RE = re.compile(
    r'\\(?:new|provide)command\s*\{\\([A-Za-z@]+)\}\s*\{',
)

FIGURE_ENV_RE = re.compile(r'\\begin\{(figure\*?)\}')
TABLE_ENV_RE = re.compile(r'\\begin\{(table\*?|longtable)\}')
MATH_ENVS = (
    'align*', 'align', 'equation*', 'equation',
    'eqnarray*', 'eqnarray', 'gather*', 'gather',
    'multline*', 'multline',
)


def hash_block(content: str) -> str:
    """Short stable hash of a latex block's normalized content."""
    normalized = re.sub(r'\s+', ' ', content).strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]


def parse_macros(template_text: str) -> dict[str, str]:
    """Extract zero-argument \\newcommand/\\providecommand definitions.

    Returns a dict {macro_name: replacement_body}. Multi-arg forms like
    \\newcommand{\\foo}[1]{...} are skipped because expanding them requires
    parsing argument applications and is lossy enough not to be worth it.
    """
    macros: dict[str, str] = {}
    for m in _NEWCMD_RE.finditer(template_text):
        name = m.group(1)
        body = _extract_balanced(template_text, m.end())
        if body is None:
            continue
        # Skip if the preceding tokens include an arg count like [1]
        # (our regex already excludes that case, but double-check by peeking
        # at the character just before the { that started the body)
        # The regex only matches \newcommand{\name}{ — an optional [N] would
        # sit between the closing } of the name and the opening { of the body,
        # so our match would have failed. We're safe.
        macros[name] = body
    return macros


def expand_macros(text: str, macros: dict[str, str]) -> str:
    """Replace each `\\name` occurrence with its body, word-boundary aware.

    LaTeX control sequences end at the first non-letter character, so we use
    `(?![A-Za-z])` to avoid replacing `\\probability` when `\\prob` is defined.
    Applied iteratively so chained macros resolve.
    """
    if not macros:
        return text
    for _ in range(5):  # iterate a few times to resolve nested macros
        changed = False
        for name, body in macros.items():
            pattern = re.compile(r'\\' + re.escape(name) + r'(?![A-Za-z])')
            new = pattern.sub(lambda _m, b=body: b, text)
            if new != text:
                changed = True
                text = new
        if not changed:
            break
    return text


_INLINE_MATH_RE = re.compile(r'(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)')
_DISPLAY_DOLLAR_RE = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
_DISPLAY_BRACKET_RE = re.compile(r'\\\[(.+?)\\\]', re.DOTALL)


def expand_macros_in_math(text: str, macros: dict[str, str]) -> tuple[str, int]:
    """Apply macro expansion only inside math delimiters in a markdown doc.

    Skips ```latex fenced blocks (the LaTeX compiler will expand them from
    the template) and preview blocks (regenerated anyway).

    Returns (new_text, n_substitutions).
    """
    if not macros:
        return text, 0

    lines = text.split('\n')
    out: list[str] = []
    i = 0
    n = len(lines)
    total_subs = 0

    def expand_and_count(s: str) -> tuple[str, int]:
        expanded = expand_macros(s, macros)
        count = 0
        if expanded != s:
            for name in macros:
                count += len(re.findall(r'\\' + re.escape(name) + r'(?![A-Za-z])', s))
        return expanded, count

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Skip ```latex and preview blocks verbatim
        if stripped == '```latex' or stripped.startswith('```latex'):
            out.append(line)
            i += 1
            while i < n and lines[i].strip() != '```':
                out.append(lines[i])
                i += 1
            if i < n:
                out.append(lines[i])
                i += 1
            continue

        if PREVIEW_BEGIN_RE.match(stripped):
            out.append(line)
            i += 1
            while i < n and not PREVIEW_END_RE.match(lines[i].strip()):
                out.append(lines[i])
                i += 1
            if i < n:
                out.append(lines[i])
                i += 1
            continue

        # Expand in inline math within this line
        def _sub_inline(m: re.Match) -> str:
            nonlocal total_subs
            expanded, c = expand_and_count(m.group(1))
            total_subs += c
            return '$' + expanded + '$'

        new_line = _INLINE_MATH_RE.sub(_sub_inline, line)
        out.append(new_line)
        i += 1

    text = '\n'.join(out)

    # Display math can span lines, handle on the joined text
    def _sub_display_dollar(m: re.Match) -> str:
        nonlocal total_subs
        expanded, c = expand_and_count(m.group(1))
        total_subs += c
        return '$$' + expanded + '$$'

    def _sub_display_bracket(m: re.Match) -> str:
        nonlocal total_subs
        expanded, c = expand_and_count(m.group(1))
        total_subs += c
        return '\\[' + expanded + '\\]'

    text = _DISPLAY_DOLLAR_RE.sub(_sub_display_dollar, text)
    text = _DISPLAY_BRACKET_RE.sub(_sub_display_bracket, text)

    return text, total_subs


def _extract_balanced(text: str, start: int) -> Optional[str]:
    """Given `text[start]` is just after an opening `{`, return the content
    up to the matching close. Returns None if unbalanced."""
    depth = 1
    i = start
    while i < len(text):
        c = text[i]
        if c == '\\' and i + 1 < len(text):
            i += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def _first_caption(block: str) -> Optional[str]:
    """Extract first \\caption{...} body, balanced-brace aware."""
    m = re.search(r'\\caption\s*\{', block)
    if not m:
        return None
    body = _extract_balanced(block, m.end())
    if body is None:
        return None
    # Strip common inline formatting so the preview caption reads naturally
    body = re.sub(r'\\text(?:bf|it|rm|sf|tt)\{([^{}]*)\}', r'\1', body)
    body = re.sub(r'\\emph\{([^{}]*)\}', r'\1', body)
    body = re.sub(r'\\cite[a-z]*\{[^{}]*\}', '', body)
    body = re.sub(r'\\ref\{[^{}]*\}', '', body)
    body = re.sub(r'\\label\{[^{}]*\}', '', body)
    body = re.sub(r'\s+', ' ', body).strip()
    # Markdown alt text doesn't like unescaped brackets
    body = body.replace('[', '(').replace(']', ')')
    return body


def _first_image_path(block: str, figures: dict) -> Optional[str]:
    """Return a markdown-usable path for the first image in a figure env.

    Resolves {{canva:N}} / {{fig:id}} via the manifest. Falls back to the
    raw \\includegraphics argument if present.
    """
    fig_var = re.search(r'\{\{(?:canva|fig):([A-Za-z0-9_\-]+)\}\}', block)
    if fig_var:
        fig_id = fig_var.group(1)
        entry = figures.get(fig_id) or figures.get(str(fig_id))
        if entry:
            source = entry.source if hasattr(entry, 'source') else entry.get('source')
            if source:
                return source
    img = re.search(r'\\includegraphics(?:\[[^\]]*\])?\s*\{', block)
    if img:
        body = _extract_balanced(block, img.end())
        if body:
            return body.strip()
    return None


def _resolve_preview_path(path: str, src_dir: Path, doc_dir: Path) -> str:
    """Translate a build-time path (relative to src_dir) into a preview-time
    path relative to the doc, falling back to a sibling .png if the target
    is a .pdf (markdown viewers can't render PDFs).
    """
    # Resolve the source file (if it exists on disk)
    candidate = (src_dir / path).resolve()
    if candidate.suffix.lower() == '.pdf':
        png_sibling = candidate.with_suffix('.png')
        if png_sibling.exists():
            candidate = png_sibling

    # Build a path relative to the doc's directory. If this fails (e.g.
    # different drives on Windows), fall back to the raw path.
    try:
        rel = candidate.relative_to(doc_dir) if candidate.is_relative_to(doc_dir) else None
    except Exception:
        rel = None
    if rel is None:
        try:
            import os
            rel_str = os.path.relpath(candidate, start=doc_dir)
        except ValueError:
            return path
        return rel_str.replace('\\', '/')
    return str(rel).replace('\\', '/')


def figure_preview(block: str, figures: dict,
                   src_dir: Optional[Path] = None,
                   doc_dir: Optional[Path] = None) -> Optional[str]:
    """Generate a markdown image for a figure environment."""
    path = _first_image_path(block, figures)
    if not path:
        # Figure with no resolvable image (e.g. placeholder) — still emit a stub
        cap = _first_caption(block) or 'Figure'
        return f'*(figure placeholder — {cap})*'
    caption = _first_caption(block) or 'figure'

    if src_dir is not None and doc_dir is not None:
        display_path = _resolve_preview_path(path, src_dir, doc_dir)
    else:
        display_path = path

    # If the resolved path still ends in .pdf, markdown viewers can't render
    # it — emit a placeholder note rather than a broken image.
    if display_path.lower().endswith('.pdf'):
        return f'*(figure — PDF, see LaTeX above: {caption})*'
    return f'![{caption}]({display_path})'


def math_preview(block: str, macros: Optional[dict] = None) -> Optional[str]:
    """Generate $$...$$ blocks from math environments in a latex block."""
    # Match any of the supported math envs, longest-first so `align*` wins over `align`.
    envs_alt = '|'.join(re.escape(e) for e in MATH_ENVS)
    env_re = re.compile(
        r'\\begin\{(' + envs_alt + r')\}(.*?)\\end\{\1\}',
        re.DOTALL,
    )
    lines_out = []
    for m in env_re.finditer(block):
        body = m.group(2).strip()
        # Drop labels — they don't render in $$ math
        body = re.sub(r'\\label\{[^{}]*\}', '', body)
        # Split on `\\` row separators, strip alignment tabs `&`
        for raw in re.split(r'\\\\', body):
            s = raw.replace('&', '').strip()
            s = re.sub(r'\s+', ' ', s)
            if s:
                if macros:
                    s = expand_macros(s, macros)
                lines_out.append(f'$$ {s} $$')
    if not lines_out:
        return None
    return '\n\n'.join(lines_out)


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split text on `sep`, ignoring occurrences inside balanced `{...}`.

    Check for `sep` BEFORE treating `\\` as an escape, so a `\\\\` row separator
    (literal `\\`) isn't consumed by the escape-skip when sep happens to be `\\\\`.
    """
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    L = len(text)
    slen = len(sep)
    while i < L:
        # Check separator first
        if depth == 0 and text[i:i + slen] == sep:
            parts.append(text[start:i])
            i += slen
            start = i
            continue
        c = text[i]
        # Then handle escape sequences (e.g., \{ \} so braces inside them don't affect depth)
        if c == '\\' and i + 1 < L:
            i += 2
            continue
        if c == '{':
            depth += 1
            i += 1
            continue
        if c == '}':
            depth -= 1
            i += 1
            continue
        i += 1
    parts.append(text[start:])
    return parts


def _cell_to_md(cell: str) -> str:
    """Convert a LaTeX table cell to markdown-table-safe text."""
    s = cell.strip()
    # \multicolumn{N}{spec}{content} -> content
    s = re.sub(r'\\multicolumn\s*\{[^{}]*\}\s*\{[^{}]*\}\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
               r'\1', s)
    # \href{url}{text} -> [text](url)
    s = re.sub(r'\\href\{([^{}]+)\}\{([^{}]+)\}', r'[\2](\1)', s)
    # \textbf{X} -> **X**
    s = re.sub(r'\\textbf\{([^{}]*)\}', r'**\1**', s)
    # \textit{X} or \emph{X} -> *X*
    s = re.sub(r'\\(?:textit|emph)\{([^{}]*)\}', r'*\1*', s)
    # \texttt{X} -> `X`
    s = re.sub(r'\\texttt\{([^{}]*)\}', r'`\1`', s)
    # Strip \cite and \ref remnants (can't render in md table)
    s = re.sub(r'\\cite[a-z]*\{[^{}]*\}', '', s)
    s = re.sub(r'\\ref\{[^{}]*\}', '', s)
    s = re.sub(r'\\label\{[^{}]*\}', '', s)
    # Collapse whitespace; escape pipes
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.replace('|', '\\|')
    return s or ' '


_RULE_RE = re.compile(
    r'^\s*\\(?:toprule|midrule|bottomrule|hline|cmidrule(?:\(\w+\))?\{[^{}]*\})\s*$'
)


def _parse_tabular(tabular_body: str) -> list[list[str]]:
    """Parse the body of a \\begin{tabular}{...} ... \\end{tabular} into rows of cells.

    Strips horizontal rules (\\toprule, \\midrule, \\bottomrule, \\hline, \\cmidrule).
    """
    rows_raw = _split_top_level(tabular_body, '\\\\')
    rows: list[list[str]] = []
    for raw in rows_raw:
        # Remove rule commands appearing anywhere on the row
        cleaned = re.sub(
            r'\\(?:toprule|midrule|bottomrule|hline|cmidrule(?:\([^)]*\))?\{[^{}]*\})',
            '', raw,
        )
        # Remove orphan \\ or \cmidrule with no args
        cleaned = cleaned.strip()
        if not cleaned:
            continue
        cells = [_cell_to_md(c) for c in _split_top_level(cleaned, '&')]
        # Skip rows that became entirely empty after cleaning
        if any(c.strip() for c in cells):
            rows.append(cells)
    return rows


def _render_md_table(rows: list[list[str]]) -> str:
    """Render a list of cell-rows as a GitHub-flavored markdown table."""
    if not rows:
        return ''
    n_cols = max(len(r) for r in rows)
    padded = [r + [' '] * (n_cols - len(r)) for r in rows]
    header = padded[0]
    body = padded[1:]
    sep = ['---'] * n_cols
    out = ['| ' + ' | '.join(header) + ' |',
           '| ' + ' | '.join(sep) + ' |']
    for r in body:
        out.append('| ' + ' | '.join(r) + ' |')
    return '\n'.join(out)


def table_preview(block: str) -> Optional[str]:
    """Generate a markdown-table preview from a table/longtable environment.

    Extracts each \\begin{tabular}{...}...\\end{tabular}, parses rows, and
    emits a GitHub-flavored markdown table. Includes caption as a bold prefix.
    \\multicolumn cells collapse to their content (span info is lost); rules
    are dropped.
    """
    tab_re = re.compile(
        r'\\begin\{tabular\*?\}\s*\{[^{}]*\}(.*?)\\end\{tabular\*?\}',
        re.DOTALL,
    )
    tables = tab_re.findall(block)
    if not tables:
        cap = _first_caption(block)
        return f'*(table — {cap})*' if cap else '*(table — see LaTeX above)*'

    caption = _first_caption(block)
    out_parts: list[str] = []
    if caption:
        out_parts.append(f'**Table:** {caption}')
        out_parts.append('')
    for body in tables:
        rows = _parse_tabular(body)
        if rows:
            out_parts.append(_render_md_table(rows))
            out_parts.append('')

    # Strip trailing blank line
    while out_parts and not out_parts[-1]:
        out_parts.pop()
    return '\n'.join(out_parts) if out_parts else None


def _render_preview_body(block: str, figures: dict,
                         macros: Optional[dict] = None,
                         src_dir: Optional[Path] = None,
                         doc_dir: Optional[Path] = None) -> Optional[str]:
    """Pick the right preview generator for a latex block."""
    if FIGURE_ENV_RE.search(block):
        return figure_preview(block, figures, src_dir=src_dir, doc_dir=doc_dir)
    if any(f'\\begin{{{env}}}' in block for env in MATH_ENVS):
        return math_preview(block, macros)
    if TABLE_ENV_RE.search(block):
        return table_preview(block)
    return None


def _emit_preview(hash_hex: str, body: str) -> list[str]:
    return [
        f'<!-- latex-builder:preview:begin hash={hash_hex} -->',
        body,
        '<!-- latex-builder:preview:end -->',
    ]


def rewrite_doc(md_content: str, figures: dict,
                macros: Optional[dict] = None,
                src_dir: Optional[Path] = None,
                doc_dir: Optional[Path] = None) -> tuple[str, int, int]:
    """Insert/update preview blocks in a markdown document.

    Returns (new_content, n_added, n_updated).
    """
    lines = md_content.split('\n')
    out: list[str] = []
    added = 0
    updated = 0
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        if line.strip() != '```latex':
            out.append(line)
            i += 1
            continue

        # Gather the ```latex block
        fence_start = i
        i += 1
        body_lines = []
        while i < n and lines[i].strip() != '```':
            body_lines.append(lines[i])
            i += 1
        if i >= n:
            # Unclosed fence: pass through as-is
            out.extend(lines[fence_start:])
            break
        fence_end = i  # closing ```
        block_content = '\n'.join(body_lines)
        # Emit the fenced block
        out.extend(lines[fence_start:fence_end + 1])
        i = fence_end + 1

        # If an existing preview block follows (possibly after blank lines),
        # note it and skip past it so we can rewrite.
        lookahead = i
        while lookahead < n and not lines[lookahead].strip():
            lookahead += 1
        existing = None  # (start, end, hash)
        if lookahead < n:
            m = PREVIEW_BEGIN_RE.match(lines[lookahead].strip())
            if m:
                end_idx = lookahead + 1
                while end_idx < n and not PREVIEW_END_RE.match(lines[end_idx].strip()):
                    end_idx += 1
                if end_idx < n:
                    existing = (lookahead, end_idx, m.group(1))

        preview_body = _render_preview_body(
            block_content, figures, macros, src_dir=src_dir, doc_dir=doc_dir
        )
        if preview_body is None:
            # Not a kind we preview. Leave any existing preview block alone
            # (user may have authored it manually for a passthrough we don't handle).
            continue

        new_hash = hash_block(block_content)
        new_block = _emit_preview(new_hash, preview_body)

        if existing:
            _, end_idx, old_hash = existing
            # Skip over the old preview range
            i = end_idx + 1
            if old_hash != new_hash:
                updated += 1
            else:
                # Hash matches — preserve existing block content verbatim
                # (avoids diff noise when rebodies would be semantically identical)
                pass
            out.append('')
            out.extend(new_block)
        else:
            added += 1
            out.append('')
            out.extend(new_block)

    return '\n'.join(out), added, updated


def check_doc(md_content: str, figures: dict) -> list[str]:
    """Return a list of drift messages. Empty if all preview blocks are in sync."""
    issues: list[str] = []
    lines = md_content.split('\n')
    n = len(lines)
    i = 0
    while i < n:
        if lines[i].strip() != '```latex':
            i += 1
            continue
        fence_start = i
        i += 1
        body_lines = []
        while i < n and lines[i].strip() != '```':
            body_lines.append(lines[i])
            i += 1
        if i >= n:
            break
        fence_end = i
        block_content = '\n'.join(body_lines)
        i = fence_end + 1

        preview_body = _render_preview_body(block_content, {})
        if preview_body is None and not any(
            FIGURE_ENV_RE.search(block_content) or TABLE_ENV_RE.search(block_content)
            or (f'\\begin{{{env}}}' in block_content) for env in MATH_ENVS
        ):
            continue

        # Look for existing preview block
        lookahead = i
        while lookahead < n and not lines[lookahead].strip():
            lookahead += 1
        expected_hash = hash_block(block_content)
        if lookahead < n:
            m = PREVIEW_BEGIN_RE.match(lines[lookahead].strip())
            if m:
                if m.group(1) != expected_hash:
                    issues.append(
                        f'line {fence_start + 1}: preview block is stale '
                        f'(hash={m.group(1)}, expected={expected_hash})'
                    )
                continue
        issues.append(f'line {fence_start + 1}: missing preview block')
    return issues


def _load_template_macros(root_dir: Path, manifest) -> dict[str, str]:
    """Find the template .tex and parse \\newcommand macros from it."""
    template_name = manifest.get_template_name() if manifest else 'article'
    for candidate in [
        root_dir / 'templates' / f'{template_name}.tex',
        root_dir / f'{template_name}.tex',
    ]:
        if candidate.exists():
            return parse_macros(candidate.read_text(encoding='utf-8'))
    return {}


def run(root_dir: Path, version: str, check: bool = False,
        verbose: bool = False, expand_macros: bool = True) -> int:
    """Rewrite (or check) preview blocks across every doc in src/<version>/docs/."""
    from .manifest import Manifest

    src_dir = root_dir / 'src' / version
    docs_dir = src_dir / 'docs'
    manifest_path = src_dir / 'manifest.yaml'

    if not docs_dir.exists():
        print(f'  Error: {docs_dir} not found', flush=True)
        return 1

    figures = {}
    manifest = None
    if manifest_path.exists():
        manifest = Manifest(manifest_path)
        figures = dict(manifest.figures)

    macros: dict[str, str] = {}
    if expand_macros:
        macros = _load_template_macros(root_dir, manifest)
        if macros and verbose:
            print(f'  Loaded {len(macros)} template macro(s): '
                  f'{", ".join(sorted(macros.keys()))}')

    total_added = 0
    total_updated = 0
    total_subs = 0
    total_issues: list[tuple[Path, str]] = []
    n_files = 0

    for md_path in sorted(docs_dir.rglob('*.md')):
        n_files += 1
        content = md_path.read_text(encoding='utf-8')
        if check:
            issues = check_doc(content, figures)
            for msg in issues:
                total_issues.append((md_path, msg))
            if verbose and not issues:
                print(f'  OK  {md_path.relative_to(root_dir)}')
            continue

        # First expand macros in inline/display math (outside fences and preview blocks)
        subs_here = 0
        if macros:
            content, subs_here = expand_macros_in_math(content, macros)
            total_subs += subs_here

        new_content, added, updated = rewrite_doc(
            content, figures, macros,
            src_dir=src_dir, doc_dir=md_path.parent,
        )
        if new_content != content:
            md_path.write_text(new_content, encoding='utf-8')
        elif subs_here > 0:
            md_path.write_text(content, encoding='utf-8')

        total_added += added
        total_updated += updated
        if verbose:
            note = f'+{added} added, {updated} updated'
            if subs_here:
                note += f', {subs_here} macro expansion(s)'
            print(f'  {md_path.relative_to(root_dir)}: {note}')

    if check:
        if total_issues:
            for path, msg in total_issues:
                print(f'  {path.relative_to(root_dir)}: {msg}')
            print(f'\n  {len(total_issues)} preview drift(s) across {n_files} files')
            return 1
        print(f'  All preview blocks in sync across {n_files} files')
        return 0

    summary = (f'  Preview: {total_added} added, {total_updated} updated '
               f'across {n_files} files')
    if total_subs:
        summary += f'; {total_subs} macro expansion(s)'
    print(summary)
    return 0
