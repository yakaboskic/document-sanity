# Canva Branding Guide for PIGEAN Manuscripts

This guide provides the exact font specifications from the Springer Nature (sn-nature) LaTeX template for creating figures in Canva that match your manuscript styling.

## Primary Font

**Manuscript Font:** Helvetica (set in `main.tex`)
```latex
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}
```

**Canva Equivalent:** **Arial** (closest match to Helvetica)

---

## Typography Specifications

### Font Sizes by Element

| Element | Size (pt) | Line Height (pt) | Weight | Canva Settings |
|---------|-----------|------------------|--------|----------------|
| **Document Elements** |
| Body Text | 10 | 12 | Regular | Arial 10pt |
| Small Text | 9 | 11 | Regular | Arial 9pt |
| Footnote | 7 | 8 | Regular | Arial 7pt |
| Large Text | 12 | 14 | Regular | Arial 12pt |
| **Headings** |
| Section | 14 | 16 | **Bold** | Arial Bold 14pt |
| Subsection | 12 | 14 | **Bold** | Arial Bold 12pt |
| Sub-subsection | 11 | 13 | **Bold** | Arial Bold 11pt |
| **Figures & Tables** |
| Figure Captions | 8 | 9.5 | Regular | Arial 8pt |
| Figure Labels (Fig. 1) | 8 | 9.5 | **Bold** | Arial Bold 8pt |
| Table Body | 8 | 9.5 | Regular | Arial 8pt |
| Table Footnote | 8 | 9.5 | Regular | Arial 8pt |

---

## Canva Brand Kit Setup

### Recommended Typography Hierarchy

```
1. Main Title: Arial Bold 16-17pt
2. Section Headers: Arial Bold 14pt
3. Subsection Headers: Arial Bold 12pt
4. Body Text: Arial Regular 10pt
5. Captions & Labels: Arial Regular/Bold 8pt
6. Small Notes: Arial Regular 7pt
```

### For Figure Design

Create text styles in Canva for:

| Text Style Name | Font | Size | Weight | Use Case |
|----------------|------|------|--------|----------|
| "Axis Label" | Arial | 8pt | Regular | X/Y axis labels |
| "Axis Tick" | Arial | 7pt | Regular | Axis tick values |
| "Legend Text" | Arial | 8pt | Regular | Legend entries |
| "Panel Label" | Arial | 10-12pt | **Bold** | Panel letters (a, b, c) |
| "Figure Title" | Arial | 12pt | **Bold** | Optional in-figure title |
| "Annotation" | Arial | 7-8pt | Regular | Statistical annotations |

---

## Layout Specifications

### Page Dimensions

Based on manuscript geometry:
```latex
\geometry{a4paper, margin=1in}
```

- **Paper:** A4 (210mm × 297mm)
- **Margins:** 1 inch (25.4mm) all sides
- **Text Width:** ~160mm (6.3 inches)
- **Text Height:** ~9.5 inches

### Figure Dimensions for Canva

**Standard Full-Width Figure:**
- **Width:** 1800px (at 300 DPI ≈ 6 inches = `\textwidth`)
- **Height:** Variable (will be cropped by build script)
- **Resolution:** 300 DPI

**Recommended Heights:**
- Small figure: 1200-1400px
- Medium figure: 1600-2000px
- Large figure: 2200-2600px

**Export Settings:**
- Format: PNG
- Quality: High (300 DPI)
- Then run: `python scripts/crop_figure_whitespace.py figure.png`

---

## Color Palette

### Text Colors

- **Primary Text:** RGB(0, 0, 0) - Black
- **Secondary Text:** RGB(51, 51, 51) - Dark Gray
- **Disabled Text:** RGB(128, 128, 128) - Medium Gray

### Figure Colors (Accessible Palette)

Nature journals recommend high-contrast, colorblind-friendly colors:

| Color Name | RGB | Hex | Use Case |
|-----------|-----|-----|----------|
| Blue | RGB(0, 114, 178) | #0072B2 | Primary data |
| Orange | RGB(230, 159, 0) | #E69F00 | Secondary data |
| Green | RGB(0, 158, 115) | #009E73 | Positive/Success |
| Red | RGB(213, 94, 0) | #D55E00 | Negative/Warning |
| Purple | RGB(204, 121, 167) | #CC79A7 | Tertiary data |
| Yellow | RGB(240, 228, 66) | #F0E442 | Highlight |

