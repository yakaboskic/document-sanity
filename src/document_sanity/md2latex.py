#!/usr/bin/env python3
"""
Markdown to LaTeX converter.

Converts markdown source files into LaTeX, preserving:
- YAML frontmatter (title, author, date, abstract, keywords, etc.)
- Headings -> \\section, \\subsection, \\subsubsection
- Bold, italic, code inline formatting
- Bullet and numbered lists
- Tables -> LaTeX tabular
- Code blocks -> lstlisting or verbatim
- Blockquotes -> quote environment
- Links -> \\href or \\url
- Images -> \\includegraphics
- Horizontal rules -> \\newpage
- LaTeX pass-through blocks (fenced with ```latex)

Template variable syntax ({{VAR}} and {{VAR:fmt}}) is preserved through
the conversion so the variable processor can handle it later.
"""

import re
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class MarkdownMeta:
    """Parsed frontmatter metadata."""
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    abstract: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    document_class: Optional[str] = None
    extra: dict = field(default_factory=dict)


def parse_frontmatter(md: str) -> tuple[MarkdownMeta, str]:
    """Parse YAML frontmatter from markdown content.

    Returns (metadata, body) where body is the markdown without frontmatter.
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)', md, re.DOTALL)
    if not match:
        return MarkdownMeta(), md

    try:
        raw = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return MarkdownMeta(), md

    meta = MarkdownMeta(
        title=raw.pop('title', None),
        author=raw.pop('author', None),
        date=raw.pop('date', None),
        abstract=raw.pop('abstract', None),
        keywords=raw.pop('keywords', []),
        document_class=raw.pop('document_class', None),
        extra=raw,
    )
    if isinstance(meta.keywords, str):
        meta.keywords = [k.strip() for k in meta.keywords.split(',')]

    return meta, match.group(2)


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters, but preserve template variables {{...}}."""
    # First, protect template variables
    protected = []
    parts = re.split(r'(\{\{[^}]+\}\})', text)
    for part in parts:
        if part.startswith('{{') and part.endswith('}}'):
            protected.append(part)
        else:
            # Escape LaTeX special chars
            s = part
            s = s.replace('\\', '\\textbackslash{}')
            s = s.replace('&', '\\&')
            s = s.replace('%', '\\%')
            s = s.replace('$', '\\$')
            s = s.replace('#', '\\#')
            s = s.replace('_', '\\_')
            s = s.replace('{', '\\{')
            s = s.replace('}', '\\}')
            s = s.replace('~', '\\textasciitilde{}')
            s = s.replace('^', '\\textasciicircum{}')
            protected.append(s)
    return ''.join(protected)


