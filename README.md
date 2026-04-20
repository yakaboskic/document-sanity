# PIGEAN Manuscript Hub

Welcome to the PIGEAN Manuscript Hub! This repository is designed to support collaborative manuscript writing, figure and table management, and reproducible results for the PIGEAN project and related manuscripts.

## 📚 Documentation

Comprehensive documentation is available in the [`docs/`](docs/) folder:

- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Commands, syntax, and common tasks
- **[Build System](docs/BUILD_SYSTEM.md)** - Complete technical documentation
- **[Canva Setup Guide](docs/CANVA_SETUP_GUIDE.md)** - First-time Canva API setup
- **[Canva Integration](docs/CANVA_INTEGRATION.md)** - API usage and automation
- **[Canva Branding](docs/CANVA_BRANDING.md)** - Typography and design specifications
- **[Examples](docs/examples/)** - Template syntax examples

For a detailed index, see: **[docs/README.md](docs/README.md)**

---

## Project Structure

The repository is organized to keep all manuscript components modular, reproducible, and easy to navigate. Below is a description of the main directories and their intended usage:

### `figures/`
- **Structure:** `figures/{manuscript-name}/`
- **Contents:** All figures for each manuscript are stored in their respective subdirectories. For example, figures for the "indirect-support" manuscript are in `figures/indirect-support/real/`.
- **Usage:** Place all image files (e.g., `.png`, `.pdf`) for a manuscript in its subdirectory.

### `sections/`
- **Structure:** `sections/{manuscript-name}/{MMDDYYYY}`
- **Contents:** Section `.tex` files for each manuscript. Naming convention: `{section_name}_{MMDDYYYY}.tex` (e.g., `methods_09262025.tex`).
- **Usage:** Use this directory to break up large manuscripts into manageable sections, which can be imported into the main manuscript file as needed.

### `tables/`
- **Structure:** `tables/{manuscript-name}/{MMDDYYYY}`
- **Contents:** All table `.tex` files for each manuscript.
- **Usage:** Store all LaTeX-formatted tables for each manuscript in the appropriate subdirectory.

### `versions/`
- **Structure:** `versions/{manuscript-name}/`
- **Contents:** Versioned main manuscript files. Naming convention: `main_{MMDDYYYY}.tex` (e.g., `main_09262025.tex`).
- **Usage:** Each version imports the relevant section files to create a complete manuscript for a specific date or submission.

### `variables/`
- **Contents:** Variable definition files in JSON format (e.g., `indirect-support.json`).
- **Usage:** See below for details on variable management.

### `out/`
- **Contents:** Generated build output (gitignored).
- **Usage:** This directory is automatically created by the build script and contains processed LaTeX files ready for compilation. Never edit files in this directory directly.

### `manuscripts/`
- **Contents:** Main manuscript `.tex` files (e.g., `indirect-support.tex`).
- **Usage:** These are the primary entry points for each manuscript. They may import variables and sections as needed.
- This is currently legacy

### Other files and folders
- Files such as `.bst`, `.cls`, and `.bib` are standard LaTeX support files (bibliography styles, class files, reference databases, etc.).
- The `empty.eps` file is a placeholder for figures.

---

## Variable Management

To ensure reproducibility and easy updating of manuscript values (e.g., results, statistics), variables are defined in JSON files within the `variables/` directory.

### How Variables Are Defined

Variables are stored in JSON files (e.g., `variables/indirect-support.json`):

```json
{
  "OTG_GWAS_SE": 0.30,
  "PIGEAN_GWAS_SE": 0.53,
  "PIGEAN_DIRECT_REGRESSION_P_VALUE": 7.5142e-13,
  "NUM_PIGEAN_TRAITS": "6,488"
}
```

### How Variables Are Used in Templates

In your LaTeX section files, use the `{{variable_name}}` syntax with optional Python-style formatting:

```latex
% Simple replacement
The standard error was {{OTG_GWAS_SE}}.

% With formatting
The p-value was {{PIGEAN_DIRECT_REGRESSION_P_VALUE:.2e}}.
The R² was {{PIGEAN_RIDGE_REGRESSION_R2:.2f}}.
We analyzed {{NUM_PIGEAN_TRAITS:,}} traits.

% Supported formats:
% :.2f  = 2 decimal places (0.30)
% :.2e  = scientific notation (7.51e-13)
% :,    = thousands separator (6,488)
% :.1%  = percentage (58.0%)
```

### Undefined Variables

If you use `{{VARIABLE_NAME}}` in your template but haven't defined it in the JSON yet, the build script will:
- Replace it with `XXXX` (placeholder)
- Show a warning with the file and line number
- Continue building (unless you use `--strict` mode)

This allows you to write your manuscript first, then fill in the actual values from analysis later.

### Build Process

The build script (`scripts/build.py`) processes templates and generates compilation-ready LaTeX files:

```bash
# Build the latest version
python scripts/build.py

# Build specific version
python scripts/build.py --manuscript indirect-support --date 10072025

# Build with figure cropping
python scripts/build.py --crop-figures

# Strict mode (fail on undefined variables)
python scripts/build.py --strict
```

