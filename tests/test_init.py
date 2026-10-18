from __future__ import annotations

import io
import os
import re
import shutil
import socket
import subprocess
import tarfile
from pathlib import Path

import pytest
import yaml

from document_sanity import __version__
from document_sanity import init_project as ip
from document_sanity.cli import main

ANSWERS = [
    "--name", "demo-paper", "--title", "Demo", "--author", "Ada Lovelace",
    "--email", "ada@example.org", "--yes",
]


def answers(**overrides: str) -> ip.Answers:
    base = dict(
        slug="demo-paper", title="Demo", author="Ada Lovelace", email="ada@example.org",
        description="Demo, built with document-sanity", starters="both",
    )
    return ip.Answers(**{**base, **overrides})


def metadata(path: Path) -> dict:
    return yaml.safe_load(path.read_text())["metadata"]


def test_bundled_template_is_a_clean_snapshot() -> None:
    files, label = ip.bundled_template()
    assert label.startswith("document-sanity-template@")
    for rel in ("pyproject.toml", "Makefile", "AGENTS.md", "templates/article.docx",
                "src/manuscript/manifest.yaml", "src/proposal/manifest.yaml"):
        assert rel in files
    assert ip.starters_in(files) == ["manuscript", "proposal"]
    for rel in files:
        parts = rel.split("/")
        assert not {"out", "site", ".venv", "__pycache__"} & set(parts), rel
        assert rel not in ip.TEMPLATE_ONLY


def test_template_marks_what_init_rewrites() -> None:
    files, _ = ip.bundled_template()
    assert b"TEMPLATE:" in files["pyproject.toml"]
    for doc in ("manuscript", "proposal"):
        assert b"TEMPLATE:" in files[f"src/{doc}/manifest.yaml"]


# ── init into a new folder ───────────────────────────────────────────────────

def test_init_into_new_dir_applies_answers(tmp_path: Path, capsys) -> None:
    dest = tmp_path / "x"
    assert main(["init", str(dest), *ANSWERS]) == 0

    pyproject = (dest / "pyproject.toml").read_text()
    assert 'name = "demo-paper"' in pyproject
    assert 'description = "Demo, built with document-sanity"' in pyproject
    if re.fullmatch(r"\d+\.\d+\.\d+", __version__):
        assert f"document-sanity.git@v{__version__}" in pyproject

    for doc in ("manuscript", "proposal"):
        meta = metadata(dest / f"src/{doc}/manifest.yaml")
        assert meta["title"] == "Demo"
        assert meta["authors"] == [{"name": "Ada Lovelace", "email": "ada@example.org", "affiliations": [1]}]
        assert meta["affiliations"]  # the rest of the metadata survives
    manifest = yaml.safe_load((dest / "src/manuscript/manifest.yaml").read_text())
    assert "PVAL" in manifest["variables"] and manifest["sections"]

    readme = (dest / "README.md").read_text()
    assert readme.startswith("# demo-paper") and "VERSION=manuscript" in readme

    for rel in ip.TEMPLATE_ONLY:
        assert not (dest / rel).exists()
    assert not (dest / ".git").exists()
    assert not (dest / "uv.lock").exists()  # the first `uv sync` writes it
    for base in ip.SKILL_DIRS:
        assert (dest / base / "document-sanity" / "SKILL.md").is_file()
        assert (dest / base / "document-sanity" / "modes" / "_shared.md").is_file()

    out = capsys.readouterr().out
    assert "uv sync" in out and "uv.lock" in out and "document-sanity check" in out


def test_init_keeps_only_the_chosen_starter(tmp_path: Path, capsys) -> None:
    dest = tmp_path / "p"
    assert main(["init", str(dest), *ANSWERS, "--starter", "proposal"]) == 0
    assert (dest / "src/proposal/manifest.yaml").is_file()
    assert not (dest / "src/manuscript").exists()
    assert "VERSION=proposal" in (dest / "README.md").read_text()
    assert "src/proposal/" in capsys.readouterr().out


def test_unknown_starter_is_refused(tmp_path: Path, capsys) -> None:
    assert main(["init", str(tmp_path / "q"), *ANSWERS, "--starter", "thesis"]) == 1
    assert "thesis" in capsys.readouterr().err and not (tmp_path / "q").exists()


