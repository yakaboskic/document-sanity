#!/usr/bin/env python3
"""
Version naming for latex-builder.

Supports three version naming strategies:
  - "date"     : MMDDYYYY (e.g., 04202026)
  - "fun"      : random fun name via coolname (e.g., elegant-crimson-fox)
  - "both"     : MMDDYYYY-elegant-crimson-fox

The version name is used for:
  - Directory names under versions/ and sections/
  - File suffixes on main_*.tex and section files
  - Build output naming
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from coolname import generate_slug


def get_date_string() -> str:
    """Get today's date in MMDDYYYY format."""
    return datetime.today().strftime("%m%d%Y")


def generate_fun_name(n_words: int = 3) -> str:
    """Generate a random fun name slug.

    Examples: 'elegant-crimson-fox', 'swift-azure-falcon'
    """
    return generate_slug(n_words)


def make_version_name(
    strategy: str = "both",
    n_words: int = 3,
    date: Optional[str] = None,
) -> str:
    """Generate a version name based on the chosen strategy.

    Args:
        strategy: One of "date", "fun", or "both"
        n_words: Number of words for fun name (2, 3, or 4)
        date: Optional date override (MMDDYYYY). Defaults to today.

    Returns:
        Version name string.
    """
    date_str = date or get_date_string()
    fun_name = generate_fun_name(n_words)

    if strategy == "date":
        return date_str
    elif strategy == "fun":
        return fun_name
    elif strategy == "both":
        return f"{date_str}-{fun_name}"
    else:
        raise ValueError(f"Unknown version strategy: {strategy}. Use 'date', 'fun', or 'both'.")


def parse_version_date(version_name: str) -> Optional[datetime]:
    """Extract date from a version name, if present.

    Handles:
      - "04202026"  (pure date)
      - "04202026-elegant-fox" (date + fun)
      - "elegant-fox" (pure fun, returns None)
    """
    # Try extracting MMDDYYYY from the start
    import re
    match = re.match(r'^(\d{8})', version_name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%m%d%Y")
        except ValueError:
            pass
    return None


def find_latest_version(
    versions_dir: Path,
    manuscript: Optional[str] = None,
) -> tuple[str, str]:
    """Find the latest manuscript version by date.

    Args:
        versions_dir: Path to the versions/ directory
        manuscript: Manuscript name. If None, auto-detect (must be exactly one).

    Returns:
        (manuscript_name, version_name)
    """
    if not versions_dir.exists():
        raise ValueError(f"Versions directory not found: {versions_dir}")

    if manuscript is None:
        manuscripts = [d.name for d in versions_dir.iterdir() if d.is_dir()]
        if not manuscripts:
            raise ValueError(f"No manuscripts found in {versions_dir}")
        if len(manuscripts) > 1:
            raise ValueError(
                f"Multiple manuscripts found: {manuscripts}. Specify --manuscript."
            )
        manuscript = manuscripts[0]

    manuscript_dir = versions_dir / manuscript
    if not manuscript_dir.exists():
        raise ValueError(f"Manuscript not found: {manuscript}")

    # Find all main_*.tex files
    import re
    main_files = list(manuscript_dir.glob("main_*.tex"))
    if not main_files:
        raise ValueError(f"No main_*.tex files found in {manuscript_dir}")

    # Extract version names and find latest by date
    versions = []
    for f in main_files:
        match = re.match(r'main_(.+)\.tex$', f.name)
        if match:
            ver = match.group(1)
            dt = parse_version_date(ver)
            versions.append((ver, dt, f))

    if not versions:
        raise ValueError("No valid main_*.tex files found")

    # Sort: dated versions first (by date), then undated by name
    dated = [(v, d, f) for v, d, f in versions if d is not None]
    undated = [(v, d, f) for v, d, f in versions if d is None]

    if dated:
        dated.sort(key=lambda x: x[1], reverse=True)
        return manuscript, dated[0][0]
    elif undated:
        undated.sort(key=lambda x: x[0], reverse=True)
        return manuscript, undated[0][0]
    else:
        raise ValueError("No versions found")


class VersionLog:
    """Track version history in a JSON log file."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.entries: list[dict] = []
        if log_path.exists():
            with open(log_path) as f:
                self.entries = json.load(f)

    def add_entry(
        self,
        version_name: str,
        manuscript: str,
        strategy: str,
        source_version: Optional[str] = None,
    ) -> None:
        """Record a new version."""
        self.entries.append({
            'version': version_name,
            'manuscript': manuscript,
            'strategy': strategy,
            'source_version': source_version,
            'created_at': datetime.now().isoformat(),
        })
        self._save()

    def _save(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, 'w') as f:
            json.dump(self.entries, f, indent=2)