The build process:
1. Loads variables from JSON files
2. Processes section templates (replaces `{{variable}}` syntax)
3. Updates `\input` paths to point to processed files
4. Optionally crops figure whitespace
5. Copies supporting files (.bib, .bst, .cls)
6. Outputs to `out/` directory

---

## Figure Management

Figures are managed through a manifest system (`figures/manifest.json`) that provides centralized control over figure processing and placeholder generation.

### Figure Manifest Structure

```json
{
  "figures": {
    "figure_1": {
      "source": "figures/indirect-support/real/pigean-figure-1.png",
      "caption_height": "2in",
      "crop": true,
      "width": "\\textwidth"
    },
    "future_analysis": {
      "source": null,
      "caption_height": "3in",
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

### Using Figures in Templates

```latex
\begin{figure}[t!]
    \centering
    {{fig:figure_1}}
    \caption{Your caption here}
    \label{fig:example}
\end{figure}
```

During build, `{{fig:figure_1}}` expands to:
```latex
\includegraphics[width=\textwidth]{../../figures/indirect-support/real/pigean-figure-1.png}
```

### Figure Processing

The build system:
1. Looks up figure ID in manifest
2. Checks if source file exists
3. If exists: processes (crops if needed), copies to `out/figures/`
4. If missing: uses placeholder with appropriate caption height
5. Generates `\includegraphics` with correct path and width

### Placeholder Workflow

Write your manuscript before generating figures:

1. Add figure to manifest with `source: null`
2. Set `caption_height` (2in, 3in, or 4in)
3. Use `{{fig:figure_id}}` in LaTeX
4. Build shows placeholder
5. Later: create figure, update manifest path, rebuild

### Generating Placeholders

```bash
python scripts/generate_placeholders.py
```

This creates placeholders for different caption heights (2in, 3in, 4in).

---

## Zotero Reference Management

All references for this project are managed via Zotero:

- **Zotero Group:** [Flannick Lab Zotero Group](https://www.zotero.org/groups/5753581/flannick_lab)
- **Access:** If you need access, contact Chase via Slack.
- **Instructions:**
  1. Create a Zotero account if you do not have one.
  2. Link your Zotero account to Overleaf.
  3. Add references to the Flannick Lab > pigean collection in Zotero.
  4. Refresh the `references.bib` file in this repository to update all BibTeX entries.

---

## Daily Workflow

### Creating a New Version

```bash
# 1. Create new dated version from existing
python scripts/make_today_version.py versions/indirect-support/main_10072025.tex

# This creates:
#   - versions/indirect-support/main_10282025.tex
#   - sections/indirect-support/10282025/*.tex (copies of all sections)
```

### Editing and Building

```bash
# 2. Edit section templates (use {{variable}} syntax)
# Edit files in: sections/indirect-support/10282025/

# 3. Update variables as needed
# Edit: variables/indirect-support.json

# 4. Build the manuscript
python scripts/build.py

# Output will be in: out/versions/indirect-support/main_10282025.tex
```

### Using Figures

```bash
# Add figures to manifest
# Edit: figures/manifest.json

# Use in LaTeX:
# {{fig:figure_id}}
```

### Using Canva Figures

**Simple 3-step workflow (no API approval needed):**

1. **Configure manifest** (`figures/manifest.json`):
```json
{
  "canva": {
    "source": "figures/indirect-support/canva-exports/main-design.zip",
    "output_dir": "figures/indirect-support/real",
    "auto_extract": true,
    "crop": true,
    "pages": {
      "1": {"filename": "pigean-figure-1.png"},
      "2": {"filename": "validation-figure-2.png"}
    }
  }
}
```

2. **Download from Canva** and place ZIP at the configured location

3. **Use in templates**:
```latex
{{canva:1}}  % Automatically extracts, crops, and inserts figure
{{canva:2}}
```

4. **Build** (extraction happens automatically):
```bash
python scripts/build.py
```

See [Canva Integration Guide](docs/CANVA.md) for complete documentation including API mode setup.

### Compiling

```bash
# 5. Compile the generated LaTeX
cd out
pdflatex versions/indirect-support/main_10282025.tex
bibtex versions/indirect-support/main_10282025
pdflatex versions/indirect-support/main_10282025.tex
pdflatex versions/indirect-support/main_10282025.tex
```

### Migration from LuaLaTeX Variables

If you have existing LuaLaTeX variable files:

```bash
# Convert to JSON format
python scripts/migrate_variables.py variables/manuscript-variables.tex

# Then manually update your .tex files to use {{variable}} instead of LuaLaTeX syntax
```

## General Guidelines

- **Keep all manuscript content** in the respective `.tex` files for each manuscript. Avoid using `\input{...}` for section files unless required for modularity.
- **Figures and tables** should be placed in their respective directories and subdirectories.
- **Notes and outlines** can be placed in the "Notes" section within each manuscript, between `\begin{comment}` and `\end{comment}`.
- **Source files** in `sections/` and `versions/` are templates - never edit files in `out/` directly.
- **For help or questions,** contact Chase via Slack.

---

## Rendering Manuscripts

- To render a specific manuscript, set the main document in your LaTeX editor (e.g., Overleaf) to the desired `.tex` file in the `manuscripts/` or `versions/` directory.

---

*This README is structured for both human and AI consumption, with explicit directory and workflow documentation to support automation and reproducibility.*