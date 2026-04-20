#!/usr/bin/env python3
"""
Import manually downloaded Canva designs from ZIP files.

Canva exports designs as ZIP files containing numbered pages (1.png, 2.png, etc.).
This script extracts the ZIP and maps pages to figure IDs in your manifest.

Workflow:
    1. Download design from Canva as PNG (produces a ZIP file)
    2. Run this script to extract and map pages to figures
    3. Optionally crop whitespace automatically
    4. Build manuscript with the new figures

Usage:
    # Interactive mode (prompts for each page)
    python scripts/canva_manual_import.py path/to/design.zip

    # Map pages to figure IDs
    python scripts/canva_manual_import.py path/to/design.zip --map 1:figure_1 2:validation_fig_2

    # Use mapping file
    python scripts/canva_manual_import.py path/to/design.zip --mapping-file mapping.json

    # Auto-crop after import
    python scripts/canva_manual_import.py path/to/design.zip --crop

Example mapping file (mapping.json):
    {
      "1": "figure_1",
      "2": "validation_fig_2",
      "3": "methods_diagram"
    }
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Optional, List


def load_manifest(root_dir: Path) -> Dict:
    """Load figure manifest."""
    manifest_path = root_dir / "figures" / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, 'r') as f:
        return json.load(f)


def extract_zip(zip_path: Path, extract_dir: Path) -> List[Path]:
    """
    Extract ZIP file and return list of image files.

    Args:
        zip_path: Path to ZIP file
        extract_dir: Directory to extract to

    Returns:
        Sorted list of extracted image file paths
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Find all PNG files, sorted by name
    image_files = sorted(extract_dir.glob("*.png"), key=lambda p: p.name)

    if not image_files:
        raise ValueError(f"No PNG files found in {zip_path}")

    return image_files


def get_figure_ids(manifest: Dict) -> List[str]:
    """Get list of figure IDs from manifest."""
    return list(manifest.get('figures', {}).keys())


def interactive_mapping(image_files: List[Path], manifest: Dict) -> Dict[str, str]:
    """
    Interactively map pages to figure IDs.

    Args:
        image_files: List of extracted image files
        manifest: Figure manifest

    Returns:
        Dictionary mapping page numbers (as strings) to figure IDs
    """
    figure_ids = get_figure_ids(manifest)
    mapping = {}

    print(f"\n{'='*70}")
    print(f"📋 Interactive Figure Mapping")
    print(f"{'='*70}\n")

    print(f"Found {len(image_files)} pages in ZIP file:")
    for i, img_file in enumerate(image_files, 1):
        print(f"  {i}. {img_file.name}")

    print(f"\nAvailable figure IDs in manifest:")
    for i, fig_id in enumerate(figure_ids, 1):
        source = manifest['figures'][fig_id].get('source', 'null')
        print(f"  {i}. {fig_id} → {source}")

    print(f"\n{'='*70}")
    print(f"Map pages to figure IDs (or press Enter to skip a page)")
    print(f"{'='*70}\n")

    for i, img_file in enumerate(image_files, 1):
        page_num = img_file.stem  # "1", "2", etc.

        while True:
            response = input(f"Page {page_num} ({img_file.name}) → figure ID: ").strip()

            if not response:
                print(f"  ⊘ Skipping page {page_num}")
                break

            if response in figure_ids:
                mapping[page_num] = response
                print(f"  ✓ Mapped page {page_num} → {response}")
                break
            else:
                print(f"  ✗ Invalid figure ID. Choose from: {', '.join(figure_ids)}")

    return mapping


def parse_mapping_args(mapping_args: List[str]) -> Dict[str, str]:
    """
    Parse mapping arguments from command line.

    Args:
        mapping_args: List of "page:figure_id" strings

    Returns:
        Dictionary mapping page numbers to figure IDs
    """
    mapping = {}

    for arg in mapping_args:
        try:
            page, fig_id = arg.split(':', 1)
            mapping[page.strip()] = fig_id.strip()
        except ValueError:
            raise ValueError(f"Invalid mapping format: {arg}. Expected 'page:figure_id'")

    return mapping