def _convert_inline(text: str, escape: bool = True) -> str:
    """Convert inline markdown formatting to LaTeX.

    Handles: **bold**, *italic*, `code`, [links](url), ![images](path).
    Preserves {{variable}} template syntax.
    """
    # Protect template variables from processing
    var_pattern = r'\{\{[^}]+\}\}'
    placeholders = {}
    counter = [0]

    def protect_var(m):
        key = f'\x00VAR{counter[0]}\x00'
        placeholders[key] = m.group(0)
        counter[0] += 1
        return key

    text = re.sub(var_pattern, protect_var, text)

    # Protect LaTeX pass-through (text between $ signs for math)
    math_placeholders = {}

    def protect_math(m):
        key = f'\x00MATH{counter[0]}\x00'
        math_placeholders[key] = m.group(0)
        counter[0] += 1
        return key

    # Inline math $...$
    text = re.sub(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', protect_math, text)
    # Display math $$...$$
    text = re.sub(r'\$\$.+?\$\$', protect_math, text, flags=re.DOTALL)
    # Display math \[ ... \]
    text = re.sub(r'\\\[.+?\\\]', protect_math, text, flags=re.DOTALL)
    # Inline math \( ... \)
    text = re.sub(r'\\\(.+?\\\)', protect_math, text, flags=re.DOTALL)

    # Protect LaTeX commands whose arguments contain identifiers with underscores
    # (\cite, \ref, \label, \eqref, \pageref, \autoref, \nameref, \input, \includegraphics)
    cmd_placeholders = {}

    def protect_cmd(m):
        key = f'\x00CMD{counter[0]}\x00'
        cmd_placeholders[key] = m.group(0)
        counter[0] += 1
        return key

    cmd_pattern = r'\\(?:cite[a-z]*|ref|eqref|pageref|autoref|nameref|label|input|includegraphics(?:\[[^\]]*\])?)\{[^}]*\}'
    text = re.sub(cmd_pattern, protect_cmd, text)
    # \href{url}{text}: protect just the url arg, text arg goes through normal processing
    text = re.sub(r'\\href\{[^}]*\}', protect_cmd, text)

    # Inline code `...` -> \texttt{...}. The contents must render as literal
    # characters in the output, so we fully escape every LaTeX-active char
    # (including \, {, } that earlier passes left alone). We also restore any
    # variable/math placeholders that fell inside the backticks BEFORE
    # escaping, so e.g. `{{fig:x}}` ends up as \texttt{\{\{fig:x\}\}} and the
    # downstream variable processor leaves it alone.
    def protect_code(m):
        key = f'\x00CMD{counter[0]}\x00'
        inner = m.group(1)
        # Restore any placeholders that fell inside the backticks so we can
        # see and escape the literal source.
        for pkey, pval in placeholders.items():
            inner = inner.replace(pkey, pval)
        for pkey, pval in math_placeholders.items():
            inner = inner.replace(pkey, pval)
        # Full LaTeX escape — order matters: backslash first so we don't
        # double-escape the replacements we add below.
        inner = inner.replace('\\', '\\textbackslash{}')
        inner = inner.replace('{', '\\{')
        inner = inner.replace('}', '\\}')
        inner = inner.replace('&', '\\&')
        inner = inner.replace('%', '\\%')
        inner = inner.replace('$', '\\$')
        inner = inner.replace('#', '\\#')
        inner = inner.replace('_', '\\_')
        inner = inner.replace('~', '\\textasciitilde{}')
        inner = inner.replace('^', '\\textasciicircum{}')
        cmd_placeholders[key] = '\\texttt{' + inner + '}'
        counter[0] += 1
        return key
    text = re.sub(r'(?<!`)`([^`]+?)`(?!`)', protect_code, text)

    # Escape LaTeX if needed (only for non-protected text)
    if escape:
        parts = re.split(r'(\x00(?:VAR|MATH|CMD)\d+\x00)', text)
        escaped = []
        for part in parts:
            if part in placeholders or part in math_placeholders or part in cmd_placeholders:
                escaped.append(part)
            else:
                escaped.append(_escape_latex(part))
        text = ''.join(escaped)
    else:
        # In no-escape mode, still escape chars that are unsafe in running LaTeX
        # but have no special meaning in markdown: _, &, #
        parts = re.split(r'(\x00(?:VAR|MATH|CMD)\d+\x00)', text)
        escaped = []
        for part in parts:
            if part in placeholders or part in math_placeholders or part in cmd_placeholders:
                escaped.append(part)
            else:
                # Escape unescaped _, &, # (leave \_ \& \# as-is)
                s = re.sub(r'(?<!\\)_', r'\\_', part)
                s = re.sub(r'(?<!\\)&', r'\\&', s)
                s = re.sub(r'(?<!\\)#', r'\\#', s)
                escaped.append(s)
        text = ''.join(escaped)

    # Images: ![alt](path) -> \includegraphics{path}
    text = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)',
        r'\\includegraphics[width=\\textwidth]{\2}',
        text
    )

    # Links: [text](url) -> \href{url}{text}
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'\\href{\2}{\1}',
        text
    )

    # Bold + italic: ***text*** -> \textbf{\textit{text}}
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\\textbf{\\textit{\1}}', text)

    # Bold: **text** -> \textbf{text}
    text = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', text)

    # Italic: *text* -> \textit{text}
    text = re.sub(r'\*(.+?)\*', r'\\textit{\1}', text)

    # Restore protected content (iterate to handle nesting)
    for _pass in range(3):
        for key, val in placeholders.items():
            text = text.replace(key, val)
        for key, val in math_placeholders.items():
            text = text.replace(key, val)
        for key, val in cmd_placeholders.items():
            text = text.replace(key, val)

    return text


