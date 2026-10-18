"""`document-sanity init`: a new project from the template, no git required.

The template ships inside the wheel as a snapshot of document-sanity-template
(`template/`, refreshed by `scripts/sync_template.py`), so a project made by
vX.Y.Z of the tool is the template that vX.Y.Z was released with, pinned back
to vX.Y.Z. `--from gh:owner/repo[@ref]` takes a GitHub tarball instead — a
lab's own fork, downloaded over HTTPS with no git binary.

Everything happens in memory first: read the source into {path: bytes}, apply
the answers (the project's name, the documents' titles and authors, which
starters to keep), add the agent skill, and only then compare against the
destination. Nothing is written when a file would be overwritten, or when
the destination already holds documents (`src/<doc>/manifest.yaml`), unless
`force`.

The template's own `init.py` is a shim over `init --in-place`, which applies
the same answers to a "Use this template" copy where it stands.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import __version__
from .project import documents

Files =dict[str, bytes]  # posix path relative to the project root → content

TEMPLATE_REPO = "yakaboskic/document-sanity-template"
# Files that belong to the template repo itself, never to a project made from
# it: the bootstrap shim, and the workflow that deploys the template's demo
# (Pages is opt-in per project — `document-sanity pages init`).
TEMPLATE_ONLY = ("init.py", ".github/workflows/pages.yml")
# Not copied into a new project: the template's lock. The snapshot a release
# ships is taken before the template is re-locked against that release's tag,
# so its lock always pins the previous tool, and `uv sync --locked` (the Pages
# workflow) would refuse it. The project's first `uv sync` writes its own.
# `--in-place` leaves a template copy's lock alone: the template repo's own is
# current.
NOT_COPIED = ("uv.lock",)

SKILL_NAME = "document-sanity"
# Claude Code reads .claude/skills/; Codex, Pi, Cursor and other agents read
# .agents/skills/. Two plain copies rather than a symlink, which Windows and
# zip downloads don't keep.
SKILL_DIRS = (".claude/skills", ".agents/skills")

_PKG = Path(__file__).parent
_SKIP_NAMES = {"__pycache__", ".DS_Store"}

# The dependency line that pins this tool, e.g.
#   "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.0"
_PIN_RE = re.compile(
    r"(document-sanity\s*@\s*git\+https://github\.com/"
    r"yakaboskic/document-sanity(?:\.git)?@)[^\"'\s#]+"
)
_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_MANIFEST_RE = re.compile(r"^src/([^/]+)/manifest\.yaml$")
ALL = ("both", "all")


class InitError(Exception):
    """A project could not be created as asked; nothing was written."""


# ── sources ──────────────────────────────────────────────────────────────────

def read_tree(root: Path) -> Files:
    files: Files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and not _SKIP_NAMES.intersection(rel.parts):
            files[rel.as_posix()] = path.read_bytes()
    return files


def bundled_template() -> tuple[Files, str]:
    """The template snapshot shipped with this release, and where it came from."""
    root = _PKG / "template"
    if not (root / "pyproject.toml").is_file() or not (root / "src").is_dir():
        raise InitError(
            f"no template snapshot at {root} — run scripts/sync_template.py "
            "(or reinstall document-sanity)"
        )
    label = "document-sanity-template"
    source = _PKG / "template-source.json"
    if source.is_file():
        commit = json.loads(source.read_text()).get("commit", "")
        if commit:
            label += f"@{commit[:7]}"
    return read_tree(root), label


def skill_dir() -> Path:
    """The agent skill: packaged in the wheel, or `skills/` in a source checkout."""
    for candidate in (
        _PKG / "skills" / SKILL_NAME,
        _PKG.parent.parent / "skills" / SKILL_NAME,  # editable install
    ):
        if (candidate / "SKILL.md").is_file():
            return candidate
    raise InitError("the document-sanity agent skill is missing from this install")


def bundled_skill() -> Files:
    return read_tree(skill_dir())


def parse_gh_spec(spec: str) -> tuple[str, str, str | None]:
    """`gh:owner/repo[@ref]` → (owner, repo, ref or None for the default branch)."""
    m = re.fullmatch(r"gh:([\w.-]+)/([\w.-]+?)(?:\.git)?(?:@(.+))?", spec.strip())
    if m is None:
        raise InitError(f"--from expects gh:owner/repo[@ref], got {spec!r}")
    return m.group(1), m.group(2), m.group(3)


def files_from_tarball(data: bytes) -> tuple[Files, str]:
    """A GitHub tarball's files, without its `owner-repo-sha/` top directory.

    Only regular files come out; links, devices and anything that would land
    outside the project are dropped rather than trusted.
    """
    files: Files = {}
    top = ""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if not top and (member.isdir() or len(parts) > 1):
                top = parts[0]
            rel = "/".join(parts[1:])
            if not member.isfile() or not rel or parts[0] != top:
                continue
            if rel.startswith("/") or ".." in rel.split("/") or "\\" in rel:
                continue
            if _SKIP_NAMES.intersection(rel.split("/")):
                continue
            extracted = tar.extractfile(member)
            if extracted is not None:
                files[rel] = extracted.read()
    if not files:
        raise InitError("the downloaded tarball is empty")
    return files, top


def fetch_github(owner: str, repo: str, ref: str | None) -> tuple[Files, str]:
    """Download a repo snapshot from GitHub. GH_TOKEN/GITHUB_TOKEN reach private forks."""
    url = f"https://api.github.com/repos/{owner}/{repo}/tarball" + (f"/{ref}" if ref else "")
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
    except urllib.error.HTTPError as e:
        hint = " (private repo? set GH_TOKEN)" if e.code == 404 and not token else ""
        raise InitError(f"GitHub returned {e.code} for {owner}/{repo}{'@' + ref if ref else ''}{hint}") from e
    except urllib.error.URLError as e:
        raise InitError(f"could not reach GitHub: {e.reason}") from e
    files, top = files_from_tarball(data)
    sha = top.rsplit("-", 1)[-1]
    return files, f"gh:{owner}/{repo}@{ref or 'default'} ({sha[:7]})"


def starters_in(files: Files) -> list[str]:
    """The documents a template offers: every `src/<doc>/manifest.yaml`."""
    return sorted(m.group(1) for rel in files if (m := _MANIFEST_RE.match(rel)))


# ── answers ──────────────────────────────────────────────────────────────────

@dataclass
class Answers:
    slug: str
    title: str
    author: str
    email: str
    description: str
    starters: str  # "both" (keep every starter), or a comma-separated list

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.slug):
            raise InitError(
                f"project name {self.slug!r} must be letters, digits, '-', '_' or '.', "
                "e.g. my-paper"
            )
        names = [s.strip() for s in self.starters.replace(" ", ",").split(",") if s.strip()]
        if not names:
            raise InitError("--starter needs at least one starter (or `both`)")
        self.starters = "both" if any(n.lower() in ALL for n in names) else ",".join(names)

    def keep(self, available: list[str]) -> list[str]:
        """The starters to keep out of `available`; unknown names are an error."""
        if self.starters == "both":
            return list(available)
        wanted = self.starters.split(",")
        unknown = [n for n in wanted if n not in available]
        if unknown:
            raise InitError(
                f"no starter {', '.join(map(repr, unknown))} in the template "
                f"(it has: {', '.join(available) or 'none'}; or use `both`)"
            )
        return [n for n in available if n in wanted]


# (field, prompt) in the order they are asked.
QUESTIONS = (
    ("slug", "Project name (kebab-case)"),
    ("title", "Document title"),
    ("author", "Author name"),
    ("email", "Author email"),
    ("description", "Short description"),
    ("starters", "Starters to keep (manuscript, proposal, or both)"),
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return slug or "my-paper"


def _git_config(key: str) -> str | None:
    if shutil.which("git") is None:
        return None
    try:
        out = subprocess.run(
            ["git", "config", "--get", key], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _default(name: str, dest: Path, a: dict[str, str]) -> str:
    if name == "slug":
        return slugify(dest.resolve().name)
    if name == "title":
        return a["slug"].replace("-", " ").replace("_", " ").title()
    if name == "author":
        return _git_config("user.name") or "Your Name"
    if name == "email":
        return _git_config("user.email") or "you@example.com"
    if name == "description":
        return f"{a['title']}, built with document-sanity"
    if name == "starters":
        return "both"
    raise KeyError(name)


def gather_answers(
    dest: Path,
    given: dict[str, str | None],
    *,
    ask: Callable[[str, str], str] | None = None,
) -> Answers:
    """Fill every answer: from `given`, else `ask(prompt, default)`, else the default."""
    a: dict[str, str] = {}
    for name, prompt in QUESTIONS:
        value = given.get(name)
        if value is None or not str(value).strip():
            default = _default(name, dest, a)
            value = ask(prompt, default) if ask else default
        a[name] = str(value).strip()
    return Answers(**a)


# ── rewrites ─────────────────────────────────────────────────────────────────

def _q(value: str) -> str:
    """A double-quoted scalar, valid in both YAML and TOML."""
    return json.dumps(value, ensure_ascii=False)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _metadata_span(lines: list[str]) -> tuple[int, int] | None:
    """[start, end) of the lines inside the top-level `metadata:` block."""
    for i, line in enumerate(lines):
        if re.match(r"^metadata:\s*(#.*)?$", line):
            end = i + 1
            while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > 0):
                end += 1
            return i + 1, end
    return None


def _set_metadata_scalar(text: str, key: str, value: str) -> str:
    """Replace `metadata.<key>: …`, keeping indentation and trailing comments."""
    lines = text.splitlines(keepends=True)
    span = _metadata_span(lines)
    if span is None:
        return text
    pattern = re.compile(
        r"^(\s+)" + re.escape(key) + r":[ \t]*(?:\"[^\"\n]*\"|'[^'\n]*'|[^#\n]*?)([ \t]*(?:#.*)?)(\r?\n?)$"
    )
    for i in range(*span):
        m = pattern.match(lines[i])
        if m and _indent(lines[i]) == _child_indent(lines, span):
            lines[i] = f"{m.group(1)}{key}: {_q(value)}{m.group(2)}{m.group(3)}"
            break
    return "".join(lines)


def _child_indent(lines: list[str], span: tuple[int, int]) -> int:
    """Indentation of the direct children of the block in `span`."""
    for i in range(*span):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("#"):
            return _indent(lines[i])
    return 2


def _set_metadata_authors(text: str, name: str, email: str) -> str:
    """Replace the `metadata.authors` list with one author, keeping comments around it."""
    lines = text.splitlines(keepends=True)
    span = _metadata_span(lines)
    if span is None:
        return text
    child = _child_indent(lines, span)
    for i in range(*span):
        if _indent(lines[i]) == child and re.match(r"^\s*authors:\s*(#.*)?$", lines[i]):
            end = i + 1
            while end < span[1] and lines[end].strip() and _indent(lines[end]) > child:
                end += 1
            has_affiliations = any(
                re.match(r"^\s*affiliations:", lines[j]) and _indent(lines[j]) == child
                for j in range(*span)
            )
            pad = " " * (child + 2)
            block = [f"{pad}- name: {_q(name)}\n", f"{pad}  email: {_q(email)}\n"]
            if has_affiliations:
                block.append(f"{pad}  affiliations: [1]\n")
            lines[i + 1:end] = block
            break
    return "".join(lines)


def _rewrite_pyproject(text: str, a: Answers, pin: str | None) -> str:
    text = re.sub(r'^name\s*=\s*"[^"]*"', lambda _: f"name = {_q(a.slug)}", text, count=1, flags=re.M)
    text = re.sub(
        r'^description\s*=\s*"[^"]*"', lambda _: f"description = {_q(a.description)}",
        text, count=1, flags=re.M,
    )
    if pin:
        text = _PIN_RE.sub(lambda m: f"{m.group(1)}v{pin}", text)
    return text


def _rewrite_manifest(text: str, a: Answers) -> str:
    text = _set_metadata_scalar(text, "title", a.title)
    return _set_metadata_authors(text, a.author, a.email)


def commented(rows: list[tuple[str, str]], indent: str = "") -> str:
    """Shell lines with their `# comments` lined up in one column."""
    width = max(len(cmd) for cmd, _ in rows) + 3
    return "\n".join(
        f"{indent}{cmd:<{width}}# {note}" if note else f"{indent}{cmd}" for cmd, note in rows
    )


def render_readme(a: Answers, docs: list[str]) -> str:
    first = docs[0] if docs else "manuscript"
    listing = "\n".join(f"- `src/{d}/`" for d in docs) or "- (none yet)"
    develop = commented([
        ("uv sync", "installs document-sanity (pinned), writes uv.lock"),
        (f"uv run document-sanity preview -V {first}", "refresh preview blocks (after every edit)"),
        (f"make pdf VERSION={first}", f"→ out/{first}/pdf/main.pdf (needs TeX)"),
        (f"make html VERSION={first}", f"→ out/{first}/html/index.html"),
        (f"make word VERSION={first}", f"→ out/{first}/word/main.docx"),
        ("uv run document-sanity check", "build every target, before you share"),
    ])
    return f"""# {a.slug}

