# PIGEAN Manuscript Documentation

Welcome to the documentation for the PIGEAN manuscript build system!

## 📚 Documentation Overview

### Getting Started

- **[Quick Reference](QUICK_REFERENCE.md)** - Fast lookup for common commands and syntax
  - Command cheat sheet
  - Template syntax examples
  - Daily workflow guide
  - Troubleshooting tips

### Detailed Guides

- **[Build System](BUILD_SYSTEM.md)** - Complete technical documentation
  - System architecture
  - Component details
  - Template syntax specification
  - Error handling
  - Testing and debugging
  - Extension guide

- **[Canva Integration](CANVA.md)** - Complete Canva workflow guide (START HERE!)
  - Quick start (3 steps)
  - Unified workflow with `{{canva:1}}` syntax
  - Automatic extraction and cropping
  - API mode (after Canva approval)
  - OAuth setup instructions
  - Migration guides
  - Troubleshooting
  - Before/after comparison

- **[Canva Branding](CANVA_BRANDING.md)** - Typography and design specifications
  - Font specifications from LaTeX template
  - Canva brand kit setup
  - Figure layout guidelines
  - Accessible color palette
  - Export workflow

### Examples

- **[examples/variables-syntax.tex](examples/variables-syntax.tex)** - Variable template examples
  - Basic replacement
  - Python-style formatting
  - Scientific notation
  - Thousands separators
  - Placeholder workflow

- **[examples/figures-syntax.tex](examples/figures-syntax.tex)** - Figure template examples
  - Basic figure usage
  - Custom widths
  - Placeholder figures
  - Manifest structure
  - Complete workflow

## 🚀 Quick Start

### 1. Build Your Manuscript

```bash
python scripts/build.py
```

### 2. Use Variables in LaTeX

```latex
The p-value was {{PVALUE:.2e}}.
```

### 3. Use Figures in LaTeX

```latex
{{fig:figure_1}}
```

### 4. Compile PDF

```bash
cd out
pdflatex versions/indirect-support/main_10072025.tex
```

## 📖 Full Documentation

For complete project documentation, see:
- **[../README.md](../README.md)** - Main project README
- **[../CLAUDE.md](../CLAUDE.md)** - Claude Code context and instructions

## 🎯 Common Tasks

### Creating a New Version
```bash
python scripts/make_today_version.py versions/manuscript/main_10072025.tex
```

### Adding a Variable
1. Edit `variables/manuscript.json`
2. Add: `"VARIABLE_NAME": value`
3. Use in LaTeX: `{{VARIABLE_NAME}}`
4. Build: `python scripts/build.py`

### Adding a Figure
1. Edit `figures/manifest.json`
2. Add figure entry with `source` path
3. Use in LaTeX: `{{fig:figure_id}}`
4. Build: `python scripts/build.py`

### Cropping Figures
```bash
python scripts/crop_figure_whitespace.py figure.png
```

### Generating Placeholders
```bash
python scripts/generate_placeholders.py
```

## 🔍 Need Help?

1. **Quick questions?** → [Quick Reference](QUICK_REFERENCE.md)
2. **Technical details?** → [Build System](BUILD_SYSTEM.md)
3. **Figure design?** → [Canva Branding](CANVA_BRANDING.md)
4. **Examples?** → [examples/](examples/)
5. **Still stuck?** → Contact Chase via Slack

## 📋 Documentation Index

### By Topic

**Build System:**
- [Build System Architecture](BUILD_SYSTEM.md#architecture)
- [Component Details](BUILD_SYSTEM.md#components)
- [Error Handling](BUILD_SYSTEM.md#error-handling)
- [Debugging](BUILD_SYSTEM.md#debugging)

**Template Syntax:**
- [Variable Syntax](BUILD_SYSTEM.md#variable-syntax)
- [Figure Syntax](BUILD_SYSTEM.md#figure-syntax)
- [Format Specifications](QUICK_REFERENCE.md#variables)

**Workflows:**
- [Daily Workflow](QUICK_REFERENCE.md#daily-workflow)
- [Versioning](QUICK_REFERENCE.md#versioning)
- [Figure Workflow](QUICK_REFERENCE.md#adding-a-figure)
- [Canva Integration](CANVA.md) - Complete guide

**Design:**
- [Font Specifications](CANVA_BRANDING.md#typography-specifications)
- [Color Palette](CANVA_BRANDING.md#color-palette)
- [Figure Dimensions](CANVA_BRANDING.md#figure-dimensions-for-canva)
- [Canva Workflow](CANVA.md#quick-start) - 3-step process

### By User Type

**First-Time Users:**
1. [Quick Reference](QUICK_REFERENCE.md)
2. [examples/variables-syntax.tex](examples/variables-syntax.tex)
3. [examples/figures-syntax.tex](examples/figures-syntax.tex)

**Regular Users:**
1. [Quick Reference](QUICK_REFERENCE.md)
2. [Canva Branding](CANVA_BRANDING.md)

**Developers:**
1. [Build System](BUILD_SYSTEM.md)
2. [Extending the System](BUILD_SYSTEM.md#extending-the-system)

**Designers:**
1. [Canva Integration](CANVA.md) - Complete workflow
2. [Canva Branding](CANVA_BRANDING.md) - Design specifications

## 🎨 Design Resources

- [Typography Specifications](CANVA_BRANDING.md#typography-specifications)
- [Accessible Color Palette](CANVA_BRANDING.md#color-palette)
- [Canva Brand Kit Setup](CANVA_BRANDING.md#canva-brand-kit-setup)
- [Figure Template](CANVA_BRANDING.md#create-figure-template)

## 🛠️ Developer Resources

- [System Architecture](BUILD_SYSTEM.md#architecture)
- [Component Documentation](BUILD_SYSTEM.md#components)
- [Testing Guide](BUILD_SYSTEM.md#testing)
- [Extension Guide](BUILD_SYSTEM.md#extending-the-system)

---

**Repository:** PIGEAN Manuscript Hub
**Last Updated:** October 2025
**Maintainer:** Chase (contact via Slack)
