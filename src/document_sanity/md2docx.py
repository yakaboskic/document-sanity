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

Citations (\\cite{key}) register with the builder via register_citation() and
render as "[N]" inline; the caller emits the References section separately.

Variable tokens ({{VAR}} / {{VAR:fmt}}) are pre-substituted by the caller via
VariableProcessor before we get here — we don't re-substitute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .docx_content import ContentBuilder, TextStyle
from .docx_xml import RichText


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


FigureResolver = Callable[[str], Optional[Path]]
CitationHandler = Callable[[str], int]


@dataclass
class RenderContext:
    builder: ContentBuilder
    figure_resolver: Optional[FigureResolver] = None
    figures_dir: Optional[Path] = None
    section_path: str = ""


# ---- entry point -----------------------------------------------------------

def render_markdown(
    md: str,
    builder: ContentBuilder,
    *,
    figure_resolver: Optional[FigureResolver] = None,
    figures_dir: Optional[Path] = None,
    section_path: str = "",
) -> None:
    """Render a markdown document into the given ContentBuilder."""
    ctx = RenderContext(
        builder=builder,
        figure_resolver=figure_resolver,
        figures_dir=figures_dir,
        section_path=section_path,
    )

    # 1. Replace ```latex blocks with a sentinel that we'll handle in the
    #    block loop. Preserves order relative to surrounding markdown.
    latex_blocks: list[str] = []

    def _stash_latex(m: re.Match) -> str:
        latex_blocks.append(m.group(1))
        idx = len(latex_blocks) - 1
        return f"\n\x00LATEX{idx}\x00\n"

    text = _LATEX_FENCE_RE.sub(_stash_latex, md)

    # 2. Unwrap preview blocks — keep the inner content (markdown-native).
    text = _PREVIEW_BLOCK_RE.sub(lambda m: m.group(1), text)

    # 3. Drop HTML comments (metadata markers, stray label markers, etc.)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # 4. Strip LaTeX-only floats
    text = re.sub(r"\\FloatBarrier\b", "", text)

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


def _render_latex_figure(inner: str, ctx: RenderContext) -> None:
    # Two path sources:
    #   1. {{fig:id}} token -> resolve via figure_resolver(id)
    #   2. \includegraphics[...]{path}
    caption = _extract_latex_caption(inner) or ""

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
    # Pull out ![alt](path) images first — they're rendered as their own
    # paragraph in Word, so we emit the drawing now and drop the token.
    def _image_pull(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        p = _resolve_relative_image(src, ctx)
        if p and _image_supported(p):
            ctx.builder.image(p, caption=alt or None, alt_text=alt or "")
            return ""
        # Fallback: show alt text in brackets so nothing is silently lost.
        return f"[{alt}]"

    text = _IMAGE_MD_RE.sub(_image_pull, text)

    # Links — keep the display text, drop the URL.
    text = _LINK_MD_RE.sub(lambda m: m.group(1), text)

    # \cite{}, \ref{}, \label{}
    def _cite(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
        nums = [str(ctx.builder.register_citation(k)) for k in keys]
        return "[" + ", ".join(nums) + "]"

    text = _CITE_RE.sub(_cite, text)
    text = _REF_RE.sub(lambda m: m.group(1), text)
    text = _LABEL_RE.sub("", text)

    # Strip LaTeX escape sequences that don't belong in plain prose.
    for esc, lit in [
        (r"\_", "_"), (r"\&", "&"), (r"\%", "%"),
        (r"\#", "#"), (r"\$", "$"), (r"\{", "{"), (r"\}", "}"),
    ]:
        text = text.replace(esc, lit)

    # Now tokenize for bold/italic/code.
    return _tokenize_inline(text)


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
