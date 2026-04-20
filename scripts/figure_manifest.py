#!/usr/bin/env python3
"""
Figure manifest processor for LaTeX templates.

Manages figure references, processing, and placeholder generation.
Includes support for Canva designs via {{canva:page}} syntax.
"""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class FigureSpec:
    """Specification for a figure."""
    figure_id: str
    source: Optional[str]
    caption_height: str
    crop: bool = True
    width: str = "\\textwidth"

    @property
    def has_source(self) -> bool:
        """Check if figure has a valid source."""
        return self.source is not None and self.source.strip() != ""


@dataclass
class CanvaPageSpec:
    """Specification for a Canva page."""
    page_num: str
    filename: str
    caption_height: str = "2in"
    width: str = "\\textwidth"


class FigureManifest:
    """Manage figure manifest and processing."""

    def __init__(self, manifest_path: Path, root_dir: Path, figure_path_prefix: str = "figures"):
        self.manifest_path = manifest_path
        self.root_dir = root_dir
        self.figure_path_prefix = figure_path_prefix  # Prefix for figure paths in LaTeX output
        self.figures: Dict[str, FigureSpec] = {}
        self.canva_pages: Dict[str, CanvaPageSpec] = {}
        self.canva_config: Dict[str, Any] = {}
        self.placeholders: Dict[str, str] = {}
        self.missing_figures: list = []
        self.canva_extracted: bool = False

        if manifest_path.exists():
            self.load_manifest()

    def load_manifest(self) -> None:
        """Load figure manifest from JSON."""
        with open(self.manifest_path, 'r') as f:
            data = json.load(f)

        # Load Canva configuration
        if 'canva' in data:
            self.canva_config = data['canva']

            # Load Canva pages
            for page_num, spec in data['canva'].get('pages', {}).items():
                self.canva_pages[str(page_num)] = CanvaPageSpec(
                    page_num=str(page_num),
                    filename=spec.get('filename'),
                    caption_height=spec.get('caption_height', '2in'),
                    width=spec.get('width', '\\textwidth')
                )

        # Load figure specs
        for fig_id, spec in data.get('figures', {}).items():
            self.figures[fig_id] = FigureSpec(
                figure_id=fig_id,
                source=spec.get('source'),
                caption_height=spec.get('caption_height', '2in'),
                crop=spec.get('crop', True),
                width=spec.get('width', '\\textwidth')
            )

        # Load placeholder mappings
        self.placeholders = data.get('placeholders', {})

    def get_figure_path(
        self,
        figure_id: str,
        output_dir: Path,
        crop_script: Optional[Path] = None
    ) -> tuple[str, bool]:
        """
        Get the output path for a figure.

        Returns:
            (relative_path, is_placeholder)
        """
        if figure_id not in self.figures:
            # Unknown figure ID - use default placeholder
            self.missing_figures.append({
                'id': figure_id,
                'reason': 'not_in_manifest'
            })
            # Path from project root (where main.tex wrapper lives)
            return f"{self.figure_path_prefix}/placeholder-max-caption-2in.png", True

        spec = self.figures[figure_id]

        # Check if source exists
        if not spec.has_source or not (self.root_dir / spec.source).exists():
            # Use placeholder
            self.missing_figures.append({
                'id': figure_id,
                'reason': 'source_not_found',
                'source': spec.source
            })
            # Path from project root (where main.tex wrapper lives)
            return f"{self.figure_path_prefix}/placeholder-max-caption-{spec.caption_height}.png", True

        # Process figure
        source_path = self.root_dir / spec.source

        # Determine output path - flatten to just the filename
        # In new structure: current/{manuscript}/figures/{filename}
        filename = Path(spec.source).name
        output_path = output_dir / 'figures' / filename

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Process figure (crop if needed)
        if spec.crop and crop_script and crop_script.exists():
            try:
                result = subprocess.run(
                    ['python', str(crop_script), str(source_path), '--output', str(output_path)],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    # Crop failed, just copy
                    shutil.copy2(source_path, output_path)
            except Exception:
                # Fallback to copy
                shutil.copy2(source_path, output_path)
        else:
            # Just copy
            shutil.copy2(source_path, output_path)

        # Path from project root (where main.tex wrapper lives)
        return f"{self.figure_path_prefix}/{filename}", False

    def generate_includegraphics(
        self,
        figure_id: str,
        output_dir: Path,
        crop_script: Optional[Path] = None
    ) -> str:
        """
        Generate \\includegraphics command for a figure.

        Args:
            figure_id: Figure identifier
            output_dir: Output directory for processed figures
            crop_script: Path to crop script

        Returns:
            LaTeX \\includegraphics command
        """
        # Get figure spec
        if figure_id in self.figures:
            spec = self.figures[figure_id]
            width = spec.width
        else:
            width = "\\textwidth"

        # Get figure path
        fig_path, is_placeholder = self.get_figure_path(figure_id, output_dir, crop_script)

        # Generate LaTeX command
        return f"\\includegraphics[width={width}]{{{fig_path}}}"

    def extract_canva_zip(self, output_dir: Path, crop_script: Optional[Path] = None) -> None:
        """
        Extract Canva ZIP file and process pages according to manifest.

        Args:
            output_dir: Output directory for build
            crop_script: Optional path to crop script
        """
        if not self.canva_config or self.canva_extracted:
            return

        source = self.canva_config.get('source')
        if not source:
            return  # Using API mode or no Canva config

        source_path = self.root_dir / source

        if not source_path.exists():
            print(f"⚠️  Canva ZIP not found: {source}")
            print(f"   Place your downloaded Canva design at: {source}")
            return

        auto_extract = self.canva_config.get('auto_extract', True)
        if not auto_extract:
            return

        print(f"\n📦 Extracting Canva design from ZIP")
        print(f"{'='*60}")
        print(f"Source: {source}")

        # Get output directory from config
        canva_output_dir = self.root_dir / self.canva_config.get('output_dir', 'figures/canva')
        canva_output_dir.mkdir(parents=True, exist_ok=True)

        # Extract ZIP
        try:
            with zipfile.ZipFile(source_path, 'r') as zip_ref:
                # Extract all PNG files
                extracted_files = []
                for member in zip_ref.namelist():
                    if member.lower().endswith('.png'):
                        zip_ref.extract(member, canva_output_dir)
                        extracted_files.append(member)

            print(f"✓ Extracted {len(extracted_files)} pages")

            # Process each page according to manifest
            crop = self.canva_config.get('crop', True)
            processed = 0

            for page_num, page_spec in self.canva_pages.items():
                # Find extracted file (e.g., "1.png")
                page_file = canva_output_dir / f"{page_num}.png"

                if not page_file.exists():
                    print(f"⚠️  Page {page_num} not found in ZIP")
                    continue

                # Determine final destination
                dest_file = canva_output_dir / page_spec.filename

                # Crop if requested
                if crop and crop_script and crop_script.exists():
                    try:
                        subprocess.run(
                            ['python', str(crop_script), str(page_file), '--output', str(dest_file)],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        print(f"  ✓ Page {page_num} → {page_spec.filename} (cropped)")
                    except subprocess.CalledProcessError:
                        # Crop failed, just rename
                        shutil.copy2(page_file, dest_file)
                        print(f"  ✓ Page {page_num} → {page_spec.filename}")
                else:
                    # Just rename
                    shutil.copy2(page_file, dest_file)
                    print(f"  ✓ Page {page_num} → {page_spec.filename}")

                # Remove numbered file if different from destination
                if page_file != dest_file and page_file.exists():
                    page_file.unlink()

                processed += 1

            print(f"\n✓ Processed {processed} Canva pages")
            self.canva_extracted = True

        except Exception as e:
            print(f"✗ Error extracting Canva ZIP: {e}")

    def get_canva_page_path(
        self,
        page_num: str,
        output_dir: Path,
        crop_script: Optional[Path] = None
    ) -> tuple[str, bool]:
        """
        Get the output path for a Canva page.

        Args:
            page_num: Page number (as string)
            output_dir: Output directory
            crop_script: Optional crop script path

        Returns:
            (relative_path, is_placeholder)
        """
        if str(page_num) not in self.canva_pages:
            # Unknown page number
            self.missing_figures.append({
                'id': f'canva:{page_num}',
                'reason': 'page_not_in_manifest'
            })
            # Path from project root (where main.tex wrapper lives)
            return f"{self.figure_path_prefix}/placeholder-max-caption-2in.png", True

        page_spec = self.canva_pages[str(page_num)]

        # Get Canva output directory
        canva_output_dir = self.canva_config.get('output_dir', 'figures/canva')
        source_path = self.root_dir / canva_output_dir / page_spec.filename

        # Check if file exists
        if not source_path.exists():
            self.missing_figures.append({
                'id': f'canva:{page_num}',
                'reason': 'canva_file_not_found',
                'filename': page_spec.filename
            })
            placeholder = self.placeholders.get(
                page_spec.caption_height,
                self.placeholders.get('2in', 'figures/placeholder-max-caption-2in.png')
            )
            # Path from project root (where main.tex wrapper lives)
            return f"{self.figure_path_prefix}/placeholder-max-caption-{page_spec.caption_height}.png", True

        # Copy to output directory
        # In new structure: current/{manuscript}/figures/{filename}
        output_path = output_dir / "figures" / page_spec.filename

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(source_path, output_path)

        # Path from project root (where main.tex wrapper lives)
        return f"{self.figure_path_prefix}/{page_spec.filename}", False

    def generate_canva_includegraphics(
        self,
        page_num: str,
        output_dir: Path,
        crop_script: Optional[Path] = None
    ) -> str:
        """
        Generate \\includegraphics command for a Canva page.

        Args:
            page_num: Page number
            output_dir: Output directory for processed figures
            crop_script: Path to crop script

        Returns:
            LaTeX \\includegraphics command
        """
        # Get page spec
        if str(page_num) in self.canva_pages:
            spec = self.canva_pages[str(page_num)]
            width = spec.width
        else:
            width = "\\textwidth"

        # Get page path
        page_path, is_placeholder = self.get_canva_page_path(page_num, output_dir, crop_script)

        # Generate LaTeX command
        return f"\\includegraphics[width={width}]{{{page_path}}}"

    def has_missing_figures(self) -> bool:
        """Check if any figures are missing."""
        return len(self.missing_figures) > 0

    def print_report(self) -> None:
        """Print figure processing report."""
        total = len(self.figures)
        missing = len(self.missing_figures)
        processed = total - missing

        print(f"\n🖼️  Figure Processing Report")
        print(f"{'='*60}")
        print(f"  Total figures in manifest: {total}")
        print(f"  Processed: {processed}")
        print(f"  Using placeholders: {missing}")

        if self.missing_figures:
            print(f"\n⚠️  Figures using placeholders ({missing}):")
            for fig in self.missing_figures:
                fig_id = fig['id']
                reason = fig['reason']
                if reason == 'not_in_manifest':
                    print(f"  • {fig_id} - Not defined in manifest")
                elif reason == 'source_not_found':
                    source = fig.get('source', 'None')
                    print(f"  • {fig_id} - Source not found: {source}")


def create_example_manifest(output_path: Path) -> None:
    """Create an example figure manifest."""
    example = {
        "figures": {
            "figure_1": {
                "source": "figures/indirect-support/real/pigean-figure-1.png",
                "caption_height": "2in",
                "crop": True,
                "width": "\\textwidth"
            },
            "validation_fig_2": {
                "source": "figures/indirect-support/real/validation-figure-2.png",
                "caption_height": "3in",
                "crop": True,
                "width": "0.8\\textwidth"
            },
            "future_figure": {
                "source": None,
                "caption_height": "2in",
                "width": "\\textwidth"
            }
        },
        "placeholders": {
            "2in": "figures/placeholder-max-caption-2in.png",
            "3in": "figures/placeholder-max-caption-3in.png",
            "4in": "figures/placeholder-max-caption-4in.png"
        }
    }

    with open(output_path, 'w') as f:
        json.dump(example, f, indent=2)

    print(f"Created example manifest: {output_path}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'create-example':
        output = Path('figures/manifest.json')
        create_example_manifest(output)
    else:
        print("Usage:")
        print("  python figure_manifest.py create-example")