def test_starters_accept_lists_and_both() -> None:
    assert answers(starters="manuscript, proposal").keep(["manuscript", "proposal"]) == ["manuscript", "proposal"]
    assert answers(starters="BOTH").starters == "both"
    assert answers(starters="manuscript").keep(["manuscript", "proposal"]) == ["manuscript"]


def test_quoting_survives_the_rewrite(tmp_path: Path) -> None:
    dest = tmp_path / "y"
    ip.create_project(dest, answers(title='The "Big" Paper: v1', author="O'Brien"))
    meta = metadata(dest / "src/manuscript/manifest.yaml")
    assert meta["title"] == 'The "Big" Paper: v1'
    assert meta["authors"][0]["name"] == "O'Brien"


def test_init_without_skills(tmp_path: Path) -> None:
    dest = tmp_path / "z"
    assert main(["init", str(dest), *ANSWERS, "--no-skills"]) == 0
    assert not (dest / ".claude").exists() and not (dest / ".agents").exists()


def test_defaults_come_from_the_folder_name(tmp_path: Path) -> None:
    a = ip.gather_answers(tmp_path / "Grant Renewal 2027", {"author": "A", "email": "a@b.c"})
    assert a.slug == "grant-renewal-2027"
    assert a.title == "Grant Renewal 2027"
    assert a.starters == "both"


def test_prompts_fill_only_what_was_not_given(tmp_path: Path) -> None:
    asked: list[str] = []

    def ask(prompt: str, default: str) -> str:
        asked.append(prompt)
        return "My Title" if prompt.startswith("Document title") else default

    a = ip.gather_answers(tmp_path / "p", {"author": "A", "email": "a@b.c"}, ask=ask)
    assert a.title == "My Title"
    assert not any(p.startswith("Author") for p in asked)


def test_bad_answers_are_refused() -> None:
    with pytest.raises(ip.InitError):
        answers(slug="no spaces please")
    with pytest.raises(ip.InitError):
        answers(starters=" , ")


# ── never overwrite ──────────────────────────────────────────────────────────

def test_knit_into_current_dir_keeps_other_files(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "notes.txt").write_text("mine\n")
    (tmp_path / "uv.lock").write_text("my lock\n")  # never a conflict: not copied
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "results.csv").write_text("a,b\n")
    monkeypatch.chdir(tmp_path)
    assert main(["init", ".", *ANSWERS]) == 0
    assert (tmp_path / "notes.txt").read_text() == "mine\n"
    assert (tmp_path / "data/results.csv").read_text() == "a,b\n"
    assert (tmp_path / "uv.lock").read_text() == "my lock\n"
    assert (tmp_path / "src/manuscript/manifest.yaml").is_file()


def test_knit_refuses_conflicts_and_writes_nothing(tmp_path: Path, capsys) -> None:
    (tmp_path / "README.md").write_text("# my repo\n")
    (tmp_path / "Makefile").write_text("all:\n")
    assert main(["init", str(tmp_path), *ANSWERS]) == 1
    err = capsys.readouterr().err
    assert "README.md" in err and "Makefile" in err and "--force" in err
    assert (tmp_path / "README.md").read_text() == "# my repo\n"
    assert not (tmp_path / "pyproject.toml").exists()  # nothing at all was written


def test_force_overwrites_conflicts(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# my repo\n")
    assert main(["init", str(tmp_path), *ANSWERS, "--force"]) == 0
    assert (tmp_path / "README.md").read_text().startswith("# demo-paper")


def test_init_twice_refuses(tmp_path: Path, capsys) -> None:
    dest = tmp_path / "twice"
    assert main(["init", str(dest), *ANSWERS]) == 0
    readme = (dest / "README.md").read_text()
    assert main(["init", str(dest), *ANSWERS]) == 1
    assert "already a document-sanity project" in capsys.readouterr().err
    assert main(["init", str(dest), *ANSWERS, "--title", "Other"]) == 1
    assert (dest / "README.md").read_text() == readme
    assert metadata(dest / "src/manuscript/manifest.yaml")["title"] == "Demo"


def test_dest_that_is_a_file_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.write_text("x")
    with pytest.raises(ip.InitError):
        ip.create_project(target, answers())


# ── --git ────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_makes_a_first_commit(tmp_path: Path, monkeypatch) -> None:
    for var, value in {
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.org",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.org",
    }.items():
        monkeypatch.setenv(var, value)
    dest = tmp_path / "g"
    assert main(["init", str(dest), *ANSWERS, "--git"]) == 0
    log = subprocess.run(["git", "log", "--oneline"], cwd=dest, capture_output=True, text=True)
    assert log.stdout.count("\n") == 1 and "demo-paper" in log.stdout
    tracked = subprocess.run(["git", "ls-files"], cwd=dest, capture_output=True, text=True).stdout
    assert "src/manuscript/manifest.yaml" in tracked
    assert ".claude/skills/document-sanity/SKILL.md" in tracked


# ── uv.lock ──────────────────────────────────────────────────────────────────

@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_gitignore_keeps_uv_lock(tmp_path: Path) -> None:
    """The Pages workflow installs with `uv sync --locked`: the lock must be committed."""
    dest = tmp_path / "x"
    ip.create_project(dest, answers(), skills=False)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "uv.lock"], cwd=dest)
    assert ignored.returncode == 1, "uv.lock is gitignored"


