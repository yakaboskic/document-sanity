#!/usr/bin/env python3
"""
Markdown → HTML converter for the html_builder.

Designed to consume the same markdown docs used as source-of-truth for LaTeX,
but emits HTML suitable for interactive rendering:

- ```latex pass-through blocks are DROPPED (PDF-only).
- latex-builder:preview:begin/end markers are stripped, contents kept (already
  markdown — figures as ![alt](path), math as $$...$$, tables as | ... | grids).
- Inline math $...$, display $$...$$, and \\[...\\] are preserved verbatim for
  client-side KaTeX to render.
- {{VARIABLE}} and {{VARIABLE:fmt}} tokens get wrapped in <span class="var"> with
  a data-provenance JSON blob, so the viewer can show popovers with the source,
  command, description, etc. Substitution into the span's visible text happens
  in the builder, not here.
- Images with .html extensions become <iframe> (for interactive figures like
  plotly exports); everything else is a plain <img>.
"""

import html as _html
import json
import re
import unicodedata
from typing import Any, Callable, Optional


def slugify(text: str) -> str:
    """GitHub-style heading slug: lowercase, alnum + hyphens."""
    # Strip HTML tags, then normalize, lowercase, convert to hyphens
    text = re.sub(r'<[^>]+>', '', text)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text or 'section'


# Preview markers and latex fences we strip before rendering
_PREVIEW_BLOCK_RE = re.compile(
    r'<!--\s*latex-builder:preview:begin[^>]*-->\s*(.*?)\s*<!--\s*latex-builder:preview:end\s*-->',
    re.DOTALL,
)
_LATEX_FENCE_RE = re.compile(
    r'^```latex\s*\n.*?^```\s*$',
    re.MULTILINE | re.DOTALL,
)
_CODE_FENCE_RE = re.compile(r'```(\w*)\s*\n(.*?)```', re.DOTALL)


# Variable token: {{name}} or {{name:fmt}}. Match mixed-case identifiers
# (some variables have lowercase segments like ..._AT_RS_eq_...).
_VAR_RE = re.compile(r'\{\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]+))?\}\}')


# Image/link markdown
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)')
_LINK_RE = re.compile(r'(?<!\!)\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)')


def _escape(text: str) -> str:
    """HTML-escape while leaving math and protected placeholders alone."""
    return _html.escape(text, quote=False)


def _protect(text: str, pattern: re.Pattern, store: dict,
             counter: list[int], prefix: str) -> str:
    """Replace regex matches with sentinel tokens; save originals for later restore."""
    def repl(m: re.Match) -> str:
        key = f'\x00{prefix}{counter[0]}\x00'
        store[key] = m.group(0)
        counter[0] += 1
        return key
    return pattern.sub(repl, text)


def _restore(text: str, store: dict) -> str:
    for _ in range(3):
        changed = False
        for key, val in store.items():
            if key in text:
                text = text.replace(key, val)
                changed = True
        if not changed:
            break
    return text


def _render_variable_span(name: str, fmt: Optional[str],
                          resolve_variable: Callable[[str, Optional[str]], tuple]) -> str:
    """Return the <span> HTML for a {{VAR}} token.

    resolve_variable(name, fmt) must return (display_text, provenance_dict_or_None,
    is_defined_bool).
    """
    display, provenance, is_defined = resolve_variable(name, fmt)
    classes = ['var']
    if not is_defined:
        classes.append('var-undefined')
    if provenance:
        classes.append('var-has-provenance')
    attrs = [f'class="{" ".join(classes)}"', f'data-var="{_escape(name)}"']
    if fmt:
        attrs.append(f'data-fmt="{_escape(fmt)}"')
    if provenance:
        prov_json = json.dumps(provenance, ensure_ascii=True)
        attrs.append(f"data-provenance='{_html.escape(prov_json, quote=True)}'")
    return f'<span {" ".join(attrs)}>{_escape(display)}</span>'


_SCI_RE = re.compile(r'(-?\d+(?:\.\d+)?)[eE]([+-]?\d+)')


def _prettify_sci_in_math(text: str) -> str:
    """Inside math content, rewrite `8.65e-09` → `8.65 \\times 10^{-9}`."""
    return _SCI_RE.sub(
        lambda m: f'{m.group(1)} \\times 10^{{{int(m.group(2))}}}',
        text,
    )