These colors are from the [Wong (2011) colorblind-friendly palette](https://www.nature.com/articles/nmeth.1618).

---

## Canva Template Setup

### 1. Create Brand Kit

In Canva, set up your brand kit with:

**Brand Fonts:**
- Font 1: Arial Regular
- Font 2: Arial Bold

**Brand Colors:**
- Add all colors from the accessible palette above

### 2. Save Text Styles

Create and save these text styles:

1. **Figure Caption** - Arial 8pt Regular
2. **Axis Label** - Arial 8pt Regular
3. **Panel Label** - Arial Bold 12pt
4. **Legend** - Arial 8pt Regular
5. **Title** - Arial Bold 14pt

### 3. Create Figure Template

**Template Specifications:**
- Size: 1800px × 2000px (Custom size)
- Resolution: 300 DPI
- Background: White
- Grid: Optional, for alignment

**Layout Guidelines:**
- Margins: 50-100px on all sides
- Panel spacing: 30-50px between sub-panels
- Legend position: Top-right or bottom-right
- Panel labels: Top-left of each panel

---

## Quick Reference Table

### Most Common Figure Elements

| Element | Font | Size | Weight | Example |
|---------|------|------|--------|---------|
| Axis labels | Arial | 8pt | Regular | "Time (hours)" |
| Axis values | Arial | 7pt | Regular | "0, 10, 20" |
| Panel labels | Arial | 12pt | **Bold** | "a", "b", "c" |
| Legend | Arial | 8pt | Regular | "Control", "Treatment" |
| P-values | Arial | 7pt | Regular | "p < 0.001" |
| Error bars | — | — | — | Line width 1-2pt |

---

## Figure Export Workflow

1. **Design in Canva** at 1800px width (fixed)
2. **Use brand fonts** (Arial at specified sizes)
3. **Export** as PNG, 300 DPI
4. **Crop whitespace:**
   ```bash
   python scripts/crop_figure_whitespace.py figure.png
   ```
5. **Add to manifest:**
   ```json
   "my_figure": {
     "source": "figures/manuscript/real/figure.png",
     "caption_height": "2in",
     "crop": true,
     "width": "\\textwidth"
   }
   ```
6. **Use in LaTeX:**
   ```latex
   {{fig:my_figure}}
   ```

---

## Examples

### Example 1: Simple Bar Chart
- **Axes:** Arial 8pt Regular
- **Values:** Arial 7pt Regular
- **Error bars:** 1pt black lines
- **Legend:** Arial 8pt Regular, top-right
- **Panel label:** Arial Bold 12pt, "a" in top-left

### Example 2: Multi-Panel Figure
- **Each panel:** 850px × 850px
- **Spacing:** 100px between panels
- **Panel labels:** Arial Bold 12pt, "a", "b", "c", "d"
- **Shared axis labels:** Arial 8pt Regular
- **Common legend:** Arial 8pt Regular, centered below panels

### Example 3: Complex Diagram
- **Main labels:** Arial Bold 10pt
- **Secondary labels:** Arial Regular 8pt
- **Annotations:** Arial Regular 7pt
- **Arrows:** 2pt width, black
- **Boxes:** 1pt stroke, no fill

---

## Tips for Consistency

✅ **Do:**
- Use exact font sizes from this guide
- Export at 300 DPI
- Use accessible color palette
- Maintain consistent spacing
- Crop whitespace with script

❌ **Don't:**
- Use fonts other than Arial
- Export at lower resolution
- Use similar but not exact colors
- Manually specify figure dimensions in LaTeX
- Use very small text (<7pt)

---

## Additional Resources

- **LaTeX class:** `sn-jnl.cls` (lines 155-205 for font definitions)
- **Main template:** `versions/indirect-support/main_10072025.tex`
- **Crop script:** `scripts/crop_figure_whitespace.py`
- **Examples:** `docs/examples/figures-syntax.tex`

---

**Last Updated:** October 2025
**Based on:** Springer Nature Journal Template (sn-nature style)
