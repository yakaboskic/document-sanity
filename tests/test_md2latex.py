"""LaTeX conversion must leave template tokens ({{VAR}}, {{op:...:fmt}})
untouched — including underscores inside them — so VariableProcessor can
resolve them on the .tex afterward."""

from document_sanity.md2latex import md_to_latex


def test_plain_variable_token_survives_escaping():
    _, body = md_to_latex("We analyzed {{NUM_SAMPLES}} samples.")
    assert "{{NUM_SAMPLES}}" in body


def test_op_token_with_format_spec_survives():
    _, body = md_to_latex("Change of {{op:(falcon_RS_cat - BL_NG_RS) / BL_NG_RS:.2f}} units.")
    assert "{{op:(falcon_RS_cat - BL_NG_RS) / BL_NG_RS:.2f}}" in body
    # Underscores inside the token must NOT be escaped to \_.
    assert "falcon_RS_cat" in body
    assert "falcon\\_RS\\_cat" not in body


def test_prose_underscores_are_escaped_but_tokens_are_not():
    _, body = md_to_latex("cohort_A used {{N_SAMPLES}} rows.")
    # Prose underscore escaped for LaTeX...
    assert "cohort\\_A" in body
    # ...but the token's underscore is preserved.
    assert "{{N_SAMPLES}}" in body


def test_no_escape_mode_preserves_token_underscores():
    # escape_text=False is used for the abstract / section pass-through path.
    _, body = md_to_latex("Value {{NUM_SAMPLES}} and {{op:a_b / c_d:.2f}}", escape_text=False)
    assert "{{NUM_SAMPLES}}" in body
    assert "{{op:a_b / c_d:.2f}}" in body
    assert "a\\_b" not in body
