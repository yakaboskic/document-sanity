# Quick Reference Guide

Fast reference for common tasks in the PIGEAN manuscript build system.

## 🚀 Common Commands

### Build & Compile
```bash
# Build latest version
python scripts/build.py

# Build specific version
python scripts/build.py --manuscript indirect-support --date 10072025

# Build with figure cropping
python scripts/build.py --crop-figures

# Build in strict mode (fail on undefined variables)
python scripts/build.py --strict

# Compile PDF (output is in current/{manuscript}/)
cd current/indirect-support
pdflatex main_current.tex
bibtex main_current
pdflatex main_current.tex
pdflatex main_current.tex
```

### Versioning
```bash
# Create new dated version
python scripts/make_today_version.py versions/indirect-support/main_10072025.tex

# Preview without making changes
python scripts/make_today_version.py versions/indirect-support/main_10072025.tex --dry-run
```

### Figures
```bash
# Generate placeholder figures
python scripts/generate_placeholders.py

# === Canva Unified Workflow (RECOMMENDED) ===

# 1. Configure manifest: figures/manifest.json
#    {
#      "canva": {
#        "source": "figures/indirect-support/canva-exports/design.zip",
#        "pages": {"1": {"filename": "fig1.png"}, ...}
#      }
#    }

# 2. Download from Canva, place ZIP at configured location

# 3. Build (auto-extracts, crops, processes)
python scripts/build.py

# Use in templates: {{canva:1}}, {{canva:2}}, etc.

# === Canva API Mode (after approval) ===

# Set design_id in manifest instead of source
# {"canva": {"design_id": "DAFxxxxxx", ...}}

# Authenticate (one-time)
python scripts/canva_auth.py

# List designs to find IDs
python scripts/canva_export.py --list-designs

# Build (auto-downloads from API)
python scripts/build.py

# === Figure Cropping ===

# Crop single figure manually
python scripts/crop_figure_whitespace.py figure.png

# Crop with custom output
python scripts/crop_figure_whitespace.py figure.png --output cropped.png

# Crop multiple figures
python scripts/crop_figure_whitespace.py fig1.png fig2.png fig3.png
```

### Variables
```bash
# Migrate LuaLaTeX variables to JSON
python scripts/migrate_variables.py variables/manuscript-variables.tex

# Custom output path
python scripts/migrate_variables.py variables/manuscript-variables.tex --output variables/custom.json
```

---

## 📝 Template Syntax

### Variables

```latex
% Simple replacement
The value was {{VARIABLE_NAME}}.

% With formatting
The p-value was {{PVALUE:.2e}}.          % Scientific notation
The R² was {{R2:.2f}}.                    % 2 decimal places
We analyzed {{NUM_TRAITS:,}} traits.     % Thousands separator
Success rate: {{SUCCESS_RATE:.1%}}       % Percentage
```

**Format Specifiers:**
- `:.2f` - 2 decimal places → `0.30`
- `:.3f` - 3 decimal places → `0.300`
- `:.2e` - Scientific notation → `7.51e-13`
- `:,` - Thousands separator → `6,488`
- `:.1%` - Percentage → `58.0%`

### Figures

**Canva figures (recommended):**
```latex
\begin{figure}[t!]
    \centering
    {{canva:1}}
    \caption{Figure from Canva page 1}
    \label{fig:results}
\end{figure}

\begin{figure}[t!]
    \centering
    {{canva:2}}
    \caption{Figure from Canva page 2}
    \label{fig:validation}
\end{figure}
```

**Traditional figures:**
```latex
\begin{figure}[t!]
    \centering
    {{fig:figure_id}}
    \caption{Your caption here}
    \label{fig:label}
\end{figure}
```

---

## 📋 File Formats

### Variable File (`variables/manuscript.json`)
```json
{
  "VARIABLE_NAME": 0.30,
  "PVALUE": 7.5142e-13,
  "NUM_TRAITS": "6,488",
  "PERCENTAGE": 0.58
}
```

### Figure Manifest (`figures/manifest.json`)
```json
{
  "figures": {
    "figure_1": {
      "source": "figures/manuscript/real/figure.png",
      "caption_height": "2in",
      "crop": true,
      "width": "\\textwidth"
    },
    "placeholder_figure": {
      "source": null,
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
```

---

## 📁 Directory Structure

