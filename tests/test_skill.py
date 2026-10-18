"""The agent skill ships with the tool and stays in step with it."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from document_sanity.init_project import bundled_skill, skill_dir

REPO = Path(__file__).resolve().parent.parent


def frontmatter(text: str) -> dict:
    return yaml.safe_load(re.match(r"---\n(.*?)\n---", text, re.S).group(1))


def test_router_frontmatter() -> None:
    meta = frontmatter((skill_dir() / "SKILL.md").read_text())
    assert meta["name"] == "document-sanity"
    assert meta["user-invocable"] is True
    assert meta["metadata"]["family"] == "sanitism"


def test_every_routed_mode_exists() -> None:
    router = (skill_dir() / "SKILL.md").read_text()
    routed = set(re.findall(r"`modes/([\w-]+)\.md`", router))
    files = {p.stem for p in (skill_dir() / "modes").glob("*.md")}
    assert routed == files, (routed ^ files)
    hint = frontmatter(router)["argument-hint"]
    assert set(hint.strip("[]").replace(" ", "").split("|")) == files - {"_shared"}


def _commands() -> set[str]:
    from document_sanity.cli import build_parser

    return set(build_parser()._subparsers._group_actions[0].choices)  # noqa: SLF001


def test_modes_only_mention_real_commands() -> None:
    skill = bundled_skill()
    text = "\n".join(skill[k].decode() for k in skill if k.endswith(".md"))
    used = set(re.findall(r"(?:uv run|uvx --from \S+) document-sanity ([a-z][a-z-]*)", text))
    used |= set(re.findall(r"\n\s*document-sanity ([a-z][a-z-]*)(?=\s)", text))
    assert used and used <= _commands(), used - _commands()


def test_modes_only_mention_real_make_targets() -> None:
    from document_sanity.init_project import bundled_template

    makefile = bundled_template()[0]["Makefile"].decode()
    targets = set(re.findall(r"^([a-z][\w-]*):", makefile, re.M))
    skill = bundled_skill()
    text = "\n".join(skill[k].decode() for k in skill if k.endswith(".md"))
    # in code: a `make x` span, or a line of a code block that starts with `make x`
    used = {a or b for a, b in re.findall(r"`make ([a-z][\w-]*)|\n\s*make ([a-z][\w-]*)", text)}
    assert used and used <= targets, used - targets


def test_ground_rule_end_with_preview() -> None:
    shared = (skill_dir() / "modes" / "_shared.md").read_text()
    assert "End every iteration with `preview`" in shared


def test_plugin_manifest_matches_the_tool() -> None:
    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["name"] == "document-sanity"
    assert (REPO / "skills" / plugin["name"] / "SKILL.md").is_file()


def test_versions_match_the_tool() -> None:
    """Release step: the skill and plugin manifest are bumped with the tool."""
    from document_sanity import __version__

    meta = frontmatter((skill_dir() / "SKILL.md").read_text())
    assert meta["metadata"]["version"] == __version__, "bump skills/…/SKILL.md"
    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == __version__, "bump .claude-plugin/plugin.json"
    pyproject = (REPO / "pyproject.toml").read_text()
    assert f'version = "{__version__}"' in pyproject, "bump pyproject.toml"
