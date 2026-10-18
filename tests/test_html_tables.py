"""{{tab:id}} in the HTML viewer — a csv-backed table expands to a native
table, as it does in LaTeX and Word, instead of an undefined XXXX span."""

from document_sanity.html_builder import build_html


def test_csv_table_token_renders_as_a_table(tmp_path):
    ver = tmp_path / "src" / "v1"
    (ver / "docs").mkdir(parents=True)
    (ver / "tables").mkdir()
    (ver / "tables" / "subgroups.csv").write_text(
        "Subgroup,Effect\nOlder,0.42\nYounger,0.17\n"
    )
    (ver / "docs" / "results.md").write_text(
        "# Results\n\nBy subgroup:\n\n{{tab:subgroups}}\n\nDone.\n"
    )
    (ver / "manifest.yaml").write_text(
        "metadata:\n"
        "  title: Tables\n"
        "sections:\n"
        "  - docs/results.md\n"
        "tables:\n"
        "  subgroups:\n"
        "    source: tables/subgroups.csv\n"
        "    format: csv\n"
    )

    assert build_html(tmp_path, "v1")
    html = (tmp_path / "out" / "v1" / "html" / "index.html").read_text()

    assert '<table class="md-table">' in html
    for cell in ("Subgroup", "Effect", "Older", "0.42", "Younger", "0.17"):
        assert f">{cell}</t" in html
    assert 'data-var="tab"' not in html
    assert "{{tab:subgroups}}" not in html