def _convert_inline(text: str,
                    resolve_variable: Callable[[str, Optional[str]], tuple],
                    escape_text: bool = True,
                    resolve_citation: Optional[Callable[[str], tuple]] = None) -> str:
    """Convert a single line of markdown prose to HTML.

    Escapes LaTeX/HTML special characters, preserves math and citations,
    and wraps {{VAR}} tokens with provenance spans.
    """
    store: dict[str, str] = {}
    counter = [0]

    # 1. Protect math FIRST so we can substitute variables inside it as plain
    # TeX (no span wrappers) and rewrite scientific notation into \times 10^N.
    def _protect_math(m: re.Match) -> str:
        content = m.group(0)
        def _math_var(vm: re.Match) -> str:
            display, _, _ = resolve_variable(vm.group(1), vm.group(2))
            return _prettify_sci_in_math(display)
        content = _VAR_RE.sub(_math_var, content)
        content = _prettify_sci_in_math(content)
        key = f'\x00M{counter[0]}\x00'
        store[key] = content
        counter[0] += 1
        return key

    text = re.sub(r'\$\$.+?\$\$', _protect_math, text, flags=re.DOTALL)
    text = re.sub(r'(?<!\$)\$(?!\$)[^$\n]+?\$(?!\$)', _protect_math, text)
    text = re.sub(r'\\\[.+?\\\]', _protect_math, text, flags=re.DOTALL)
    text = re.sub(r'\\\(.+?\\\)', _protect_math, text, flags=re.DOTALL)

    # 2. Now wrap any variable tokens left OUTSIDE math with provenance spans.
    var_spans: dict[str, str] = {}

    def _var_repl(m: re.Match) -> str:
        key = f'\x00V{counter[0]}\x00'
        var_spans[key] = _render_variable_span(m.group(1), m.group(2), resolve_variable)
        counter[0] += 1
        return key
    text = _VAR_RE.sub(_var_repl, text)

    # 3. Protect LaTeX commands whose args we don't want mangled (\cite, \ref, \label).
    def _cite(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(',') if k.strip()]
        key = f'\x00C{counter[0]}\x00'
        if resolve_citation is not None:
            pieces = []
            for k in keys:
                num, href = resolve_citation(k)
                if num is None:
                    pieces.append(
                        f'<span class="cite cite-missing" title="{_escape(k)}">?</span>'
                    )
                else:
                    target = href if href else f'#ref-{k}'
                    pieces.append(
                        f'<a class="cite" href="{_escape(target)}" title="{_escape(k)}">{num}</a>'
                    )
            store[key] = '[' + ', '.join(pieces) + ']'
        else:
            pretty = ', '.join(keys)
            store[key] = f'<span class="cite" title="{_escape(pretty)}">[{_escape(pretty)}]</span>'
        counter[0] += 1
        return key
    text = re.sub(r'\\cite[a-z]*\{([^{}]+)\}', _cite, text)

    def _ref(m: re.Match) -> str:
        key = f'\x00R{counter[0]}\x00'
        label = m.group(1)
        store[key] = f'<a class="ref" href="#{_escape(label)}">{_escape(label)}</a>'
        counter[0] += 1
        return key
    text = re.sub(r'\\(?:ref|eqref|pageref|autoref|nameref)\{([^{}]+)\}', _ref, text)

    # \label{foo} alone — emit an anchor
    def _label(m: re.Match) -> str:
        key = f'\x00L{counter[0]}\x00'
        store[key] = f'<a id="{_escape(m.group(1))}"></a>'
        counter[0] += 1
        return key
    text = re.sub(r'\\label\{([^{}]+)\}', _label, text)

    # 4. Protect inline code (already handled specially)
    def _code(m: re.Match) -> str:
        key = f'\x00K{counter[0]}\x00'
        inner = m.group(1)
        # Strip LaTeX escape sequences; in code/HTML we want the literal chars
        for esc, lit in [('\\_', '_'), ('\\&', '&'), ('\\%', '%'),
                         ('\\#', '#'), ('\\$', '$'),
                         ('\\{', '{'), ('\\}', '}')]:
            inner = inner.replace(esc, lit)
        store[key] = f'<code>{_escape(inner)}</code>'
        counter[0] += 1
        return key
    text = re.sub(r'(?<!`)`([^`]+?)`(?!`)', _code, text)

    # 4b. Convert \textit / \textbf / \emph / \texttt / \underline inline commands
    # (they leak through from LaTeX-native source docs).
    def _textit(m: re.Match) -> str:
        key = f'\x00T{counter[0]}\x00'
        store[key] = f'<em>{_escape(m.group(1))}</em>'
        counter[0] += 1
        return key
    text = re.sub(r'\\(?:textit|emph)\{([^{}]*)\}', _textit, text)

    def _textbf(m: re.Match) -> str:
        key = f'\x00T{counter[0]}\x00'
        store[key] = f'<strong>{_escape(m.group(1))}</strong>'
        counter[0] += 1
        return key
    text = re.sub(r'\\textbf\{([^{}]*)\}', _textbf, text)

    def _texttt(m: re.Match) -> str:
        key = f'\x00T{counter[0]}\x00'
        inner = m.group(1)
        for esc, lit in [('\\_', '_'), ('\\&', '&'), ('\\%', '%'),
                         ('\\#', '#')]:
            inner = inner.replace(esc, lit)
        store[key] = f'<code>{_escape(inner)}</code>'
        counter[0] += 1
        return key
    text = re.sub(r'\\texttt\{([^{}]*)\}', _texttt, text)
    # \underline{X} -> just X (no HTML equivalent without changing semantics)
    text = re.sub(r'\\underline\{([^{}]*)\}', r'\1', text)

    # 5. Now escape the remaining prose. Strip LaTeX escape sequences
    # (\_, \&, \%, \#, \$, \{, \}) first — they're LaTeX-only artifacts and
    # should display as the literal character in HTML.
    if escape_text:
        parts = re.split(r'(\x00[VMCRLKT]\d+\x00)', text)
        escaped = []
        for p in parts:
            if p in var_spans or p in store:
                escaped.append(p)
            else:
                for esc, lit in [('\\_', '_'), ('\\&', '&'), ('\\%', '%'),
                                 ('\\#', '#'), ('\\$', '$'),
                                 ('\\{', '{'), ('\\}', '}')]:
                    p = p.replace(esc, lit)
                escaped.append(_escape(p))
        text = ''.join(escaped)

    # 6. Convert markdown inline formatting
    # images first (so ![alt](url) doesn't collide with links)
    def _img(m: re.Match) -> str:
        alt, src, title = m.group(1), m.group(2), m.group(3)
        title_attr = f' title="{_escape(title)}"' if title else ''
        if src.lower().endswith('.html') or src.lower().endswith('.htm'):
            # interactive/plotly figure — embed as iframe
            return (f'<div class="figure-html">'
                    f'<iframe src="{_escape(src)}"{title_attr} '
                    f'class="w-full min-h-[400px] rounded-lg border" loading="lazy"></iframe>'
                    f'<p class="caption">{_escape(alt)}</p></div>')
        if src.lower().endswith('.pdf'):
            return (f'<div class="figure-pdf">'
                    f'<embed src="{_escape(src)}" type="application/pdf" '
                    f'class="w-full min-h-[500px] rounded-lg border"/>'
                    f'<p class="caption">{_escape(alt)}</p></div>')
        return (f'<figure class="figure-img">'
                f'<img src="{_escape(src)}" alt="{_escape(alt)}"{title_attr} '
                f'class="mx-auto max-w-full rounded-lg"/>'
                f'<figcaption class="caption">{_escape(alt)}</figcaption></figure>')
    text = _IMAGE_RE.sub(_img, text)

    # links
    def _lnk(m: re.Match) -> str:
        t, u, title = m.group(1), m.group(2), m.group(3)
        title_attr = f' title="{_escape(title)}"' if title else ''
        return f'<a href="{_escape(u)}"{title_attr}>{_escape(t)}</a>'
    text = _LINK_RE.sub(_lnk, text)

    # bold+italic ***...***
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # italic *...*
    text = re.sub(r'(?<!\w)\*([^*\n]+)\*(?!\w)', r'<em>\1</em>', text)

    # 7. Restore protected placeholders. Inner items (variables) may be nested
    # inside outer items (math), so restore OUTER first, then iterate both until
    # stable.
    combined = {**store, **var_spans}
    for _ in range(5):
        changed = False
        for key, val in combined.items():
            if key in text:
                text = text.replace(key, val)
                changed = True
        if not changed:
            break

    return text


