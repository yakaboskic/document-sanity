#!/usr/bin/env python3
"""
Generate placeholder figures with different caption heights.

Usage:
    python scripts/generate_placeholders.py
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def create_placeholder(width: int, height: int, caption_height_text: str, output_path: Path):
    """
    Create a placeholder figure.

    Args:
        width: Image width in pixels
        height: Image height in pixels
        caption_height_text: Text to display (e.g., "2in", "3in")
        output_path: Output file path
    """
    # Create image with light gray background
    img = Image.new('RGB', (width, height), color='#E8E8E8')
    draw = ImageDraw.Draw(img)

    # Draw border
    border_color = '#CCCCCC'
    border_width = 3
    draw.rectangle(
        [border_width, border_width, width - border_width, height - border_width],
        outline=border_color,
        width=border_width
    )

    # Draw diagonal lines
    draw.line([0, 0, width, height], fill=border_color, width=2)
    draw.line([width, 0, 0, height], fill=border_color, width=2)

    # Add text
    try:
        # Try to use a nice font
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except:
        # Fallback to default font
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Center text
    text1 = "PLACEHOLDER"
    text2 = f"Max Caption Height: {caption_height_text}"

    # Get text bounding boxes
    bbox1 = draw.textbbox((0, 0), text1, font=font_large)
    bbox2 = draw.textbbox((0, 0), text2, font=font_small)

    text1_width = bbox1[2] - bbox1[0]
    text1_height = bbox1[3] - bbox1[1]
    text2_width = bbox2[2] - bbox2[0]
    text2_height = bbox2[3] - bbox2[1]

    # Position text
    x1 = (width - text1_width) // 2
    y1 = (height - text1_height - text2_height - 20) // 2
    x2 = (width - text2_width) // 2
    y2 = y1 + text1_height + 20

    # Draw text with shadow
    shadow_offset = 2
    draw.text((x1 + shadow_offset, y1 + shadow_offset), text1, fill='#999999', font=font_large)
    draw.text((x1, y1), text1, fill='#666666', font=font_large)

    draw.text((x2 + shadow_offset, y2 + shadow_offset), text2, fill='#999999', font=font_small)
    draw.text((x2, y2), text2, fill='#666666', font=font_small)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save
    img.save(output_path, 'PNG', dpi=(300, 300))
    print(f"Created: {output_path}")


def main():
    """Generate placeholder figures for different caption heights."""
    # Standard figure width at 300 DPI (for \textwidth ≈ 6 inches)
    width = 1800

    # Calculate heights based on A4 text height minus caption
    # A4 text height ≈ 9.5 inches at 300 DPI = 2850 pixels
    # Caption heights: 2in, 3in, 4in at 300 DPI = 600, 900, 1200 pixels

    placeholders = [
        ("2in", 2250),  # 9.5in - 2in = 7.5in = 2250px
        ("3in", 1950),  # 9.5in - 3in = 6.5in = 1950px
        ("4in", 1650),  # 9.5in - 4in = 5.5in = 1650px
    ]

    output_dir = Path("figures")

    for caption_text, height in placeholders:
        output_path = output_dir / f"placeholder-max-caption-{caption_text}.png"
        create_placeholder(width, height, caption_text, output_path)

    print(f"\n✅ Generated {len(placeholders)} placeholder figures")
    print(f"📂 Location: {output_dir}")


if __name__ == '__main__':
    main()
