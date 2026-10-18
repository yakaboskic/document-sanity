from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from document_sanity import check
from document_sanity import init_project as ip
from document_sanity.cli import main

needs_tex = pytest.mark.skipif(
    shutil.which("pdflatex") is None or shutil.which("bibtex") is None,
    reason="no TeX (pdflatex + bibtex)",
)


def statuses(result: check.DocResult) -> dict[str, str]:
    return {s.name: s.status for s in result.steps}


@pytest.fixture(scope="module")
def template_project(tmp_path_factory) -> Path:
    """A project made by `init` from the bundled template (no skill)."""
    dest = tmp_path_factory.mktemp("tpl") / "proj"
    ip.create_project(dest, ip.Answers(
        slug="proj", title="Demo", author="Ada", email="ada@example.org",
        description="Demo", starters="both",
    ), skills=False)
    return dest


def test_clean_project_passes(project: Path) -> None:
    result = check.build_document(project, "paper", pdf=False)
    s = statuses(result)
    assert s["preview"] == s["refs"] == s["html"] == "ok"
    assert s["pdf"] == "skip"
    assert s["word"] == "warn"  # no templates/*.docx: Word is skipped, not failed
    assert not result.errors
    assert (project / "out/paper/html/index.html").is_file()
    assert (project / "out/paper/latex/main.tex").is_file()


def test_unresolved_references_are_errors(project: Path, write) -> None:
    write({"src/paper/docs/intro.md": (
        "# Intro\n\nA {{MISSING:,}} value \\cite{nobody1999} and \\ref{fig:none}.\n"
        "`\\cite{literal}` in code is fine. <!-- \\cite{commented} -->\n"
    )})
    result = check.build_document(project, "paper", pdf=False)
    refs = result.step("refs")
    assert refs.status == "error"
    joined = "\n".join(refs.notes)
    assert "src/paper/docs/intro.md:3  {{MISSING}}" in joined
    assert "\\cite{nobody1999}" in joined and "\\ref{fig:none}" in joined
    assert "literal" not in joined and "commented" not in joined


def test_missing_section_is_reported(project: Path, write) -> None:
    write({"src/paper/manifest.yaml": (project / "src/paper/manifest.yaml").read_text().replace(
        "  - docs/intro.md\n", "  - docs/intro.md\n  - docs/gone.md\n")})
    refs = check.build_document(project, "paper", pdf=False).step("refs")
    assert refs.status == "error" and any("docs/gone.md" in n for n in refs.notes)


def test_stale_preview_is_an_error(project: Path, write) -> None:
    write({"src/paper/docs/intro.md": (
        "# Intro\n\n```latex\n\\begin{equation}\n  E = mc^2\n\\end{equation}\n```\n"
    )})
    step = check.build_document(project, "paper", pdf=False).step("preview")
    assert step.status == "error" and "preview -V paper" in step.detail
    assert main(["preview", "--root", str(project), "--version", "paper"]) == 0
    assert check.build_document(project, "paper", pdf=False).step("preview").status == "ok"


def test_missing_tex_warns_unless_required(project: Path, monkeypatch) -> None:
    monkeypatch.setattr(check.shutil, "which", lambda name: None)
    assert check.build_document(project, "paper").step("pdf").status == "warn"
    assert check.build_document(project, "paper", require_tex=True).step("pdf").status == "error"


def test_cli_exit_codes_and_selection(project: Path, write, monkeypatch, capsys) -> None:
    write({"src/other/manifest.yaml": "metadata:\n  title: Other\nsections:\n  - docs/a.md\n",
           "src/other/docs/a.md": "# A\n\n{{NOPE}}\n"})
    monkeypatch.chdir(project / "src" / "paper" / "docs")
    assert main(["check", "--no-pdf"]) == 0  # inside src/paper: just that one
    out = capsys.readouterr().out
    assert "paper" in out and "other" not in out
    monkeypatch.chdir(project)
    assert main(["check", "--no-pdf"]) == 1  # everything: `other` fails
    assert "{{NOPE}}" in capsys.readouterr().out
    assert main(["check", "--no-pdf", "nosuchdoc"]) == 1
    assert "nosuchdoc" in capsys.readouterr().err


def test_check_outside_a_project(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["check"]) == 1
    assert "document-sanity init" in capsys.readouterr().err


def test_template_builds_html_and_word(template_project: Path) -> None:
    for doc in ("manuscript", "proposal"):
        result = check.build_document(template_project, doc, pdf=False)
        assert not result.errors, [(s.name, s.detail, s.notes) for s in result.errors]
        word = result.step("word")
        assert word.status == "ok" and word.notes[0].startswith("layout: ")
        assert (template_project / f"out/{doc}/word/main.docx").is_file()
        assert (template_project / f"out/{doc}/html/index.html").is_file()


def test_an_old_layout_script_is_not_run(project: Path, write) -> None:
    """The builder lays the .docx out itself; a project's old
    scripts/finalize_word_layout.py is left alone, with a note to delete it."""
    write({check.LEGACY_LAYOUT_SCRIPT: "raise SystemExit('should not run')\n"})
    (project / "templates").mkdir()
    shutil.copy(ip._PKG / "template/templates/article.docx", project / "templates")
    word = check.build_document(project, "paper", pdf=False).step("word")
    assert word.status == "ok", word.notes
    assert any(check.LEGACY_LAYOUT_SCRIPT in note and "no longer needed" in note for note in word.notes)


@needs_tex
def test_template_builds_pdf(template_project: Path) -> None:
    result = check.build_document(template_project, "manuscript")
    assert result.step("pdf").status == "ok", result.step("pdf").notes
    assert (template_project / "out/manuscript/pdf/main.pdf").is_file()


@needs_tex
def test_latex_errors_fail_the_pdf(project: Path, write) -> None:
    write({"src/paper/docs/intro.md": (project / "src/paper/docs/intro.md").read_text()
           + "\n\\undefinedmacro\n"})
    pdf = check.build_document(project, "paper").step("pdf")
    assert pdf.status == "error" and any("Undefined control sequence" in n for n in pdf.notes)
