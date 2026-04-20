#!/usr/bin/env python3
"""
Crop vertical whitespace from LaTeX figure images.

This script automatically detects and removes excess whitespace from the top
and bottom of images while preserving the width. Designed for figures created
in Canva with standardized dimensions that need height adjustment while
maintaining width=\textwidth compatibility in LaTeX.

Requirements:
    pip install pillow numpy pdf2image
    (pdf2image also requires poppler-utils on your system)
"""
import argparse
import os
import sys
from PIL import Image
import numpy as np

try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


def detect_content_bounds(image_array, padding=0, threshold=250):
    """
    Detect the top and bottom bounds of non-whitespace content in an image.

    Args:
        image_array: NumPy array of the image (grayscale or RGB)
        padding: Additional pixels to preserve around detected content
        threshold: Pixel value threshold for whitespace detection (0-255)
                  Values above this are considered whitespace

    Returns:
        Tuple of (top, bottom) row indices for cropping
    """
    # Convert to grayscale if needed
    if len(image_array.shape) == 3:
        # Average across RGB channels
        gray = np.mean(image_array, axis=2)
    else:
        gray = image_array

    # Find rows that contain non-white pixels
    # A row is non-white if it has at least one pixel below threshold
    non_white_rows = np.any(gray < threshold, axis=1)

    # Find first and last rows with content
    content_rows = np.where(non_white_rows)[0]

    if len(content_rows) == 0:
        # No content found, return full image bounds
        return 0, image_array.shape[0]

    top = max(0, content_rows[0] - padding)
    bottom = min(image_array.shape[0], content_rows[-1] + 1 + padding)

    return top, bottom


def crop_image(input_path, output_path=None, padding=10, threshold=250, dry_run=False):
    """
    Crop whitespace from top and bottom of an image while preserving width.

    Args:
        input_path: Path to input image
        output_path: Path to save cropped image (defaults to overwriting input)
        padding: Pixels of padding to preserve around content
        threshold: Whitespace detection threshold (0-255)
        dry_run: If True, only report what would be done without saving

    Returns:
        Tuple of (original_height, new_height, pixels_cropped)
    """
    # Check if input is a PDF
    is_pdf = input_path.lower().endswith('.pdf')

    if is_pdf:
        if not PDF_SUPPORT:
            raise ImportError(
                "PDF support requires pdf2image. Install with: uv add pdf2image"
            )
        # Convert PDF to image (first page only)
        try:
            images = convert_from_path(input_path, dpi=300)
        except Exception as e:
            raise RuntimeError(
                f"Could not convert PDF to image. PDF support requires poppler-utils.\n"
                f"Install on macOS: brew install poppler\n"
                f"Install on Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                f"Original error: {e}"
            )
        if not images:
            raise ValueError(f"Could not convert PDF to image: {input_path}")
        img = images[0]
    else:
        # Load image
        img = Image.open(input_path)

    img_array = np.array(img)

    original_height = img_array.shape[0]
    original_width = img_array.shape[1]

    # Detect content bounds
    top, bottom = detect_content_bounds(img_array, padding, threshold)

    new_height = bottom - top
    pixels_cropped = original_height - new_height

    if dry_run:
        print(f"[DRY RUN] {input_path}")
        print(f"  Original size: {original_width}x{original_height}")
        print(f"  Content bounds: rows {top} to {bottom}")
        print(f"  New size: {original_width}x{new_height}")
        print(f"  Pixels cropped: {pixels_cropped} ({pixels_cropped/original_height*100:.1f}%)")
        if output_path and output_path != input_path:
            print(f"  Would save to: {output_path}")
        else:
            print(f"  Would overwrite input file")
        return original_height, new_height, pixels_cropped

    # Crop the image
    cropped_img = img.crop((0, top, original_width, bottom))

    # Save
    if output_path is None:
        output_path = input_path

    # For PDFs, save with appropriate settings
    if is_pdf:
        cropped_img.save(output_path, 'PDF', resolution=300, quality=95)
    else:
        cropped_img.save(output_path)

    print(f"Cropped {input_path}")
    print(f"  {original_width}x{original_height} -> {original_width}x{new_height} ({pixels_cropped} pixels removed)")
    if output_path != input_path:
        print(f"  Saved to: {output_path}")

    return original_height, new_height, pixels_cropped


def main():
    parser = argparse.ArgumentParser(
        description="Crop vertical whitespace from LaTeX figure images while preserving width.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Crop a single image with default padding
  %(prog)s figure.png

  # Crop with custom padding
  %(prog)s figure.png --padding 20

  # Save to a different file
  %(prog)s figure.png --output figure_cropped.png

  # Process multiple images
  %(prog)s fig1.png fig2.png fig3.png

  # Dry run to preview changes
  %(prog)s figure.png --dry-run
        """
    )

    parser.add_argument(
        'images',
        nargs='+',
        help='Path(s) to image file(s) to process'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output path (only valid for single input file; defaults to overwriting input)'
    )

    parser.add_argument(
        '-p', '--padding',
        type=int,
        default=10,
        help='Pixels of padding to preserve around content (default: 10)'
    )

    parser.add_argument(
        '-t', '--threshold',
        type=int,
        default=250,
        help='Whitespace detection threshold 0-255 (default: 250)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without modifying files'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.output and len(args.images) > 1:
        print("Error: --output can only be used with a single input file", file=sys.stderr)
        return 1

    if not (0 <= args.threshold <= 255):
        print("Error: threshold must be between 0 and 255", file=sys.stderr)
        return 1

    if args.padding < 0:
        print("Error: padding must be non-negative", file=sys.stderr)
        return 1

    # Process images
    total_cropped = 0
    for img_path in args.images:
        if not os.path.isfile(img_path):
            print(f"Warning: File not found: {img_path}", file=sys.stderr)
            continue

        try:
            output_path = args.output if len(args.images) == 1 else None
            original_h, new_h, cropped = crop_image(
                img_path,
                output_path,
                args.padding,
                args.threshold,
                args.dry_run
            )
            total_cropped += cropped
            print()
        except Exception as e:
            print(f"Error processing {img_path}: {e}", file=sys.stderr)
            continue

    if len(args.images) > 1:
        print(f"Processed {len(args.images)} images, removed {total_cropped} total pixels")

    return 0


if __name__ == "__main__":
    sys.exit(main())