def import_figures(
    mapping: Dict[str, str],
    image_files: List[Path],
    manifest: Dict,
    root_dir: Path,
    crop: bool = False,
    crop_script: Optional[Path] = None
) -> Dict[str, int]:
    """
    Import figures according to mapping.

    Args:
        mapping: Dictionary mapping page numbers to figure IDs
        image_files: List of extracted image files
        manifest: Figure manifest
        root_dir: Repository root directory
        crop: Whether to crop whitespace
        crop_script: Path to crop script

    Returns:
        Dictionary with counts: {'imported': N, 'cropped': N, 'errors': N}
    """
    stats = {'imported': 0, 'cropped': 0, 'errors': 0}

    # Create lookup by page number
    images_by_page = {img.stem: img for img in image_files}

    for page_num, fig_id in mapping.items():
        if page_num not in images_by_page:
            print(f"✗ Page {page_num} not found in ZIP")
            stats['errors'] += 1
            continue

        if fig_id not in manifest['figures']:
            print(f"✗ Figure ID '{fig_id}' not found in manifest")
            stats['errors'] += 1
            continue

        source = manifest['figures'][fig_id].get('source')
        if not source:
            print(f"✗ Figure '{fig_id}' has no source path in manifest")
            stats['errors'] += 1
            continue

        # Get source and destination paths
        src_path = images_by_page[page_num]
        dst_path = root_dir / source

        # Create parent directory if needed
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        try:
            shutil.copy2(src_path, dst_path)
            print(f"✓ Imported page {page_num} → {fig_id}")
            print(f"  {dst_path}")
            stats['imported'] += 1

            # Crop if requested
            if crop and crop_script and crop_script.exists():
                try:
                    result = subprocess.run(
                        ['python', str(crop_script), str(dst_path)],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    print(f"  ✓ Cropped whitespace")
                    stats['cropped'] += 1
                except subprocess.CalledProcessError as e:
                    print(f"  ⚠️  Crop failed: {e}")

        except Exception as e:
            print(f"✗ Failed to import page {page_num}: {e}")
            stats['errors'] += 1

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import manually downloaded Canva designs from ZIP files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python scripts/canva_manual_import.py downloads/design.zip

  # With explicit mapping
  python scripts/canva_manual_import.py design.zip --map 1:figure_1 2:figure_2

  # Using mapping file
  python scripts/canva_manual_import.py design.zip --mapping-file mapping.json

  # With auto-crop
  python scripts/canva_manual_import.py design.zip --crop
        """
    )

    parser.add_argument(
        'zip_file',
        type=Path,
        help='Path to Canva design ZIP file'
    )

    # Mapping options
    mapping_group = parser.add_mutually_exclusive_group()
    mapping_group.add_argument(
        '--map',
        nargs='+',
        metavar='PAGE:FIG_ID',
        help='Map pages to figure IDs (e.g., 1:figure_1 2:figure_2)'
    )
    mapping_group.add_argument(
        '--mapping-file',
        type=Path,
        metavar='FILE',
        help='JSON file with page-to-figure mapping'
    )

    # Processing options
    parser.add_argument(
        '--crop',
        action='store_true',
        help='Automatically crop whitespace after import'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be imported without making changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Validate ZIP file
    if not args.zip_file.exists():
        print(f"❌ ZIP file not found: {args.zip_file}")
        return 1

    if not args.zip_file.suffix.lower() == '.zip':
        print(f"❌ File must be a ZIP file: {args.zip_file}")
        return 1

    # Determine root directory
    root_dir = Path(__file__).parent.parent

    # Load manifest
    try:
        manifest = load_manifest(root_dir)
    except Exception as e:
        print(f"❌ Error loading manifest: {e}")
        return 1

    # Extract ZIP to temporary directory
    print(f"\n{'='*70}")
    print(f"📦 Extracting Canva Design ZIP")
    print(f"{'='*70}\n")
    print(f"Source: {args.zip_file}")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_files = extract_zip(args.zip_file, temp_path)

            print(f"✓ Extracted {len(image_files)} pages\n")

            if args.verbose:
                for img in image_files:
                    print(f"  - {img.name}")
                print()

            # Get mapping
            if args.mapping_file:
                # Load from file
                with open(args.mapping_file, 'r') as f:
                    mapping = json.load(f)
                print(f"✓ Loaded mapping from {args.mapping_file}\n")
            elif args.map:
                # Parse from arguments
                mapping = parse_mapping_args(args.map)
            else:
                # Interactive mode
                mapping = interactive_mapping(image_files, manifest)

            if not mapping:
                print("\n⚠️  No pages mapped. Nothing to import.")
                return 0

            # Show mapping
            print(f"\n{'='*70}")
            print(f"📋 Import Plan")
            print(f"{'='*70}\n")

            for page_num, fig_id in mapping.items():
                source = manifest['figures'][fig_id].get('source', 'unknown')
                print(f"  Page {page_num} → {fig_id}")
                print(f"           ({source})")

            if args.crop:
                print(f"\n  🔧 Auto-crop: Enabled")

            if args.dry_run:
                print(f"\n⚠️  DRY RUN - No changes will be made")
                return 0

            print(f"\n{'='*70}")
            print(f"📥 Importing Figures")
            print(f"{'='*70}\n")

            # Find crop script
            crop_script = root_dir / "scripts" / "crop_figure_whitespace.py"
            if args.crop and not crop_script.exists():
                print(f"⚠️  Crop script not found: {crop_script}")
                print(f"   Continuing without cropping...\n")
                crop_script = None

            # Import figures
            stats = import_figures(
                mapping,
                image_files,
                manifest,
                root_dir,
                crop=args.crop,
                crop_script=crop_script
            )

            # Print summary
            print(f"\n{'='*70}")
            print(f"✅ Import Complete")
            print(f"{'='*70}\n")
            print(f"  Imported: {stats['imported']}")
            if args.crop:
                print(f"  Cropped:  {stats['cropped']}")
            if stats['errors'] > 0:
                print(f"  Errors:   {stats['errors']}")

            print(f"\n💡 Next steps:")
            print(f"   1. Review imported figures in their destination folders")
            print(f"   2. Build manuscript: python scripts/build.py")
            print(f"   3. Compile PDF to verify figures appear correctly\n")

            return 0 if stats['errors'] == 0 else 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