def _convert_table(block_lines: list[str],
                   resolve_variable: Callable[[str, Optional[str]], tuple],
                   resolve_citation: Optional[Callable[[str], tuple]] = None) -> str:
    """Convert a markdown pipe-table to an HTML <table>."""
    if len(block_lines) < 2:
        return '\n'.join(block_lines)

    def _split_cells(row: str) -> list[str]:
        row = row.strip()
        if row.startswith('|'):
            row = row[1:]
        if row.endswith('|'):
            row = row[:-1]
        return [c.strip() for c in row.split('|')]

    header = _split_cells(block_lines[0])
    body_rows = [_split_cells(r) for r in block_lines[2:]]

    out = ['<table class="md-table">']
    out.append('<thead><tr>')
    for h in header:
        out.append(f'<th>{_convert_inline(h, resolve_variable, resolve_citation=resolve_citation)}</th>')
    out.append('</tr></thead>')
    out.append('<tbody>')
    for row in body_rows:
        out.append('<tr>')
        for c in row:
            out.append(f'<td>{_convert_inline(c, resolve_variable, resolve_citation=resolve_citation)}</td>')
        out.append('</tr>')
    out.append('</tbody></table>')
    return '\n'.join(out)


def md_to_html(md_content: str,
               resolve_variable: Callable[[str, Optional[str]], tuple],
               resolve_citation: Optional[Callable[[str], tuple]] = None) -> str:
    """Convert a markdown doc to an HTML fragment (not a full document).

    Args:
        md_content: Raw markdown including ```latex blocks and preview markers.
        resolve_variable: Callback (name, fmt) -> (display_text, provenance_dict_or_None,
                          is_defined_bool) used to render {{VAR}} tokens.
        resolve_citation: Callback (key) -> (number_int, href_str_or_None). If
                          provided, \\cite{key} renders as a numbered hyperlink
                          [N] pointing at #ref-key.
    """
    # Drop ```latex fences entirely (they're LaTeX-only passthrough)
    text = _LATEX_FENCE_RE.sub('', md_content)

    # Preview markers: keep the content, drop the <!-- markers -->
    def _unwrap_preview(m: re.Match) -> str:
        return m.group(1)
    text = _PREVIEW_BLOCK_RE.sub(_unwrap_preview, text)

    # Strip bare HTML comments (including the metadata ones we inserted for
    # section labels, figure captions in the source, etc.) UNLESS they wrap
    # label anchors — we keep those by converting <!-- \label{x} --> to anchors.
    text = re.sub(
        r'<!--\s*\\label\{([^{}]+)\}\s*-->',
        lambda m: f'<a id="{_escape(m.group(1))}"></a>',
        text,
    )
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # \FloatBarrier and the like — LaTeX-only, drop
    text = re.sub(r'\\FloatBarrier\b', '', text)

    lines = text.split('\n')
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            out.append('')
            i += 1
            continue

        # Code fence (non-latex)
        if stripped.startswith('```'):
            lang = stripped[3:].strip()
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing
            code_html = _escape('\n'.join(code_lines))
            lang_attr = f' data-lang="{_escape(lang)}"' if lang else ''
            out.append(f'<pre><code{lang_attr}>{code_html}</code></pre>')
            continue

        # Heading
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            level = len(m.group(1))
            raw_title = m.group(2)
            # If the comment-to-anchor step inserted a <a id="..."></a> inside
            # the title (from a <!-- \label{} --> trailing comment), lift that
            # label out to use as the heading id and strip the anchor from the
            # displayed title.
            label_ids = re.findall(r'<a id="([^"]+)"></a>', raw_title)
            clean_title = re.sub(r'<a id="[^"]+"></a>', '', raw_title).strip()
            slug = label_ids[0] if label_ids else slugify(clean_title)
            title_inline = _convert_inline(clean_title, resolve_variable, resolve_citation=resolve_citation)
            extra_anchors = ''.join(
                f'<a id="{lid}"></a>' for lid in label_ids[1:]
            )
            out.append(f'<h{level} id="{slug}">{title_inline}</h{level}>{extra_anchors}')
            i += 1
            continue

        # Horizontal rule / page break
        if re.match(r'^---+$', stripped) or re.match(r'^\*\*\*+$', stripped):
            out.append('<hr/>')
            i += 1
            continue

        # Unordered list
        if re.match(r'^[-*+]\s', stripped):
            out.append('<ul>')
            while i < n and re.match(r'^\s*[-*+]\s', lines[i]):
                item = re.sub(r'^\s*[-*+]\s+', '', lines[i])
                out.append(f'<li>{_convert_inline(item, resolve_variable, resolve_citation=resolve_citation)}</li>')
                i += 1
            out.append('</ul>')
            continue

        # Ordered list
        if re.match(r'^\d+\.\s', stripped):
            out.append('<ol>')
            while i < n and re.match(r'^\s*\d+\.\s', lines[i]):
                item = re.sub(r'^\s*\d+\.\s+', '', lines[i])
                out.append(f'<li>{_convert_inline(item, resolve_variable, resolve_citation=resolve_citation)}</li>')
                i += 1
            out.append('</ol>')
            continue

        # Table: pipe-separated with `|---|` separator row
        if '|' in stripped and i + 1 < n and re.match(r'^\s*\|?\s*[-:]+', lines[i + 1]):
            block = []
            while i < n and '|' in lines[i].strip():
                block.append(lines[i])
                i += 1
            out.append(_convert_table(block, resolve_variable, resolve_citation))
            continue

        # Blockquote
        if stripped.startswith('>'):
            quote_lines = []
            while i < n and lines[i].strip().startswith('>'):
                quote_lines.append(lines[i].strip().lstrip('>').strip())
                i += 1
            out.append('<blockquote>'
                       + _convert_inline(' '.join(quote_lines), resolve_variable,
                                         resolve_citation=resolve_citation)
                       + '</blockquote>')
            continue

        # Regular paragraph — gather until blank line / block boundary
        para_lines = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            out.append(f'<p>{_convert_inline(" ".join(para_lines), resolve_variable, resolve_citation=resolve_citation)}</p>')
            continue
        i += 1

    return '\n'.join(out)


def _is_block_start(line: str) -> bool:
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
