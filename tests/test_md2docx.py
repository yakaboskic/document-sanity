"""Word rendering of ```latex figures: a fence with a preview block renders once
(from the preview), captions carry the LaTeX figure number, and \\ref{} renders
as that number rather than the raw label key."""

import re

from PIL import Image

from document_sanity.docx_content import ContentBuilder
from document_sanity.docx_styles import default_styles
from document_sanity.md2docx import render_markdown


FIGURE = """\
See Figure \\ref{fig:arch} for the layout.

```latex
\\begin{figure}[h!]
    \\centering
    \\includegraphics[width=\\textwidth]{figures/arch.png}
    \\caption{System architecture.}
    \\label{fig:arch}
\\end{figure}
```

<!-- document-sanity:preview:begin hash=abc12345 -->
![System architecture.](../figures/arch/arch.png)
<!-- document-sanity:preview:end -->

After the figure.
"""

LABELS = {"fig:arch": ("Figure", 2)}


def _render(tmp_path, md, labels=LABELS):
    fig_dir = tmp_path / "figures" / "arch"
    fig_dir.mkdir(parents=True)
    Image.new("RGB", (4, 2), "white").save(fig_dir / "arch.png")
    builder = ContentBuilder(default_styles())
    render_markdown(md, builder, figures_dir=tmp_path / "figures", labels=labels)
    xml = builder.to_xml()
    text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))
    return builder, text


def test_fence_with_preview_renders_the_figure_once(tmp_path):
    builder, text = _render(tmp_path, FIGURE)

    assert len(builder.pending_images) == 1
    # No "[caption]" placeholder from the fence alongside the preview's image.
    assert "[System architecture.]" not in text
    assert text.count("System architecture.") == 1


def test_caption_carries_the_latex_figure_number(tmp_path):
    _, text = _render(tmp_path, FIGURE)

    assert "Figure 2: System architecture." in text


def test_ref_renders_as_the_number_even_before_the_figure(tmp_path):
    _, text = _render(tmp_path, FIGURE)

    assert "See Figure 2 for the layout." in text
    assert "fig:arch" not in text


def test_unknown_ref_falls_back_to_the_key(tmp_path):
    _, text = _render(tmp_path, FIGURE, labels={})

    assert "See Figure fig:arch for the layout." in text
    assert "Figure 2:" not in text


def test_fence_without_preview_does_not_swallow_a_later_preview(tmp_path):
    md = (
        "```latex\n\\begin{equation}\nE = mc^2\n\\label{eq:e}\n\\end{equation}\n```\n\n"
        "Between the blocks.\n\n" + FIGURE
    )
    builder, text = _render(tmp_path, md)

    assert "Between the blocks." in text
    assert "E = mc^2" in text
    assert len(builder.pending_images) == 1
