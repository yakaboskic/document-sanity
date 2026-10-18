"""Refresh the template snapshot that ships inside the wheel.

    uv run python scripts/sync_template.py [--template PATH] [--ref REF]

Copies the *tracked* files of document-sanity-template at REF (default HEAD)
into src/document_sanity/template/, minus the template-only files (init.py,
the demo's Pages workflow), and records the commit in
src/document_sanity/template-source.json. It reads through `git archive`, so
out/, .venv/ and anything else untracked never come along, and uncommitted
edits don't either — commit them in the template first.

Run it as part of every release (see "Releasing" in the README), so the
snapshot a version ships is the template that version was released with.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from document_sanity import __version__  # noqa: E402
from document_sanity.init_project import TEMPLATE_ONLY, TEMPLATE_REPO  # noqa: E402

SNAPSHOT = REPO / "src" / "document_sanity" / "template"
SOURCE = REPO / "src" / "document_sanity" / "template-source.json"


def git(template: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(template), *args], check=True, capture_output=True
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--template", type=Path, default=REPO.parent / "document-sanity-template",
        help="document-sanity-template checkout (default: a sibling folder)",
    )
    parser.add_argument("--ref", default="HEAD", help="commit, branch or tag (default: HEAD)")
    args = parser.parse_args()

    template = args.template.resolve()
    commit = git(template, "rev-parse", args.ref + "^{commit}").decode().strip()
    if args.ref == "HEAD" and git(template, "status", "--porcelain", "--untracked-files=no"):
        print("  note: the template has uncommitted changes — they are NOT in the snapshot")

    archive = git(template, "archive", "--format=tar", commit)
    if SNAPSHOT.exists():
        shutil.rmtree(SNAPSHOT)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if not member.isfile() or member.name in TEMPLATE_ONLY:
                continue
            target = SNAPSHOT / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
            count += 1

    SOURCE.write_text(json.dumps({"repo": TEMPLATE_REPO, "commit": commit}, indent=2) + "\n")
    print(f"  {count} files from {TEMPLATE_REPO}@{commit[:7]} → {SNAPSHOT.relative_to(REPO)}/")

    pin = re.search(r"document-sanity\.git@([^\"\s]+)", (SNAPSHOT / "pyproject.toml").read_text())
    if pin and pin.group(1) != f"v{__version__}":
        print(
            f"  note: the template pins @{pin.group(1)}, this tool is {__version__}; "
            f"`init` writes v{__version__} into new projects, but move the template's pin too"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
