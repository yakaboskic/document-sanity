#!/usr/bin/env python3
"""
Figure manifest processor for LaTeX templates.

Manages figure references, processing, and placeholder generation.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class FigureSpec:
    """Specification for a figure."""
    figure_id: str
    source: Optional[str]
    caption_height: str = "2in"
    crop: bool = True
    width: str = "\\textwidth"

    @property
    def has_source(self) -> bool:
        return self.source is not None and self.source.strip() != ""


class FigureManifest:
    """Manage figure manifest and processing."""

    def __init__(self, manifest_path: Path, root_dir: Path, figure_path_prefix: str = "figures"):
        self.manifest_path = manifest_path
        self.root_dir = root_dir
        self.figure_path_prefix = figure_path_prefix
        self.figures: dict[str, FigureSpec] = {}
        self.placeholders: dict[str, str] = {}
        self.missing_figures: list[dict] = []

        if manifest_path.exists():
            self._load_manifest()

    def _load_manifest(self) -> None:
        with open(self.manifest_path, 'r') as f:
            data = json.load(f)

        for fig_id, spec in data.get('figures', {}).items():
            self.figures[fig_id] = FigureSpec(
                figure_id=fig_id,
                source=spec.get('source'),
                caption_height=spec.get('caption_height', '2in'),
                crop=spec.get('crop', True),
                width=spec.get('width', '\\textwidth'),
            )

        self.placeholders = data.get('placeholders', {})

    def get_figure_path(
        self,
        figure_id: str,
        output_dir: Path,
        crop_script: Optional[Path] = None,
    ) -> tuple[str, bool]:
        """Get the output path for a figure. Returns (relative_path, is_placeholder)."""
        if figure_id not in self.figures:
            self.missing_figures.append({'id': figure_id, 'reason': 'not_in_manifest'})
            return f"{self.figure_path_prefix}/placeholder-2in.png", True

        spec = self.figures[figure_id]

        if not spec.has_source or not (self.root_dir / spec.source).exists():
            self.missing_figures.append({
                'id': figure_id, 'reason': 'source_not_found', 'source': spec.source
            })
            return f"{self.figure_path_prefix}/placeholder-{spec.caption_height}.png", True

        source_path = self.root_dir / spec.source
        filename = Path(spec.source).name
        output_path = output_dir / 'figures' / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if spec.crop and crop_script and crop_script.exists():
            try:
                result = subprocess.run(
                    ['python', str(crop_script), str(source_path), '--output', str(output_path)],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    shutil.copy2(source_path, output_path)
            except Exception:
                shutil.copy2(source_path, output_path)
        else:
            shutil.copy2(source_path, output_path)

        return f"{self.figure_path_prefix}/{filename}", False

    def generate_includegraphics(
        self,
        figure_id: str,
        output_dir: Path,
        crop_script: Optional[Path] = None,
    ) -> str:
        """Generate \\includegraphics command for a figure."""
        width = "\\textwidth"
        if figure_id in self.figures:
            width = self.figures[figure_id].width

        fig_path, _ = self.get_figure_path(figure_id, output_dir, crop_script)
        return f"\\includegraphics[width={width}]{{{fig_path}}}"

    def print_report(self) -> None:
        total = len(self.figures)
        missing = len(self.missing_figures)
        print(f"\n    Figure Report")
        print(f"    {'='*50}")
        print(f"      Total:        {total}")
        print(f"      Processed:    {total - missing}")
        print(f"      Placeholders: {missing}")

        if self.missing_figures:
            print(f"\n      Missing figures ({missing}):")
            for fig in self.missing_figures:
                print(f"        - {fig['id']}: {fig['reason']}")