def _convert_table(lines: list[str]) -> str:
    """Convert a markdown table to LaTeX tabular."""
    if len(lines) < 2:
        return '\n'.join(lines)

    # Parse header
    header = [c.strip() for c in lines[0].strip('|').split('|')]
    n_cols = len(header)

    # Skip separator line (line 1)
    # Parse data rows
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.append(cells)

    # Build LaTeX
    col_spec = '|' + '|'.join(['l'] * n_cols) + '|'
    out = []
    out.append('\\begin{table}[htbp]')
    out.append('\\centering')
    out.append(f'\\begin{{tabular}}{{{col_spec}}}')
    out.append('\\hline')
    out.append(' & '.join(f'\\textbf{{{_convert_inline(h)}}}' for h in header) + ' \\\\')
    out.append('\\hline')
    for row in rows:
        # Pad row if needed
        while len(row) < n_cols:
            row.append('')
        out.append(' & '.join(_convert_inline(c) for c in row[:n_cols]) + ' \\\\')
    out.append('\\hline')
    out.append('\\end{tabular}')
    out.append('\\end{table}')

    return '\n'.join(out)


def _is_fence_closer(line: str) -> bool:
    """A code-fence closer is a line of only backticks (CommonMark: closer
    must not have an info string). This prevents a second ```latex line —
    which the author may have intended as another opener — from being
    misread as the close of the first fence."""
    return bool(re.match(r'^\s*```+\s*$', line))


_PREVIEW_BLOCK_RE = re.compile(
    r'<!--\s*(?:document-sanity|latex-builder):preview:begin[^>]*-->'
    r'.*?<!--\s*(?:document-sanity|latex-builder):preview:end\s*-->\s*',
    re.DOTALL,
)