{a.description}

Built with [document-sanity](https://github.com/yakaboskic/document-sanity),
part of [Sanitism](https://sanitism.dev). The markdown under `src/` is the
source of truth; a PDF (via LaTeX), an interactive HTML viewer and a Word
document are all generated from it. See
[document-sanity-template](https://github.com/{TEMPLATE_REPO}) for the
manifest schema, tables, figures, Word styles and authoring conventions.

Every folder under `src/` with a `manifest.yaml` is a document:

{listing}

## Develop

```bash
{develop}
```

`make help` lists the rest. Without `VERSION=`, commands pick the latest
document under `src/`. Commit the `uv.lock` the first `uv sync` writes: it
pins every dependency, and the GitHub Pages workflow installs from it with
`--locked`.

An agent skill lives in `.claude/skills/document-sanity/` (Claude Code:
`/document-sanity`) and `.agents/skills/document-sanity/` (other agents).
`uv run document-sanity skills --force` refreshes it after an upgrade.

document-sanity is pinned to a release tag in `pyproject.toml`. To upgrade,
change the tag to a newer [release](https://github.com/yakaboskic/document-sanity/releases)
and run `uv lock && uv sync`.

To publish the documents on GitHub Pages (a public site, even from a private
repository), see `uv run document-sanity pages init --help`.
"""


def apply_answers(files: Files, a: Answers, *, pin: str | None = None) -> Files:
    """The template with this project's name, titles, authors and starters.

    `pin` rewrites the document-sanity dependency to that release, so a
    project starts on the tool that created it.
    """
    available = starters_in(files)
    keep = a.keep(available)
    dropped = [f"src/{d}/" for d in available if d not in keep]
    out: Files = {
        rel: data for rel, data in files.items()
        if rel not in TEMPLATE_ONLY and not rel.startswith(tuple(dropped))
    }

    def edit(rel: str, fn: Callable[[str], str]) -> None:
        if rel in out:
            out[rel] = fn(out[rel].decode("utf-8")).encode("utf-8")

    edit("pyproject.toml", lambda t: _rewrite_pyproject(t, a, pin))
    for doc in keep:
        edit(f"src/{doc}/manifest.yaml", lambda t: _rewrite_manifest(t, a))
    out["README.md"] = render_readme(a, keep).encode("utf-8")
    return out


def with_skill(files: Files, skill: Files | None = None) -> Files:
    """`files` plus the agent skill in every agent's skills folder."""
    skill = bundled_skill() if skill is None else skill
    out = dict(files)
    for base in SKILL_DIRS:
        for rel, data in skill.items():
            out[f"{base}/{SKILL_NAME}/{rel}"] = data
    return out


# ── writing ──────────────────────────────────────────────────────────────────

@dataclass
class Plan:
    dest: Path
    create: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def plan(files: Files, dest: Path) -> Plan:
    """Sort every file into: new, already identical, or would overwrite."""
    p = Plan(dest)
    for rel, data in sorted(files.items()):
        target = dest / rel
        if not target.exists():
            p.create.append(rel)
        elif target.is_file() and target.read_bytes() == data:
            p.unchanged.append(rel)
        else:
            p.conflicts.append(rel)
    return p


def conflict_error(p: Plan, *, limit: int = 20) -> InitError:
    shown = "\n".join(f"    {rel}" for rel in p.conflicts[:limit])
    more = f"\n    … and {len(p.conflicts) - limit} more" if len(p.conflicts) > limit else ""
    return InitError(
        f"{len(p.conflicts)} file(s) already exist in {p.dest} and differ:\n{shown}{more}\n"
        "  nothing was written. Move them aside, or pass --force to overwrite them."
    )


def write(files: Files, dest: Path, rels: list[str]) -> None:
    for rel in rels:
        target = dest / rel
        if target.is_dir():
            raise InitError(f"{target} is a directory; expected a file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[rel])


def git_init(dest: Path, message: str) -> str:
    """`git init` + first commit. Returns a line for the report."""
    if shutil.which("git") is None:
        raise InitError("--git needs git on PATH")
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=dest, capture_output=True, text=True
    )
    if inside.returncode == 0 and inside.stdout.strip() == "true":
        return "already inside a git repository — left it alone (commit when ready)"
    run = lambda *cmd: subprocess.run(["git", *cmd], cwd=dest, capture_output=True, text=True)  # noqa: E731
    result = run("init", "-b", "main")
    if result.returncode != 0:
        result = run("init")  # git < 2.28 has no -b
    if result.returncode != 0:
        raise InitError(f"git init failed: {result.stderr.strip()}")
    run("add", "-A")
    commit = run("commit", "-q", "-m", message)
    if commit.returncode != 0:
        return f"git repository created; the first commit failed: {commit.stderr.strip()}"
    return "git repository created with a first commit"


@dataclass
class Result:
    dest: Path
    source: str
    answers: Answers
    documents: list[str]
    written: list[str]
    overwritten: list[str]
    removed: list[str] = field(default_factory=list)
    git: str | None = None


def create_project(
    dest: Path,
    answers: Answers,
    *,
    source: tuple[Files, str] | None = None,
    skills: bool = True,
    force: bool = False,
    git: bool = False,
) -> Result:
    """Copy the template (or `source`) into `dest` with `answers` applied.

    `dest` may be missing, empty, or an existing folder to knit into: files
    already there are kept, and any the project would replace are listed and
    refused unless `force`.
    """
    bundled = source is None
    files, label = bundled_template() if bundled else source
    files = {rel: data for rel, data in files.items() if rel not in NOT_COPIED}
    release = re.fullmatch(r"\d+\.\d+\.\d+", __version__) is not None
    files = apply_answers(files, answers, pin=__version__ if bundled and release else None)
    if skills:
        files = with_skill(files)

    if dest.exists() and not dest.is_dir():
        raise InitError(f"{dest} exists and is not a directory")
    existing = documents(dest) if dest.is_dir() else []
    if existing and not force:
        raise InitError(
            f"{dest} is already a document-sanity project (src/: {', '.join(existing)}); "
            "nothing was written.\n"
            "  `init` starts new projects. To refresh the agent skill run "
            "`document-sanity skills`; for another document, `document-sanity new-version`. "
            "--force overwrites every file that differs."
        )
    p = plan(files, dest)
    if p.conflicts and not force:
        raise conflict_error(p)
    dest.mkdir(parents=True, exist_ok=True)
    write(files, dest, p.create + p.conflicts)
    result = Result(
        dest, label, answers, starters_in(files), written=p.create, overwritten=p.conflicts
    )
    if git:
        result.git = git_init(dest, f"Start {answers.slug} from {label}")
    return result


def init_in_place(root: Path, answers: Answers, *, skills: bool = True, force: bool = False) -> Result:
    """Apply `answers` to a template copy where it stands ("Use this template").

    The same rewrites as `create_project`; starters you don't keep and the
    template-only files are removed.
    """
    if not (root / "init.py").is_file() or not (root / "pyproject.toml").is_file():
        raise InitError(
            f"{root} doesn't look like a fresh template copy (no init.py next to "
            "pyproject.toml) — it may already be initialized"
        )
    names = ["pyproject.toml", "README.md"]
    current: Files = {n: (root / n).read_bytes() for n in names if (root / n).is_file()}
    src = root / "src"
    if src.is_dir():
        for doc in sorted(d for d in src.iterdir() if (d / "manifest.yaml").is_file()):
            current[f"src/{doc.name}/manifest.yaml"] = (doc / "manifest.yaml").read_bytes()

    available = starters_in(current)
    keep = answers.keep(available)
    files = apply_answers(current, answers)
    if skills:
        files = with_skill(files)
    p = plan(files, root)
    # Rewriting the template's own files is the point; only skill files a user
    # already has (and changed) count as conflicts here.
    conflicts = [rel for rel in p.conflicts if rel.startswith(SKILL_DIRS)]
    if conflicts and not force:
        p.conflicts = conflicts
        raise conflict_error(p)
    write(files, root, p.create + p.conflicts)

    removed = [rel for rel in TEMPLATE_ONLY if (root / rel).is_file()]
    for rel in TEMPLATE_ONLY:
        (root / rel).unlink(missing_ok=True)
        _prune_empty_parents(root / rel, root)
    for doc in available:
        if doc not in keep:
            shutil.rmtree(src / doc)
            removed.append(f"src/{doc}/")
    return Result(
        root, "this template copy", answers, keep,
        written=p.create, overwritten=p.conflicts, removed=removed,
    )


def _prune_empty_parents(path: Path, root: Path) -> None:
    """Remove the folders above a deleted file that it leaves empty, up to `root`."""
    d = path.parent
    while d != root and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def install_skill(root: Path, *, force: bool = False) -> Plan:
    """(Re)install the agent skill into an existing project."""
    files = with_skill({})
    p = plan(files, root)
    if p.conflicts and not force:
        raise conflict_error(p)
    write(files, root, p.create + p.conflicts)
    return p
