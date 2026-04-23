#!/usr/bin/env python3
"""
Create a new version from an existing version (v2 structure).

In the v2 structure, a version is a self-contained directory under src/:
  src/<version>/
    manifest.yaml
    docs/
    figures/
    tables/
    references.bib

Creating a new version copies the entire directory.
"""

import shutil
from pathlib import Path
from typing import Optional

from .version import make_version_name, VersionLog


def make_new_version(
    root_dir: Path,
    source_version: str,
    strategy: str = "both",
    n_words: int = 3,
    version_override: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[str]:
    """Create a new version by copying an existing one.

    Args:
        root_dir: Project root directory
        source_version: Name of the source version directory
        strategy: Version naming strategy
        n_words: Number of words for fun name
        version_override: Explicit version name
        dry_run: Preview without writing

    Returns:
        New version name, or None on error.
    """
    src_dir = root_dir / "src" / source_version

    if not src_dir.exists():
        print(f"  Error: Source version not found: {src_dir}")
        return None

    if not (src_dir / "manifest.yaml").exists():
        print(f"  Error: No manifest.yaml in {src_dir}")
        return None

    new_version = version_override or make_version_name(strategy, n_words)
    new_dir = root_dir / "src" / new_version

    if new_dir.exists():
        print(f"  Error: Version already exists: {new_version}")
        return None

    print(f"  Creating new version: {new_version}")
    print(f"  From: {source_version}")

    if dry_run:
        # Count what would be copied
        file_count = sum(1 for _ in src_dir.rglob('*') if _.is_file())
        print(f"\n  [DRY RUN] Would copy {file_count} files")
        print(f"  [DRY RUN] {src_dir} -> {new_dir}")
        print(f"  [DRY RUN] No files modified.")
        return new_version

    # Copy entire directory
    shutil.copytree(src_dir, new_dir)
    print(f"  Copied to: {new_dir}")

    # Count contents
    file_count = sum(1 for _ in new_dir.rglob('*') if _.is_file())
    print(f"  Files: {file_count}")

    # Log the version
    log = VersionLog(root_dir / ".version-log.json")
    log.add_entry(new_version, "default", strategy, source_version=source_version)

    print(f"\n  Version created: {new_version}")
    return new_version