def _online(host: str = "pypi.org") -> bool:
    try:
        socket.create_connection((host, 443), timeout=3).close()
        return True
    except OSError:
        return False


needs_uv = pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("git") is None, reason="needs uv and git"
)
needs_pypi = pytest.mark.skipif(not _online(), reason="offline (uv lock resolves from PyPI)")


def local_github(tmp_path: Path, tag: str) -> dict[str, str]:
    """Env in which document-sanity's GitHub URL is a local bare clone with `tag` at HEAD.

    git's insteadOf points uv at it, so a lock for a tag that isn't pushed yet
    still resolves. PyPI packages come from uv's cache or the index.
    """
    repo = Path(__file__).resolve().parent.parent
    if not (repo / ".git").exists():
        pytest.skip("not a git checkout")
    remote = tmp_path / "remote.git"
    if not remote.exists():
        subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(remote)], check=True)
    subprocess.run(["git", "-C", str(remote), "tag", "-f", tag, "HEAD"], check=True, capture_output=True)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(
        f'[url "file://{remote}"]\n'
        "\tinsteadOf = https://github.com/yakaboskic/document-sanity.git\n"
    )
    return {**os.environ, "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
            "UV_NO_GITHUB_FAST_PATH": "1"}


def uv_lock(project: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["uv", "lock", *args], cwd=project, env=env, capture_output=True, text=True)


def pinned_tag(project: Path) -> str:
    return re.search(r"document-sanity\.git@([^\"]+)", (project / "pyproject.toml").read_text()).group(1)


@needs_uv
@needs_pypi
@pytest.mark.skipif(not re.fullmatch(r"\d+\.\d+\.\d+", __version__), reason="not a release version")
def test_first_lock_resolves_the_pinned_tag(tmp_path: Path) -> None:
    """The lock a new project's first `uv sync` writes pins the release that made it."""
    env = local_github(tmp_path, f"v{__version__}")
    dest = tmp_path / "x"
    ip.create_project(dest, answers(), skills=False)
    assert not (dest / "uv.lock").exists()
    assert pinned_tag(dest) == f"v{__version__}"
    lock = uv_lock(dest, env)
    assert lock.returncode == 0, lock.stderr
    assert f"document-sanity.git?rev=v{__version__}#" in (dest / "uv.lock").read_text()
    locked = uv_lock(dest, env, "--locked")  # what CI's `uv sync --locked` checks first
    assert locked.returncode == 0, locked.stderr


@needs_uv
@needs_pypi
def test_in_place_drops_the_lock_its_rename_would_break(tmp_path: Path) -> None:
    """After `init.py`, the template's own lock fails --locked; a fresh one passes."""
    root = template_copy(tmp_path)
    env = local_github(tmp_path, pinned_tag(root))
    assert uv_lock(root, env).returncode == 0  # the template repo's lock: current
    template_lock = (root / "uv.lock").read_bytes()
    assert uv_lock(root, env, "--locked").returncode == 0

    ip.init_in_place(root, answers(), skills=False)
    assert not (root / "uv.lock").exists()

    (root / "uv.lock").write_bytes(template_lock)  # had it stayed…
    stale = uv_lock(root, env, "--locked")
    assert stale.returncode != 0 and "needs to be updated" in stale.stderr
    (root / "uv.lock").unlink()

    fresh = uv_lock(root, env)  # what the project's first `uv sync` does
    assert fresh.returncode == 0, fresh.stderr
    assert 'name = "demo-paper"' in (root / "uv.lock").read_text()
    assert uv_lock(root, env, "--locked").returncode == 0


# ── --in-place (the template's init.py) ─────────────────────────────────────

