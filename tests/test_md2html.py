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