def md_to_latex(
    md_content: str,
    escape_text: bool = True,
) -> tuple[MarkdownMeta, str]:
    """Convert markdown content to LaTeX body content.

    Args:
        md_content: Raw markdown string (may include frontmatter).
        escape_text: Whether to escape LaTeX special characters in prose.

    Returns:
        (metadata, latex_body) where latex_body is just the body content,
        not a complete document. The caller wraps it in a document environment.
    """
    meta, body = parse_frontmatter(md_content)

    # Strip auto-generated preview blocks so they don't round-trip into LaTeX.
    # The ```latex block above each preview remains the source of truth.
    body = _PREVIEW_BLOCK_RE.sub('', body)

    lines = body.split('\n')
    output = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Empty line -> blank line (paragraph break)
        if not stripped:
            output.append('')
            i += 1
            continue

        # HTML comments -> LaTeX comments
        if '<!--' in stripped:
            import re as _re
            converted = _re.sub(r'<!--\s*(.*?)\s*-->', r'% \1', line)
            # If the line is ONLY a comment, output it and continue
            if _re.match(r'^\s*%\s', converted.strip()):
                output.append(converted.rstrip())
                i += 1
                continue
            # Headings carry an embedded `<!-- \label{...} -->` by convention.
            # Convert the comment in place and let the heading handler below
            # extract the label — don't strip it.
            if stripped.startswith('#'):
                line = converted
                lines[i] = line
                stripped = line.strip()
            else:
                # Otherwise, strip the inline comment from the line entirely
                # (LaTeX % comments would eat the rest of the line including content after them)
                line = _re.sub(r'\s*<!--\s*.*?\s*-->\s*', ' ', line).rstrip()
                lines[i] = line
                stripped = line.strip()
                if not stripped:
                    output.append('')
                    i += 1
                    continue

        # LaTeX pass-through block: ```latex ... ```
        if stripped.startswith('```latex'):
            i += 1
            latex_block = []
            while i < len(lines) and not _is_fence_closer(lines[i]):
                latex_block.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            output.extend(latex_block)
            continue

        # Code block: ``` ... ```
        # The info string (e.g. ```markdown) is intentionally dropped. The
        # listings package only knows a fixed set of languages, the default
        # template doesn't configure highlighting, and emitting
        # `language=markdown` (or any other unknown lang) is a hard pdflatex
        # error. Verbatim monospaced output is the right default; users who
        # want highlighting can \lstdefinelanguage{} in their template.
        if stripped.startswith('```'):
            i += 1
            code_lines = []
            while i < len(lines) and not _is_fence_closer(lines[i]):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            output.append('\\begin{lstlisting}')
            output.extend(code_lines)
            output.append('\\end{lstlisting}')
            continue

        # Horizontal rule -> page break
        if re.match(r'^---+$', stripped) or re.match(r'^\*\*\*+$', stripped):
            output.append('\\newpage')
            i += 1
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            raw_text = heading_match.group(2)

            # Extract \label{} from heading text (may have been converted to % \label{} by comment handler)
            label_cmd = ''
            # Match % \label{...} or <!-- \label{...} --> patterns
            label_m = re.search(r'\s*%\s*\\label\{([^}]+)\}', raw_text)
            if label_m:
                label_cmd = f'\\label{{{label_m.group(1)}}}'
                raw_text = raw_text[:label_m.start()].rstrip()

            text = _convert_inline(raw_text, escape=escape_text)
            if level == 1:
                output.append(f'\\section{{{text}}}')
            elif level == 2:
                output.append(f'\\subsection{{{text}}}')
            elif level == 3:
                output.append(f'\\subsubsection{{{text}}}')
            elif level == 4:
                output.append(f'\\paragraph{{{text}}}')
            else:
                output.append(f'\\subparagraph{{{text}}}')
            if label_cmd:
                output.append(label_cmd)
            i += 1
            continue

        # Blockquote
        if stripped.startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                quote_lines.append(lines[i].strip().lstrip('>').strip())
                i += 1
            quote_text = ' '.join(quote_lines)
            output.append('\\begin{quote}')
            output.append(_convert_inline(quote_text, escape=escape_text))
            output.append('\\end{quote}')
            continue

        # Table: detect | header | pattern
        if '|' in stripped and i + 1 < len(lines) and re.match(r'^\s*\|?\s*[-:]+', lines[i + 1]):
            table_lines = []
            while i < len(lines) and '|' in lines[i].strip():
                table_lines.append(lines[i])
                i += 1
            output.append(_convert_table(table_lines))
            continue

        # Unordered list
        if re.match(r'^[-*+]\s', stripped):
            output.append('\\begin{itemize}')
            while i < len(lines) and re.match(r'^\s*[-*+]\s', lines[i]):
                item_text = re.sub(r'^\s*[-*+]\s+', '', lines[i])
                output.append(f'  \\item {_convert_inline(item_text, escape=escape_text)}')
                i += 1
            output.append('\\end{itemize}')
            continue

        # Ordered list
        if re.match(r'^\d+\.\s', stripped):
            output.append('\\begin{enumerate}')
            while i < len(lines) and re.match(r'^\s*\d+\.\s', lines[i]):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i])
                output.append(f'  \\item {_convert_inline(item_text, escape=escape_text)}')
                i += 1
            output.append('\\end{enumerate}')
            continue

        # Regular paragraph
        para_lines = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            para_text = ' '.join(para_lines)
            output.append(_convert_inline(para_text, escape=escape_text))
            continue

        i += 1

    return meta, '\n'.join(output)


def _is_block_start(line: str) -> bool:
    """Check if a line starts a new block element."""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith('#'):
        return True
    if stripped.startswith('```'):
        return True
    if re.match(r'^---+$', stripped) or re.match(r'^\*\*\*+$', stripped):
        return True
    if stripped.startswith('>'):
        return True
    if re.match(r'^[-*+]\s', stripped):
        return True
    if re.match(r'^\d+\.\s', stripped):
        return True
    return False


def convert_md_file(
    input_path: Path,
    output_path: Path,
    escape_text: bool = True,
) -> MarkdownMeta:
    """Convert a markdown file to a LaTeX file (body only, no document wrapper).

    Args:
        input_path: Path to .md file
        output_path: Path to write .tex file
        escape_text: Whether to escape LaTeX special characters

    Returns:
        Parsed metadata from frontmatter
    """
    content = input_path.read_text(encoding='utf-8')
    meta, latex_body = md_to_latex(content, escape_text=escape_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_body, encoding='utf-8')

    return meta
