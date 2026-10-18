"""HTML inline conversion: soft-wrapped source lines reflow into one paragraph,
and a stray delimiter must not open emphasis that runs on to the next one (the
stray-asterisk runaway <em> regression)."""

from document_sanity.md2html import md_to_html


def _resolver(name, fmt):
    # (display_text, provenance_or_None, is_defined_bool)
    return (name, None, True)


def test_stray_asterisk_does_not_start_a_cross_line_em():
    md = "Threshold at * the five percent level.\nResults were *significant* overall."
    html = md_to_html(md, _resolver)

    # The real emphasis on the second line renders...
    assert "<em>significant</em>" in html
    # ...and the lone '*' on the first line does NOT open an <em> that swallows
    # everything up to the next asterisk.
    assert "<em> the five percent level" not in html


def test_soft_line_breaks_reflow_within_a_paragraph():
    # Standard markdown: a single newline inside a paragraph is a space.
    md = "First line.\nSecond line."
    html = md_to_html(md, _resolver)
    assert "<p>First line. Second line.</p>" in html
    assert "<br/>" not in html


def test_bold_within_a_line_still_works():
    html = md_to_html("This is **bold** text.", _resolver)
    assert "<strong>bold</strong>" in html


def test_stray_bold_marker_does_not_open_a_span():
    # A stray '**' should not consume the following (reflowed) line.
    md = "Loose ** marker here.\nThen **real bold** later."
    html = md_to_html(md, _resolver)
    assert "<strong>real bold</strong>" in html
    assert "<strong> marker here" not in html


# HTML comments vanish without a trace: a comment on its own line(s) must not
# leave a blank line behind (each blank line is a <br/> in the viewer).

def test_leading_comment_block_leaves_no_breaks():
    md = "<!-- Cover sheet — no heading on purpose.\n     Second line. -->\n\n**Topic**: x"
    assert md_to_html(md, _resolver) == "<p><strong>Topic</strong>: x</p>"


def test_comment_between_paragraphs_keeps_the_usual_spacing():
    plain = md_to_html("First.\n\nSecond.", _resolver)
    assert md_to_html("First.\n\n<!-- note -->\n\nSecond.", _resolver) == plain


def test_comment_line_inside_a_paragraph_does_not_split_it():
    html = md_to_html("First line.\n<!-- note -->\nSecond line.", _resolver)
    assert html == "<p>First line. Second line.</p>"


def test_text_between_two_comments_on_a_line_is_kept():
    html = md_to_html("<!-- a --> kept <!-- b -->", _resolver)
    assert "kept" in html
    assert "<!--" not in html
