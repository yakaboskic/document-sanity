"""`document-sanity pages init`: publish a project's documents on GitHub Pages.

Writes `.github/workflows/pages.yml`. On every push to the default branch it
installs the project's pinned document-sanity with uv, runs
`document-sanity site` (every document under `src/` → HTML viewer, PDF and
Word, plus an index page), and deploys `site/` with GitHub's own Pages
actions.

PDFs need TeX on the runner. The workflow installs a TeX Live subset from
Ubuntu's own packages (pdflatex, bibtex, latex-recommended + latex-extra,
fonts-recommended, lmodern): no third-party action, about a minute or two per
run. `--no-pdf` leaves TeX out and publishes the HTML viewer and the Word file
only.

A Pages site is public even when the repository is private. `pages init`
refuses a project where a document's manifest sets `metadata.notice` (CUI
banners, distribution statements) unless the owner explicitly overrides with
`allow_notice`; the workflow's `site` call enforces the same rule on every
build, so a notice added later stops the deploy instead of publishing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .project import select_documents
from .site import notice_error, with_notice

WORKFLOW_PATH = ".github/workflows/pages.yml"

# Current majors at the time of writing. astral-sh/setup-uv publishes no
# floating major tag past v7, so it is pinned to a release.
ACTIONS = {
    "checkout": "actions/checkout@v7",
    "configure-pages": "actions/configure-pages@v6",
    "setup-uv": "astral-sh/setup-uv@v10.3.0",
    "upload-pages-artifact": "actions/upload-pages-artifact@v5",
    "deploy-pages": "actions/deploy-pages@v5",
}

# Ubuntu packages for pdflatex + bibtex and what the template's LaTeX uses
# (natbib, placeins, tabularx, lmodern, …).
TEX_PACKAGES = (
    "texlive-latex-recommended",
    "texlive-latex-extra",
    "texlive-fonts-recommended",
    "lmodern",
)

WORKFLOW = """\
# Build every document under src/ and deploy them to GitHub Pages.
# Written by `document-sanity pages init` (v{version}); rerun it with
# --force to regenerate.
#
# A Pages site is PUBLIC, even when this repository is private. Everything
# `document-sanity site` builds is published: each document's HTML viewer
# (numbers and their provenance included), its PDF and its Word file.
{notice_comment}#
# One-time setup: Settings → Pages → Build and deployment → Source: GitHub Actions.
#
{tex_comment}name: Deploy to GitHub Pages

on:
  push:
    branches: [{branch}]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
{guard}    runs-on: ubuntu-latest
    steps:
      - uses: {checkout}
      - uses: {configure_pages}
      - uses: {setup_uv}
        with:
          enable-cache: true
{tex_step}      - name: Install document-sanity
        run: uv sync --locked
      - name: Build site/
        run: uv run --no-sync document-sanity site --out site{site_args}
      - uses: {upload}
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{{{ steps.deployment.outputs.page_url }}}}
    steps:
      - id: deployment
        uses: {deploy}
"""

TEX_STEP = """\
      - name: Install TeX (pdflatex, bibtex)
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \\
            {packages}
"""

TEX_ON = """\
# PDFs need TeX: the build job installs a TeX Live subset from Ubuntu's
# packages (about a minute or two per run). If a template \\usepackage's
# something outside it, the PDF step fails with a missing .sty. Rerun with
# `pages init --no-pdf --force` to publish HTML and Word only.
"""

TEX_OFF = """\
# PDFs are off (`pages init --no-pdf`): the site has each document's HTML
# viewer and Word file, and the runner skips TeX. Rerun `pages init --force`
# without --no-pdf to add them.
"""


class PagesError(Exception):
    """The project can't deploy this way yet; nothing was written."""