def template_copy(tmp_path: Path) -> Path:
    root = tmp_path / "copy"
    for rel, data in ip.bundled_template()[0].items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    (root / "init.py").write_text("# shim\n")
    (root / ".github/workflows").mkdir(parents=True)
    (root / ".github/workflows/pages.yml").write_text("# demo deploy\n")
    return root


def test_in_place_renames_and_removes_template_files(tmp_path: Path) -> None:
    root = template_copy(tmp_path)
    assert main(["init", str(root), "--in-place", *ANSWERS, "--starter", "manuscript"]) == 0
    assert 'name = "demo-paper"' in (root / "pyproject.toml").read_text()
    assert metadata(root / "src/manuscript/manifest.yaml")["title"] == "Demo"
    assert not (root / "src/proposal").exists()
    assert (root / "templates/article.docx").is_file()  # shared files stay
    assert not (root / "init.py").exists()
    assert not (root / ".github").exists()  # no empty folders left behind
    assert (root / ".claude/skills/document-sanity/SKILL.md").is_file()
    assert (root / "README.md").read_text().startswith("# demo-paper")
    assert not (root / "uv.lock").exists()  # renamed project, stale lock: gone
    # a second run finds nothing to initialize
    assert main(["init", str(root), "--in-place", *ANSWERS]) == 1


def test_in_place_refuses_from(tmp_path: Path, capsys) -> None:
    root = template_copy(tmp_path)
    assert main(["init", str(root), "--in-place", "--from", "gh:a/b", *ANSWERS]) == 1
    assert "--in-place" in capsys.readouterr().err
    assert (root / "init.py").exists()


# ── --from gh:owner/repo ─────────────────────────────────────────────────────

def tarball(files: dict[str, bytes], top: str = "lab-paper-template-abc1234") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in {f"{top}/{k}": v for k, v in files.items()}.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo(f"{top}/evil")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        tar.addfile(link)
        escape = tarfile.TarInfo(f"{top}/../escape.txt")
        escape.size = 1
        tar.addfile(escape, io.BytesIO(b"x"))
    return buf.getvalue()


def test_parse_gh_spec() -> None:
    assert ip.parse_gh_spec("gh:lab/paper-template") == ("lab", "paper-template", None)
    assert ip.parse_gh_spec("gh:lab/paper-template.git@v2") == ("lab", "paper-template", "v2")
    with pytest.raises(ip.InitError):
        ip.parse_gh_spec("https://github.com/lab/t")


def test_tarball_strips_top_dir_and_drops_links() -> None:
    files, top = ip.files_from_tarball(tarball({"pyproject.toml": b"x", "src/a/manifest.yaml": b"y"}))
    assert files == {"pyproject.toml": b"x", "src/a/manifest.yaml": b"y"}
    assert top.endswith("abc1234")


def test_init_from_github_fork(tmp_path: Path, monkeypatch) -> None:
    template, _ = ip.bundled_template()
    pinned = re.sub(rb"document-sanity\.git@[^\"]+", b"document-sanity.git@v0.1.9", template["pyproject.toml"])
    fork = {**template, "pyproject.toml": pinned, "init.py": b"# shim\n", "LAB.md": b"lab house rules\n"}
    seen: list[str] = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=0):
        seen.append(request.full_url)
        return Response(tarball(fork))

    monkeypatch.setattr(ip.urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "f"
    assert main(["init", str(dest), "--from", "gh:lab/paper-template@v2", *ANSWERS]) == 0
    assert seen == ["https://api.github.com/repos/lab/paper-template/tarball/v2"]
    assert (dest / "LAB.md").read_text() == "lab house rules\n"
    assert not (dest / "init.py").exists()
    assert "uv.lock" in fork and not (dest / "uv.lock").exists()
    # a fork's pin is the fork's business: left as the fork wrote it
    assert "document-sanity.git@v0.1.9" in (dest / "pyproject.toml").read_text()


# ── skills on an existing project ────────────────────────────────────────────

def test_skills_command_installs_and_refreshes(project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(project / "src" / "paper")  # found by walking up
    assert main(["skills"]) == 0
    skill = project / ".agents/skills/document-sanity/SKILL.md"
    assert skill.is_file()
    skill.write_text("edited\n")
    assert main(["skills"]) == 1  # won't clobber an edit…
    assert main(["skills", "--force"]) == 0  # …unless asked
    assert skill.read_text() != "edited\n"
