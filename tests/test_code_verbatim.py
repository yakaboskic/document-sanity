"""Code is verbatim in every target: `\\cite{key}` in an inline code span, or
anything in a non-LaTeX fence, is syntax to show, not a citation, reference,
label, variable or comment to process. The starter manuscript relies on this
to document its own markup ("Cite with `\\cite{key}` ...")."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from document_sanity import init_project as ip
from document_sanity.docx_builder import WordBuilder
from document_sanity.docx_content import ContentBuilder
from document_sanity.docx_styles import default_styles
from document_sanity.html_builder import build_html
from document_sanity.labels import collect_labels
from document_sanity.md2docx import render_markdown
from document_sanity.md2html import md_to_html
from document_sanity.md2latex import md_to_latex

CITE = "Cite with `\\cite{key}` and for real: \\cite{real}."
REF = "Cross-reference with `\\ref{...}` — see Figure \\ref{fig:x}."
FENCE = """\
```markdown
# Methods <!-- \\label{sec:m} -->
<!-- a comment -->
See \\cite{key}, \\ref{fig:x} and {{N}} at ![a](../figures/x/x.png).
```
"""


# ── HTML ─────────────────────────────────────────────────────────────────────

def _var(name, fmt):
    return (f"<{name}>", None, True, None)


def _html(md):
    cited: list[str] = []

    def cite(key):
        cited.append(key)
        return (1, f"#ref-{key}") if key == "real" else (None, None)

    def ref(key):
        return ("1", f"#{key}") if key == "fig:x" else (key, f"#{key}")

    return md_to_html(md, _var, resolve_citation=cite, resolve_ref=ref), cited


def test_html_inline_cite_stays_literal_next_to_a_real_one():
    html, cited = _html(CITE)

    assert "<code>\\cite{key}</code>" in html
    assert '[<a class="cite" href="#ref-real" title="real">1</a>]' in html
    assert "cite-missing" not in html
    assert cited == ["real"]  # the key in code is never numbered


def test_html_inline_ref_stays_literal_next_to_a_real_one():
    html, _ = _html(REF)

    assert "<code>\\ref{...}</code>" in html
    assert 'Figure <a class="ref" href="#fig:x">1</a>' in html
    assert 'href="#..."' not in html


def test_html_inline_label_eqref_math_and_variables_stay_literal():
    html, _ = _html("Use `\\label{eq:a}`, `\\eqref{eq:a}`, `$x$` and `{{fig:example}}`.")

    assert "<code>\\label{eq:a}</code>" in html
    assert "<code>\\eqref{eq:a}</code>" in html
    assert "<code>$x$</code>" in html
    assert "<code>{{fig:example}}</code>" in html
    assert '<a id="eq:a">' not in html
    assert 'class="var' not in html


def test_html_fenced_code_is_verbatim():
    html, cited = _html(FENCE)

    code = re.search(r'<pre><code data-lang="markdown">(.*?)</code></pre>', html, re.S).group(1)
    assert code == (
        "# Methods &lt;!-- \\label{sec:m} --&gt;\n"
        "&lt;!-- a comment --&gt;\n"
        "See \\cite{key}, \\ref{fig:x} and {{N}} at ![a](../figures/x/x.png)."
    )
    assert cited == []


# ── Word ─────────────────────────────────────────────────────────────────────

def _word(md):
    builder = ContentBuilder(default_styles())
    render_markdown(md, builder, labels={"fig:x": ("Figure", 1)})
    xml = builder.to_xml()
    return builder, xml, "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def _code_runs(xml):
    runs = re.findall(r"<w:r>(?:(?!</w:r>).)*</w:r>", xml, re.S)
    return ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", r)) for r in runs if 'w:val="Code"' in r]


def test_word_inline_cite_stays_literal_next_to_a_real_one():
    builder, xml, text = _word(CITE)

    assert "Cite with \\cite{key} and for real: [1]." in text
    assert builder.citation_keys == ["real"]  # no bogus "key" entry in References
    assert _code_runs(xml) == ["\\cite{key}"]


def test_word_inline_ref_stays_literal_next_to_a_real_one():
    _, xml, text = _word(REF)

    assert "Cross-reference with \\ref{...} — see Figure 1." in text
    assert _code_runs(xml) == ["\\ref{...}"]


def test_word_inline_math_and_label_stay_literal():
    _, xml, text = _word("Use `$x$`, `\\label{eq:a}` and `![a](b.png)`.")

    assert _code_runs(xml) == ["$x$", "\\label{eq:a}", "![a](b.png)"]
    assert "<m:oMath" not in xml


def test_word_fenced_code_keeps_its_comments_and_commands():
    builder, _, text = _word(FENCE)

    assert "# Methods &lt;!-- \\label{sec:m} --&gt;" in text
    assert "&lt;!-- a comment --&gt;" in text
    assert "See \\cite{key}, \\ref{fig:x}" in text
    assert builder.citation_keys == []


# ── LaTeX (already right; keep it that way) ──────────────────────────────────

def test_latex_inline_cite_and_ref_are_texttt():
    _, body = md_to_latex(CITE + "\n\n" + REF, escape_text=False)

    assert "\\texttt{\\textbackslash{}cite\\{key\\}}" in body
    assert "\\cite{real}" in body
    assert "\\texttt{\\textbackslash{}ref\\{...\\}}" in body
    assert "\\ref{fig:x}" in body


# ── label numbering ──────────────────────────────────────────────────────────

def test_labels_in_code_are_not_numbered(tmp_path):
    (tmp_path / "a.md").write_text(
        "# Intro <!-- \\label{sec:intro} -->\n\n"
        "Write `\\label{fig:fake}` under the caption.\n\n"
        "```markdown\n\\label{fig:fenced}\n```\n\n"
        "```latex\n\\begin{figure}\n\\caption{Real.}\n\\label{fig:real}\n\\end{figure}\n```\n"
    )
    labels = collect_labels(SimpleNamespace(sections=["a.md"]), tmp_path)

    assert labels == {"sec:intro": ("Section", 1), "fig:real": ("Figure", 1)}


# ── the starter manuscript, end to end ───────────────────────────────────────

@pytest.fixture(scope="module")
def starter(tmp_path_factory) -> Path:
    dest = tmp_path_factory.mktemp("verbatim") / "proj"
    ip.create_project(dest, ip.Answers(
        slug="proj", title="Demo", author="Ada", email="ada@example.org",
        description="Demo", starters="manuscript",
    ), skills=False)
    return dest


def test_starter_html_shows_its_own_syntax(starter):
    assert build_html(starter, "manuscript")
    html = (starter / "out" / "manuscript" / "html" / "index.html").read_text()

    assert "Cite with <code>\\cite{key}</code>" in html
    assert "Cross-reference with <code>\\ref{...}</code>" in html
    assert 'see Figure <a class="ref" href="#fig:example">1</a>' in html
    assert 'title="example_paper_2024">1</a>' in html
    assert 'class="cite cite-missing"' not in html
    assert "with <code>{{fig:example}}</code>" in html
    assert "![Example caption.](../figures/example/example.png)</code></pre>" in html


def test_starter_word_shows_its_own_syntax(starter):
    builder = WordBuilder(root_dir=starter, version="manuscript")
    assert builder.build()
    with ZipFile(builder.out_docx) as z:
        xml = z.read("word/document.xml").decode()
    text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))

    assert "Cite with \\cite{key} — the HTML viewer" in text
    assert "references section: [1]." in text
    assert "Cross-reference with \\ref{...} — see Figure 1 for" in text
    assert "MISSING" not in text
    assert "figures with {{fig:example}}:" in text
