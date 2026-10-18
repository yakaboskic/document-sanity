from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from document_sanity import pages
from document_sanity.cli import main
from document_sanity.site import MARKER, SiteError, build_site

NOTICE = "  notice: |\n    CUI // controlled. Distribution D.\n"


def workflow(root: Path) -> dict:
    return yaml.safe_load((root / pages.WORKFLOW_PATH).read_text())


def add_notice(project: Path) -> None:
    path = project / "src/paper/manifest.yaml"
    path.write_text(path.read_text().replace("metadata:\n", "metadata:\n" + NOTICE, 1))


# ── pages init ───────────────────────────────────────────────────────────────

def test_pages_init_writes_the_workflow(project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(project)
    assert main(["pages", "init", "--yes"]) == 0
    wf = workflow(project)
    assert wf[True]["push"]["branches"] == ["main"]  # YAML 1.1 reads `on:` as True
    assert wf["permissions"] == {"contents": "read", "pages": "write", "id-token": "write"}

    steps = wf["jobs"]["build"]["steps"]
    uses = [s["uses"] for s in steps if "uses" in s]
    assert uses == [
        "actions/checkout@v7", "actions/configure-pages@v6", "astral-sh/setup-uv@v10.3.0",
        "actions/upload-pages-artifact@v5",
    ]
    runs = {s.get("name"): s.get("run", "") for s in steps}
    assert "texlive-latex-extra" in runs["Install TeX (pdflatex, bibtex)"]
    assert runs["Install document-sanity"] == "uv sync --locked"
    assert runs["Build site/"] == "uv run --no-sync document-sanity site --out site"
    assert steps[-1]["with"]["path"] == "site"
    assert "if" not in wf["jobs"]["build"]

    deploy = wf["jobs"]["deploy"]
    assert deploy["needs"] == "build" and deploy["environment"]["name"] == "github-pages"
    assert deploy["steps"][0]["uses"] == "actions/deploy-pages@v5"

    out = capsys.readouterr().out
    assert "build_type=workflow" in out and "every document" in out


def test_pages_init_asks_first(project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(project)
    assert main(["pages", "init"]) == 1  # no terminal, no --yes: refuse
    err = capsys.readouterr().err
    assert "PUBLIC" in err and "--yes" in err
    assert not (project / pages.WORKFLOW_PATH).exists()

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert main(["pages", "init"]) == 1
    assert not (project / pages.WORKFLOW_PATH).exists()
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    assert main(["pages", "init"]) == 0
    assert (project / pages.WORKFLOW_PATH).is_file()


def test_pages_init_options(project: Path) -> None:
    pages.pages_init(project, branch="trunk", only_repo="lab/paper", docs=["paper"], pdf=False)
    wf = workflow(project)
    assert wf[True]["push"]["branches"] == ["trunk"]
    assert wf["jobs"]["build"]["if"] == "github.repository == 'lab/paper'"
    steps = wf["jobs"]["build"]["steps"]
    assert not any("TeX" in s.get("name", "") for s in steps)
    assert any(s.get("run") == "uv run --no-sync document-sanity site --out site --no-pdf paper" for s in steps)
    with pytest.raises(pages.PagesError):
        pages.pages_init(project, only_repo="not a repo", force=True)
    with pytest.raises(pages.PagesError, match="nosuchdoc"):
        pages.pages_init(project, docs=["nosuchdoc"], force=True)


def test_pages_init_never_overwrites_without_force(project: Path) -> None:
    pages.pages_init(project)
    (project / pages.WORKFLOW_PATH).write_text("# mine\n")
    with pytest.raises(pages.PagesError, match="--force"):
        pages.pages_init(project)
    pages.pages_init(project, force=True)
    assert "configure-pages" in (project / pages.WORKFLOW_PATH).read_text()


def test_pages_init_refuses_a_notice(project: Path, capsys, monkeypatch) -> None:
    add_notice(project)
    monkeypatch.chdir(project)
    assert main(["pages", "init", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "metadata.notice" in err and "CUI" in err and "--allow-notice" in err
    assert not (project / pages.WORKFLOW_PATH).exists()
    assert main(["pages", "init", "--yes", "--allow-notice"]) == 0
    run = [s.get("run", "") for s in workflow(project)["jobs"]["build"]["steps"]]
    assert "uv run --no-sync document-sanity site --out site --allow-notice" in run


def test_pages_init_needs_a_document_sanity_project(project: Path, tmp_path: Path, monkeypatch, capsys) -> None:
    (project / "pyproject.toml").write_text('[project]\nname = "document-sanity-template"\n')
    with pytest.raises(pages.PagesError, match="depends on document-sanity"):
        pages.pages_init(project)
    elsewhere = tmp_path / "empty"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert main(["pages", "init", "--yes"]) == 1
    assert "document-sanity init" in capsys.readouterr().err


def test_notes_for_missing_lock_and_unpinned_tool(project: Path) -> None:
    (project / "uv.lock").unlink()
    path = project / "pyproject.toml"
    path.write_text(path.read_text().replace("@v0.2.0", "@main"))
    notes = pages.pages_init(project).notes
    assert any("uv.lock" in n for n in notes)
    assert any("@main" in n and "release tag" in n for n in notes)


# ── site ─────────────────────────────────────────────────────────────────────

def test_site_gathers_documents_with_an_index(project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(project)
    assert main(["site", "--no-pdf"]) == 0
    site = project / "site"
    index = (site / "index.html").read_text()
    assert "A Small Paper" in index and 'href="paper/"' in index and "Ada" in index
    assert 'class="primary"' in index and "paper.pdf" not in index  # --no-pdf: no PDF link
    viewer = (site / "paper/index.html").read_text()
    assert 'href="../"' in viewer and "ds-site-nav" in viewer
    assert (site / MARKER).is_file()
    assert main(["site", "--no-pdf"]) == 0  # rebuilds over its own output


def test_site_from_inside_a_document(project: Path, write, monkeypatch) -> None:
    """Every document, and site/ at the root, wherever it's run from."""
    write({"src/other/manifest.yaml": "metadata:\n  title: Other\nsections:\n  - docs/a.md\n",
           "src/other/docs/a.md": "# A\n\nText.\n"})
    monkeypatch.chdir(project / "src" / "paper" / "docs")
    assert main(["site", "--no-pdf"]) == 0
    assert (project / "site/paper/index.html").is_file()
    assert (project / "site/other/index.html").is_file()
    assert not (project / "src/paper/docs/site").exists()


def test_site_refuses_a_notice_unless_allowed(project: Path) -> None:
    add_notice(project)
    with pytest.raises(SiteError, match="metadata.notice"):
        build_site(project, ["paper"], project / "site", pdf=False)
    assert not (project / "site").exists()
    report = build_site(project, ["paper"], project / "site", pdf=False, allow_notice=True)
    assert report.published == ["paper"]
    assert "CUI // controlled" in (project / "site/index.html").read_text()


def test_site_requires_tex_for_pdfs(project: Path, monkeypatch) -> None:
    from document_sanity import check

    monkeypatch.setattr(check.shutil, "which", lambda name: None)
    report = build_site(project, ["paper"], project / "site")
    assert report.failed and not (project / "site").exists()


def test_site_wont_clobber_a_folder_it_didnt_make(project: Path) -> None:
    (project / "public").mkdir()
    (project / "public/keep.txt").write_text("mine")
    with pytest.raises(SiteError, match="didn't put there"):
        build_site(project, ["paper"], project / "public", pdf=False)
    assert (project / "public/keep.txt").read_text() == "mine"
    with pytest.raises(SiteError, match="project itself"):
        build_site(project, ["paper"], project, pdf=False)


def test_site_with_the_template(tmp_path: Path) -> None:
    """Both starters end up on the site with their Word files."""
    from document_sanity import init_project as ip

    root = tmp_path / "proj"
    ip.create_project(root, ip.Answers(
        slug="proj", title="Demo", author="Ada", email="a@b.c", description="Demo", starters="both",
    ), skills=False)
    report = build_site(root, ["manuscript", "proposal"], root / "site", pdf=False)
    assert report.published == ["manuscript", "proposal"]
    for doc in report.published:
        assert (root / f"site/{doc}/{doc}.docx").is_file()
        assert (root / f"site/{doc}/index.html").is_file()
    assert 'href="manuscript/manuscript.docx"' in (root / "site/index.html").read_text()


def test_template_snapshot_is_deployable() -> None:
    """The project `init` creates passes pages init's checks out of the box."""
    from document_sanity.init_project import bundled_template

    files, _ = bundled_template()
    assert pages._depends_on_document_sanity(files["pyproject.toml"].decode())  # noqa: SLF001
    assert b"notice:" not in files["src/manuscript/manifest.yaml"]