```
pigean-manuscripts-overleaf/
├── sections/                # SOURCE TEMPLATES (edit these)
│   └── manuscript/
│       └── MMDDYYYY/
│           └── *.tex
├── versions/                # SOURCE TEMPLATES (edit these)
│   └── manuscript/
│       └── main_MMDDYYYY.tex
├── figures/                 # RAW FIGURES
│   ├── manifest.json
│   ├── placeholder-*.png
│   └── manuscript/
│       └── real/*.png
├── variables/               # VARIABLE DEFINITIONS
│   └── manuscript.json
├── current/                 # BUILD OUTPUT (auto-generated, shareable)
│   └── manuscript/
│       ├── main_current.tex  # Main file to compile
│       ├── sections/         # Processed section files
│       ├── figures/          # Processed figures
│       └── README.md         # Build manifest
├── scripts/                 # BUILD SCRIPTS
│   ├── build.py
│   ├── make_today_version.py
│   └── ...
└── docs/                    # DOCUMENTATION
    ├── examples/
    ├── QUICK_REFERENCE.md
    └── CANVA_BRANDING.md
```

---

## 🔄 Daily Workflow

### Starting a New Version
1. Create new version:
   ```bash
   python scripts/make_today_version.py versions/manuscript/main_10072025.tex
   ```

2. Edit templates in:
   ```
   sections/manuscript/10282025/
   ```

3. Update variables in:
   ```
   variables/manuscript.json
   ```

4. Build:
   ```bash
   python scripts/build.py
   ```

5. Compile from:
   ```
   current/manuscript/main_current.tex
   ```

### Adding a Figure

1. Add to manifest (`figures/manifest.json`):
   ```json
   "new_figure": {
     "source": null,
     "caption_height": "2in",
     "width": "\\textwidth"
   }
   ```

2. Use in LaTeX:
   ```latex
   {{fig:new_figure}}
   ```

3. Build (shows placeholder):
   ```bash
   python scripts/build.py
   ```

4. Create actual figure in Canva

5. Export and crop:
   ```bash
   python scripts/crop_figure_whitespace.py new_figure.png
   ```

6. Update manifest:
   ```json
   "new_figure": {
     "source": "figures/manuscript/real/new_figure.png",
     "caption_height": "2in",
     "crop": true,
     "width": "\\textwidth"
   }
   ```

7. Rebuild:
   ```bash
   python scripts/build.py
   ```

---

## ⚠️ Troubleshooting

### Undefined Variables
**Symptom:** Build shows `⚠️ WARNING: Undefined variables found`
**Solution:** Add variable to `variables/manuscript.json` or use placeholder intentionally

### Missing Figures
**Symptom:** Build shows `⚠️ Figures using placeholders`
**Solution:**
- Check `source` path in manifest
- Create figure or set `source: null` intentionally

### Build Errors
**Symptom:** Build fails or shows errors
**Solution:**
```bash
# Run with verbose output
python scripts/build.py --verbose

# Check for syntax errors in templates
grep "{{" sections/manuscript/date/*.tex
```

### LaTeX Compilation Errors
**Symptom:** `pdflatex` fails
**Solution:**
1. Check `current/manuscript/main_current.tex` for issues
2. Verify all `\input` paths are correct
3. Check for LaTeX syntax errors in original templates

---

## 📚 Related Documentation

- **Full Documentation:** [README.md](../README.md)
- **Claude Context:** [CLAUDE.md](../CLAUDE.md)
- **Canva Guide:** [CANVA_BRANDING.md](CANVA_BRANDING.md)
- **Variable Examples:** [examples/variables-syntax.tex](examples/variables-syntax.tex)
- **Figure Examples:** [examples/figures-syntax.tex](examples/figures-syntax.tex)

---

## 🎯 Best Practices

### Version Control
- ✅ Commit source templates (`sections/`, `versions/`)
- ✅ Commit variables (`variables/*.json`)
- ✅ Commit figure manifest (`figures/manifest.json`)
- ❌ Don't commit `current/` directory (gitignored)
- ❌ Don't commit compiled PDFs (unless intentional)

### Variables
- ✅ Use descriptive names (`PIGEAN_REGRESSION_R2`)
- ✅ Store in JSON with proper types (numbers, strings)
- ✅ Use formatting for consistency (`:. 2f`, `:.2e`)
- ❌ Don't hardcode values in LaTeX
- ❌ Don't duplicate variable definitions

### Figures
- ✅ Define all figures in manifest
- ✅ Use placeholders during writing
- ✅ Export from Canva at 1800px width
- ✅ Run crop script before building
- ❌ Don't use hardcoded paths in LaTeX
- ❌ Don't commit raw Canva exports without cropping

### Build Process
- ✅ Build frequently to catch errors early
- ✅ Review build warnings
- ✅ Test compile after major changes
- ❌ Don't edit files in `current/` directory
- ❌ Don't skip the build step

---

**Last Updated:** November 2025
