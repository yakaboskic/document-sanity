#!/usr/bin/env python3
"""
Markdown → Word document body (via ContentBuilder).

Block-level scanner modeled on md2html.py. Inline formatting is emitted as
RichText spans (bold/italic/mono) rather than HTML tags, since the target is
OOXML runs inside <w:p>.

Pass-through ```latex fences:
  - Prefer the sibling `<!-- document-sanity:preview:begin/end -->` block if one
    exists — its contents are markdown-native (images as ![](...), tables as
    `| ... |`, math as $$...$$) and render cleanly in Word. This matches how
    md2html resolves the same situation.
  - If no preview block is present and the fence contains `\\includegraphics`,
    we extract the image path + caption and emit an embedded figure.
  - Otherwise the fence is dropped.
  - A labeled figure's caption is numbered the way LaTeX numbers it
    ("Figure 2: ..."), and \\ref{key} renders as that number. The caller
    passes the label map from labels.collect_labels.

Citations (\\cite{key}) register with the builder via register_citation() and
render as "[N]" inline; the caller emits the References section separately.
Inline `code` and non-latex fences are verbatim: a `\\cite{key}` in backticks
shows as written and registers nothing.

Variable tokens ({{VAR}} / {{VAR:fmt}}) are pre-substituted by the caller via
VariableProcessor before we get here — we don't re-substitute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .docx_content import ContentBuilder, TextStyle
from .docx_math import DISPLAY_RE, INLINE_RE, MathCache, scan
from .docx_xml import RichText
from .verbatim import mask_code, unmask_code


# ---- regex library ---------------------------------------------------------

_LATEX_FENCE_RE = re.compile(
    r"^```latex\s*\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
_PREVIEW_BLOCK_RE = re.compile(
    r"<!--\s*(?:document-sanity|latex-builder):preview:begin[^>]*-->\s*(.*?)"
    r"\s*<!--\s*(?:document-sanity|latex-builder):preview:end\s*-->",
    re.DOTALL,
)
_CITE_RE = re.compile(r"\\cite[a-z]*\{([^{}]+)\}")
_REF_RE = re.compile(r"\\(?:ref|eqref|pageref|autoref|nameref)\{([^{}]+)\}")
_LABEL_RE = re.compile(r"\\label\{([^{}]+)\}")
_IMAGE_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
_LINK_MD_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
# A ```latex fence immediately followed by its preview block. The body may not
# contain ``` so a fence without a preview can't swallow a later fence's preview.
_FENCE_THEN_PREVIEW_RE = re.compile(
    r"^```latex[ \t]*\n((?:(?!```)[\s\S])*?)^```[ \t]*$\s*"
    r"<!--\s*(?:document-sanity|latex-builder):preview:begin[^>]*-->\s*(.*?)"
    r"\s*<!--\s*(?:document-sanity|latex-builder):preview:end\s*-->",
    re.MULTILINE | re.DOTALL,
)


FigureResolver = Callable[[str], Optional[Path]]
CitationHandler = Callable[[str], int]
# {label key: (kind name, number)}, e.g. {"fig:arch": ("Figure", 2)}
Labels = dict[str, tuple[str, int]]


@dataclass
class RenderContext:
    builder: ContentBuilder
    figure_resolver: Optional[FigureResolver] = None
    figures_dir: Optional[Path] = None
    section_path: str = ""
    labels: Optional[Labels] = None
    math: Optional[MathCache] = None
    # Figure captions taken from the LaTeX fence (bold, italics, math and citations
    # kept), keyed by the sentinel that replaces the preview image's alt text.
    captions: list[str] = field(default_factory=list)


# ---- entry point -----------------------------------------------------------

def render_markdown(
    md: str,
    builder: ContentBuilder,
    *,
    figure_resolver: Optional[FigureResolver] = None,
    figures_dir: Optional[Path] = None,
    section_path: str = "",
    labels: Optional[Labels] = None,
) -> None:
    """Render a markdown document into the given ContentBuilder."""
    ctx = RenderContext(
        builder=builder,
        figure_resolver=figure_resolver,
        figures_dir=figures_dir,
        section_path=section_path,
        labels=labels,
        math=MathCache(),
    )

    # 0. A fence with a preview block renders from the preview alone (its
    #    labels only number the caption); rendering both duplicated figures.
    def _prefer_preview(m: re.Match) -> str:
        prefix = _caption_prefix(m.group(1), ctx)
        preview = m.group(2)
        rich = _latex_caption_markdown(m.group(1))
        if rich is not None:
            # The preview's alt text has lost the caption's formatting; carry the
            # LaTeX caption (as markdown) to the image through a sentinel.
            ctx.captions.append(prefix + rich)
            key = f"\x03CAP{len(ctx.captions) - 1}\x03"
            preview = _IMAGE_MD_RE.sub(lambda im: f"![{key}]({im.group(2)})", preview, count=1)
        elif prefix:
            preview = _IMAGE_MD_RE.sub(
                lambda im: f"![{prefix}{im.group(1)}]({im.group(2)})", preview, count=1
            )
        return f"\n{preview}\n"

    md = _FENCE_THEN_PREVIEW_RE.sub(_prefer_preview, md)

    # 1. Replace ```latex blocks with a sentinel that we'll handle in the
    #    block loop. Preserves order relative to surrounding markdown.
    latex_blocks: list[str] = []

    def _stash_latex(m: re.Match) -> str:
        latex_blocks.append(m.group(1))
        idx = len(latex_blocks) - 1
        return f"\n\x00LATEX{idx}\x00\n"

    text = _LATEX_FENCE_RE.sub(_stash_latex, md)

    # Code is verbatim: hold it out of steps 2-4b, back in for the block walk.
    text, code = mask_code(text)

    # 2. Unwrap preview blocks — keep the inner content (markdown-native).
    text = _PREVIEW_BLOCK_RE.sub(lambda m: m.group(1), text)

    # 3. Drop HTML comments (metadata markers, stray label markers, etc.)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # 4. Strip LaTeX-only floats
    text = re.sub(r"\\FloatBarrier\b", "", text)

    # 4b. Convert every math snippet of the section in one batch (pandoc):
    #     $$...$$ and $...$ in the markdown, and math environments in fences.
    snippets = scan(text)
    for block in latex_blocks:
        env = _MATH_ENV_RE.search(block)
        if env:
            snippets.append((env.group(2), True))
    ctx.math.prefetch(snippets)
    text = unmask_code(text, code)

    # 5. Block-level walk.
    lines = text.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Latex sentinel — process the stashed block.
        sentinel_m = re.match(r"\x00LATEX(\d+)\x00", stripped)
        if sentinel_m:
            block = latex_blocks[int(sentinel_m.group(1))]
            _render_latex_block(block, ctx)
            i += 1
            continue

        # Display math: $$ ... $$ on one line or across several.
        if stripped.startswith("$$"):
            chunk = [line]
            while not DISPLAY_RE.search("\n".join(chunk)) and i + 1 < n:
                i += 1
                chunk.append(lines[i])
            i += 1
            joined = "\n".join(chunk)
            for m in DISPLAY_RE.finditer(joined):
                _render_display_math(m.group(1), ctx)
            continue

        # Fenced code (non-latex).
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            code_lines: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            _render_code_block("\n".join(code_lines), lang, ctx)
            continue

        # Heading.
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            title = m.group(2)
            # Strip any inline \label{} from the title
            title = _LABEL_RE.sub("", title).strip()
            if level == 1:
                builder.h1(title)
            elif level == 2:
                builder.h2(title)
            elif level == 3:
                builder.h3(title)
            else:
                builder.label(title)
            i += 1
            continue

        # Horizontal rule -> page break.
        if re.match(r"^---+$", stripped) or re.match(r"^\*\*\*+$", stripped):
            builder.page_break()
            i += 1
            continue

        # Unordered list.
        if re.match(r"^[-*+]\s", stripped):
            while i < n and re.match(r"^\s*[-*+]\s", lines[i]):
                item = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                builder.bullet(_inline_to_rich(item, ctx))
                i += 1
            continue

        # Ordered list.
        if re.match(r"^\d+\.\s", stripped):
            while i < n and re.match(r"^\s*\d+\.\s", lines[i]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                builder.numbered(_inline_to_rich(item, ctx))
                i += 1
            continue

        # Table.
        if "|" in stripped and i + 1 < n and re.match(r"^\s*\|?\s*[-:]+", lines[i + 1]):
            block: list[str] = []
            while i < n and "|" in lines[i].strip():
                block.append(lines[i])
                i += 1
            _render_table(block, ctx)
            continue

        # Blockquote -> note.
        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            builder.note(_rich_to_text(_inline_to_rich(" ".join(quote_lines), ctx)),
                         type_="info", label="")
            continue

        # Paragraph — gather until blank line / block boundary.
        para_lines: list[str] = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            builder.p(_inline_to_rich(" ".join(para_lines), ctx))
            continue
        i += 1


def render_notice(text: str, builder: ContentBuilder) -> None:
    """Render manifest.metadata.notice: each paragraph centered, italic and
    in the small font size, set apart at the top of the body."""
    ctx = RenderContext(builder=builder)
    s = builder.styles
    style = TextStyle(
        alignment="center",
        italic=True,
        size=s["fontSizes"]["small"],
        spacing_after=s["spacing"]["paragraph"]["afterSmall"],
    )
    for para in re.split(r"\n\s*\n", text.strip()):
        builder.p(_inline_to_rich(" ".join(para.split()), ctx), style)


# ---- block helpers --------------------------------------------------------

def _render_code_block(code: str, lang: str, ctx: RenderContext) -> None:
    # Render as a single paragraph in monospace at small size.
    style = TextStyle(
        font=ctx.builder.styles["fonts"]["mono"],
        size=ctx.builder.styles["fontSizes"]["small"],
    )
    for line in code.split("\n"):
        ctx.builder.p(line if line else " ", style)


def _render_table(block_lines: list[str], ctx: RenderContext) -> None:
    if len(block_lines) < 2:
        return

    def _split_cells(row: str) -> list[str]:
        row = row.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [c.strip() for c in row.split("|")]

    headers = _split_cells(block_lines[0])
    body_rows = [_split_cells(r) for r in block_lines[2:]]
    # Pass list[RichText] per cell so create_table can emit one <w:r>
    # per run, preserving sup/sub/bold/italic/code formatting inside
    # cells. (Was previously flattened to plain text via _rich_to_text,
    # which dropped R<sup>2</sup> formatting in the rendered table.)
    rich_headers = [_inline_to_rich(h, ctx) for h in headers]
    rich_rows = [[_inline_to_rich(c, ctx) for c in row] for row in body_rows]
    ctx.builder.table(rich_headers, rich_rows)


def _render_latex_block(body: str, ctx: RenderContext) -> None:
    """Handle a ```latex ... ``` fence.

    We look for:
      - figure/figure*  -> embed image if resolvable, caption as italic line
      - equation/align/gather/multline -> render as mono block
      - anything else -> drop (labels were preserved outside by caller's preview
        block unwrap; nothing else renders meaningfully in Word).
    """
    env_match = re.search(r"\\begin\{([a-zA-Z*]+)\}([\s\S]*?)\\end\{\1\}", body)
    if not env_match:
        return
    env = env_match.group(1).rstrip("*")
    inner = env_match.group(2)

    if env == "figure":
        _render_latex_figure(inner, ctx)
        return

    if env in {"equation", "align", "gather", "multline", "eqnarray"}:
        if ctx.math is not None and _render_display_math(env_match.group(0), ctx):
            return
        style = TextStyle(
            font=ctx.builder.styles["fonts"]["mono"],
            size=ctx.builder.styles["fontSizes"]["small"],
            alignment="center",
            italic=True,
        )
        cleaned = inner.strip()
        if cleaned:
            ctx.builder.p(cleaned, style)
        return

    if env in {"table", "tabular"}:
        # Minimal fallback — surface as caption-only placeholder so the reader
        # at least sees that a table was here.
        caption = _extract_latex_caption(inner) or "[LaTeX table]"
        ctx.builder.image_placeholder(caption=caption, description="")
        return


_MATH_ENV_RE = re.compile(
    r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?)\}([\s\S]*?)\\end\{\1\}"
)


def _render_display_math(tex: str, ctx: RenderContext) -> bool:
    """A display equation as Office Math; the LaTeX source as centred italic
    text when it cannot be converted. Returns whether Office Math was written."""
    m = _MATH_ENV_RE.search(tex)
    if m:  # a whole environment: convert its body (aligned when it is an align)
        body = m.group(2)
        tex = f"\\begin{{aligned}}{body}\\end{{aligned}}" if m.group(1).startswith(("align", "eqnarray")) else body
    omml = ctx.math.get(tex.strip(), True) if ctx.math is not None else None
    if omml:
        ctx.builder.raw(f'<w:p><w:pPr><w:spacing w:before="120" w:after="120"/></w:pPr>{omml}</w:p>')
        return True
    style = TextStyle(
        font=ctx.builder.styles["fonts"]["mono"],
        size=ctx.builder.styles["fontSizes"]["small"],
        alignment="center",
        italic=True,
    )
    ctx.builder.p(tex.strip(), style)
    return False


def _render_latex_figure(inner: str, ctx: RenderContext) -> None:
    # Two path sources:
    #   1. {{fig:id}} token -> resolve via figure_resolver(id)
    #   2. \includegraphics[...]{path}
    caption = _extract_latex_caption(inner) or ""
    if caption:
        caption = _caption_prefix(inner, ctx) + caption

    fig_token = re.search(r"\{\{fig:([A-Za-z0-9_]+)\}\}", inner)
    path: Optional[Path] = None
    if fig_token and ctx.figure_resolver:
        path = ctx.figure_resolver(fig_token.group(1))

    if path is None:
        inc = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", inner)
        if inc and ctx.figures_dir is not None:
            raw = inc.group(1).strip()
            candidate = Path(raw)
            if not candidate.is_absolute():
                # figures_dir is the run-local figures directory; paths in the
                # latex block may be "figures/foo" (paper-repo style).
                candidate = ctx.figures_dir.parent / raw
            if candidate.exists():
                path = candidate
            elif (ctx.figures_dir / Path(raw).name).exists():
                path = ctx.figures_dir / Path(raw).name

    if path is not None and _image_supported(path):
        ctx.builder.image(path, caption=caption or None, alt_text=caption)
    else:
        ctx.builder.image_placeholder(caption=caption or "[figure]", description="")


def _caption_prefix(latex: str, ctx: RenderContext) -> str:
    """"Figure 2: " for a fence whose figure label is in the label map, so
    the Word caption carries the number LaTeX prints and \\ref points to."""
    for key in _LABEL_RE.findall(latex):
        kind, num = (ctx.labels or {}).get(key, ("", 0))
        if kind == "Figure":
            return f"{kind} {num}: "
    return ""


def _latex_caption_markdown(block: str) -> Optional[str]:
    """The \\caption{...} of a LaTeX figure as inline markdown: \\textbf and \\textit
    become ** and *, while citations, references, math and escapes stay for the
    inline renderer. None when the block has no caption."""
    m = re.search(r"\\caption\s*\{", block)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(block) and depth:
        depth += {"{": 1, "}": -1}.get(block[i], 0) if block[i - 1] != "\\" else 0
        i += 1
    if depth:
        return None
    body = block[m.end() : i - 1]
    for _ in range(3):  # nested formatting, innermost first
        body = re.sub(r"\\textbf\{([^{}]*)\}", r"**\1**", body)
        body = re.sub(r"\\(?:textit|emph)\{([^{}]*)\}", r"*\1*", body)
    body = re.sub(r"\\label\{[^{}]*\}", "", body)
    return re.sub(r"\s+", " ", body).strip()


def _extract_latex_caption(inner: str) -> Optional[str]:
    # Find \caption{...} allowing one level of nested braces.
    m = re.search(r"\\caption\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", inner)
    if not m:
        return None
    cap = m.group(1).strip()
    # Strip LaTeX inline markup that we can't render
    cap = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", cap)
    cap = re.sub(r"\\textit\{([^{}]*)\}", r"\1", cap)
    cap = re.sub(r"\\emph\{([^{}]*)\}", r"\1", cap)
    cap = re.sub(r"\\label\{[^{}]+\}", "", cap).strip()
    return cap


def _image_supported(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


# ---- inline rendering -----------------------------------------------------

def _inline_to_rich(text: str, ctx: RenderContext) -> list[RichText]:
    """Parse inline markdown into RichText runs.

    Handles: **bold**, *italic*, `code`, \\cite{}, \\ref{}, links, images
    (images inline — we emit an image drawing + caption before this call
    returns, via register_embedded_image). Math is left as literal text.
    """
    # `code` is literal: hold it out of every pass below (images, math, links,
    # \cite/\ref/\label) until the tokenizer gives it the Code style.
    text, code = mask_code(text)

    # Pull out ![alt](path) images first — they're rendered as their own
    # paragraph in Word, so we emit the drawing now and drop the token.
    def _image_pull(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        cap = re.fullmatch(r"\x03CAP(\d+)\x03", alt)
        caption: object = unmask_code(alt, code) or None
        if cap:  # the LaTeX caption, rendered with its formatting, math and citations
            md = ctx.captions[int(cap.group(1))]
            caption = _inline_to_rich(md, ctx)
            alt = _rich_to_text(caption)
        p = _resolve_relative_image(src, ctx)
        if p and _image_supported(p):
            ctx.builder.image(p, caption=caption, alt_text=unmask_code(alt, code) or "")
            return ""
        # Fallback: show alt text in brackets so nothing is silently lost.
        return f"[{alt}]"

    text = _IMAGE_MD_RE.sub(_image_pull, text)

    # Inline math -> sentinels, expanded to Office Math runs after tokenizing
    # (before the escape stripping below, which would unescape \$ into $).
    math_runs: list[RichText] = []

    def _math(m: re.Match) -> str:
        tex = m.group(1)
        omml = ctx.math.get(tex, False) if ctx.math is not None else None
        math_runs.append(RichText(text="" if omml else tex, italic=None if omml else True, omml=omml))
        return f"\x02{len(math_runs) - 1}\x02"

    text = INLINE_RE.sub(_math, text)

    # Links — keep the display text, drop the URL.
    text = _LINK_MD_RE.sub(lambda m: m.group(1), text)

    # \cite{}, \ref{}, \label{}
    def _cite(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
        nums = [str(ctx.builder.register_citation(k)) for k in keys]
        return "[" + ", ".join(nums) + "]"

    text = _CITE_RE.sub(_cite, text)

    def _ref(m: re.Match) -> str:
        # Just the number, as LaTeX's \ref prints it; the prose supplies the
        # noun ("Figure \ref{fig:x}"). Unknown labels fall back to the key.
        found = (ctx.labels or {}).get(m.group(1))
        return str(found[1]) if found else m.group(1)

    text = _REF_RE.sub(_ref, text)
    text = _LABEL_RE.sub("", text)

    # Strip LaTeX escape sequences that don't belong in plain prose (or code),
    # then put the code back.
    text = unmask_code(_strip_tex_escapes(text), [_strip_tex_escapes(c) for c in code])

    # Now tokenize for bold/italic/code.
    return _expand_math(_tokenize_inline(text), math_runs)


def _strip_tex_escapes(text: str) -> str:
    for esc, lit in [
        (r"\_", "_"), (r"\&", "&"), (r"\%", "%"),
        (r"\#", "#"), (r"\$", "$"), (r"\{", "{"), (r"\}", "}"),
    ]:
        text = text.replace(esc, lit)
    return text


def _expand_math(runs: list[RichText], math_runs: list[RichText]) -> list[RichText]:
    """Split runs at inline-math sentinels and put the math runs in their place."""
    if not math_runs:
        return runs
    out: list[RichText] = []
    for run in runs:
        if "\x02" not in run.text:
            out.append(run)
            continue
        for k, piece in enumerate(run.text.split("\x02")):
            if k % 2:
                out.append(math_runs[int(piece)])
            elif piece:
                out.append(RichText(text=piece, bold=run.bold, italic=run.italic, color=run.color,
                                    font=run.font, size=run.size, rstyle=run.rstyle,
                                    vert_align=run.vert_align))
    return out


def _resolve_relative_image(src: str, ctx: RenderContext) -> Optional[Path]:
    if not src:
        return None
    # Ignore remote images.
    if src.startswith(("http://", "https://", "data:")):
        return None
    p = Path(src)
    if p.is_absolute() and p.exists():
        return p
    if ctx.figures_dir is not None:
        # Try (figures_dir.parent)/src first, then figures_dir/basename.
        for base in (ctx.figures_dir.parent, ctx.figures_dir):
            candidate = (base / src).resolve()
            if candidate.exists():
                return candidate
        # Last-ditch: basename only.
        candidate = ctx.figures_dir / Path(src).name
        if candidate.exists():
            return candidate
    return None


# Inline tokenizer: walks the string, emitting RichText spans.
#
# Recognized markers (outside of `backticks`):
#   ***x*** / ___x___      -> bold + italic
#   **x** / __x__          -> bold
#   *x* / _x_              -> italic
#   `x`                    -> monospace
#
# Nesting is flat (don't try to parse bold-inside-italic cross-combinations —
# the wordy markdown cases we see in papers don't exercise that).

def _tokenize_inline(text: str) -> list[RichText]:
    runs: list[RichText] = []
    i = 0
    n = len(text)
    buf: list[str] = []
    active_bold = False
    active_italic = False

    def flush(extra_font: Optional[str] = None):
        if not buf:
            return
        runs.append(RichText(
            text="".join(buf),
            bold=True if active_bold else None,
            italic=True if active_italic else None,
            font=extra_font,
        ))
        buf.clear()

    # Pre-process super/subscript markers — both <sup>X</sup> /
    # <sub>X</sub> (the portable form) and \textsuperscript{X} /
    # \textsubscript{X} (LaTeX-native source). Replace with sentinel
    # markers we can detect during the inline scan below, since the
    # tokenizer otherwise has no notion of nested runs.
    SUP_OPEN, SUP_CLOSE = "\x01SUP\x01", "\x01/SUP\x01"
    SUB_OPEN, SUB_CLOSE = "\x01SUB\x01", "\x01/SUB\x01"
    text = re.sub(r'<sup>(.+?)</sup>', lambda m: f'{SUP_OPEN}{m.group(1)}{SUP_CLOSE}', text, flags=re.IGNORECASE)
    text = re.sub(r'<sub>(.+?)</sub>', lambda m: f'{SUB_OPEN}{m.group(1)}{SUB_CLOSE}', text, flags=re.IGNORECASE)
    text = re.sub(r'\\textsuperscript\{([^{}]*)\}', lambda m: f'{SUP_OPEN}{m.group(1)}{SUP_CLOSE}', text)
    text = re.sub(r'\\textsubscript\{([^{}]*)\}', lambda m: f'{SUB_OPEN}{m.group(1)}{SUB_CLOSE}', text)
    n = len(text)

    while i < n:
        ch = text[i]

        # Super/subscript sentinels emitted by the pre-pass above.
        if text.startswith(SUP_OPEN, i):
            flush()
            j = text.find(SUP_CLOSE, i + len(SUP_OPEN))
            if j != -1:
                runs.append(RichText(
                    text=text[i + len(SUP_OPEN) : j],
                    vert_align="superscript",
                    bold=True if active_bold else None,
                    italic=True if active_italic else None,
                ))
                i = j + len(SUP_CLOSE)
                continue
        if text.startswith(SUB_OPEN, i):
            flush()
            j = text.find(SUB_CLOSE, i + len(SUB_OPEN))
            if j != -1:
                runs.append(RichText(
                    text=text[i + len(SUB_OPEN) : j],
                    vert_align="subscript",
                    bold=True if active_bold else None,
                    italic=True if active_italic else None,
                ))
                i = j + len(SUB_CLOSE)
                continue

        # Backtick-delimited code span. Apply the template's "Code"
        # character style (rStyle) so the template author's choice of
        # mono font, color, and size propagates here. If the template
        # doesn't define a Code character style, the run still renders
        # (just without monospace) — author can add one to fix that.
        # _tokenize_inline doesn't take ctx, so we can't fall back to
        # ctx.builder.styles["fonts"]["mono"] here; the rstyle is the
        # cleanest path either way.
        if ch == "`":
            flush()
            j = text.find("`", i + 1)
            if j == -1:
                buf.append(ch)
                i += 1
                continue
            runs.append(RichText(
                text=text[i + 1 : j],
                rstyle="Code",
            ))
            i = j + 1
            continue

        # Bold+italic ***x*** / ___x___
        if text.startswith("***", i) or text.startswith("___", i):
            flush()
            marker = text[i : i + 3]
            end = text.find(marker, i + 3)
            if end == -1:
                buf.append(ch)
                i += 1
                continue
            runs.append(RichText(text=text[i + 3 : end], bold=True, italic=True))
            i = end + 3
            continue

        # Bold **x** / __x__
        if text.startswith("**", i) or text.startswith("__", i):
            flush()
            marker = text[i : i + 2]
            end = text.find(marker, i + 2)
            if end == -1:
                buf.append(ch)
                i += 1
                continue
            runs.append(RichText(text=text[i + 2 : end], bold=True))
            i = end + 2
            continue

        # Italic *x* / _x_ (require word boundary to avoid eating snake_case)
        if ch in "*_":
            prev = text[i - 1] if i > 0 else ""
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt and nxt != ch and not nxt.isspace():
                end = text.find(ch, i + 1)
                if end != -1 and end > i + 1:
                    candidate_after = text[end + 1 : end + 2]
                    if not candidate_after.isalnum():
                        flush()
                        runs.append(RichText(text=text[i + 1 : end], italic=True))
                        i = end + 1
                        continue

        buf.append(ch)
        i += 1

    flush()
    return runs


def _rich_to_text(runs: list[RichText]) -> str:
    return "".join(r.text for r in runs)


# ---- block-start detection (mirrors md2html._is_block_start) --------------

def _is_block_start(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    if stripped.startswith("```"):
        return True
    if stripped.startswith("$$"):
        return True
    if re.match(r"^---+$", stripped) or re.match(r"^\*\*\*+$", stripped):
        return True
    if stripped.startswith(">"):
        return True
    if re.match(r"^[-*+]\s", stripped):
        return True
    if re.match(r"^\d+\.\s", stripped):
        return True
    if stripped.startswith("\x00LATEX"):
        return True
    return False
