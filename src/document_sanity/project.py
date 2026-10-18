"""Where a project is, and which documents it holds.

A project is a folder whose `src/` holds one folder per document, each with a
`manifest.yaml` (`src/manuscript/`, `src/proposal/`, `src/03302026/`). The
document id is that folder's name — what every command takes as `--version`.
"""

from __future__ import annotations

from pathlib import Path


def documents(root: Path) -> list[str]:
    """The document ids under `root/src/`, sorted."""
    src = root / "src"
    if not src.is_dir():
        return []
    return sorted(d.name for d in src.iterdir() if (d / "manifest.yaml").is_file())


def find_project_root(start: Path) -> Path | None:
    """The nearest folder at or above `start` with `src/<doc>/manifest.yaml`."""
    start = start.resolve()
    for candidate in (start, *start.parents):
        if documents(candidate):
            return candidate
    return None


def document_at(root: Path, path: Path) -> str | None:
    """The document `path` sits inside (`root/src/<doc>/…`), if any."""
    try:
        rel = path.resolve().relative_to((root / "src").resolve())
    except ValueError:
        return None
    if rel.parts and (root / "src" / rel.parts[0] / "manifest.yaml").is_file():
        return rel.parts[0]
    return None


def select_documents(root: Path, wanted: list[str] | None, cwd: Path | None = None) -> list[str]:
    """Resolve requested document ids: `wanted`, else the one `cwd` is in, else all.

    Raises ValueError naming the ids that don't exist.
    """
    available = documents(root)
    if not wanted:
        here = document_at(root, cwd) if cwd is not None else None
        return [here] if here else available
    chosen: list[str] = []
    for name in wanted:
        name = name.strip().strip("/")
        if name.startswith("src/"):
            name = name[len("src/"):]
        if name not in available:
            raise ValueError(
                f"no document {name!r} under src/ (have: {', '.join(available) or 'none'})"
            )
        if name not in chosen:
            chosen.append(name)
    return chosen