def render_workflow(
    *,
    branch: str = "main",
    only_repo: str | None = None,
    docs: list[str] | None = None,
    pdf: bool = True,
    allow_notice: bool = False,
) -> str:
    guard = ""
    if only_repo:
        guard = (
            "    # Deploy from this repository only: forks and template copies skip it.\n"
            f"    if: github.repository == '{only_repo}'\n"
        )
    args = []
    if not pdf:
        args.append("--no-pdf")
    if allow_notice:
        args.append("--allow-notice")
    args += list(docs or [])
    if allow_notice:
        notice_comment = (
            "# --allow-notice: the owner agreed to publish documents that carry a\n"
            "# metadata.notice (restriction or distribution statement).\n"
        )
    else:
        notice_comment = (
            "# `site` refuses any document whose manifest sets metadata.notice (CUI,\n"
            "# distribution statements), so adding one later stops the deploy.\n"
        )
    if docs:
        notice_comment += f"# Published documents: {', '.join(docs)} (others under src/ stay off the site).\n"
    else:
        notice_comment += "# Every document under src/ is published, including ones added later.\n"
    packages = " ".join(TEX_PACKAGES)
    return WORKFLOW.format(
        version=__version__,
        branch=branch,
        guard=guard,
        notice_comment=notice_comment,
        tex_comment=TEX_ON if pdf else TEX_OFF,
        tex_step=TEX_STEP.format(packages=packages) if pdf else "",
        site_args="".join(f" {a}" for a in args),
        checkout=ACTIONS["checkout"],
        configure_pages=ACTIONS["configure-pages"],
        setup_uv=ACTIONS["setup-uv"],
        upload=ACTIONS["upload-pages-artifact"],
        deploy=ACTIONS["deploy-pages"],
    )


def _depends_on_document_sanity(pyproject: str) -> bool:
    return re.search(r"[\"']document-sanity(?:\[[^\]]*\])?\s*(?:@|[<>=!~;]|[\"'])", pyproject) is not None


def _pinned_ref(pyproject: str) -> str | None:
    m = re.search(r"document-sanity(?:\.git)?@([^\"'\s#]+)", pyproject)
    return m.group(1) if m else None


@dataclass
class Report:
    path: Path
    docs: list[str]
    notes: list[str] = field(default_factory=list)


def pages_init(
    root: Path,
    *,
    branch: str = "main",
    only_repo: str | None = None,
    docs: list[str] | None = None,
    pdf: bool = True,
    allow_notice: bool = False,
    force: bool = False,
) -> Report:
    """Write the workflow. The caller has already confirmed the site may be public."""
    path = root / WORKFLOW_PATH
    if path.exists() and not force:
        raise PagesError(f"{WORKFLOW_PATH} already exists — pass --force to regenerate it")
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file() or not _depends_on_document_sanity(pyproject.read_text()):
        raise PagesError(
            "no pyproject.toml that depends on document-sanity — the workflow installs "
            "the tool with uv from this project's own pin (see `document-sanity init`)"
        )
    if only_repo is not None and not re.fullmatch(r"[\w.-]+/[\w.-]+", only_repo):
        raise PagesError(f"--only-repo expects OWNER/NAME, got {only_repo!r}")
    try:
        chosen = select_documents(root, docs)
    except ValueError as e:
        raise PagesError(str(e)) from None
    if not chosen:
        raise PagesError("no documents under src/ (each needs a manifest.yaml)")
    flagged = with_notice(root, chosen)
    if flagged and not allow_notice:
        raise PagesError(str(notice_error(flagged)))

    notes = []
    if not (root / "uv.lock").is_file():
        notes.append("no uv.lock — run `uv lock` and commit it (the workflow installs with --locked)")
    ref = _pinned_ref(pyproject.read_text())
    if ref and not re.fullmatch(r"v\d+(\.\d+)*", ref):
        notes.append(
            f"document-sanity is pinned to `@{ref}`, not a release tag — deploys can "
            "change under you; pin a tag from https://github.com/yakaboskic/document-sanity/releases"
        )
    if pdf and shutil.which("pdflatex") is None:
        notes.append(
            "no pdflatex here, so the PDFs haven't been tried locally — the runner "
            "installs TeX; `--no-pdf` publishes HTML and Word only"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_workflow(
        branch=branch, only_repo=only_repo, docs=docs and chosen, pdf=pdf,
        allow_notice=allow_notice,
    ))
    return Report(path, chosen, notes)


def github_remote(root: Path) -> tuple[str, str] | None:
    """(owner, repo) of the `origin` remote when it points at GitHub."""
    if shutil.which("git") is None:
        return None
    out = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=root, capture_output=True, text=True
    )
    m = re.search(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", out.stdout.strip())
    return (m.group(1), m.group(2)) if m else None
