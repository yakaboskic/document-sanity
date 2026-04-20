# PIGEAN Manuscript Hub - Claude Context

This file provides context for Claude Code sessions working with the PIGEAN Manuscript Hub repository.

---

## Active Manuscript: indirect-support

### Session Initialization (REQUIRED)

**On every session start, Claude MUST:**

1. **Identify the most recent version** by checking `versions/indirect-support/main_*.tex` and finding the latest date (format: `main_MMDDYYYY.tex`)

2. **Check if today's version exists**:
   - If today's version does NOT exist, ask the user: *"The most recent version is [DATE]. Would you like me to create a new version for today using the build system?"*
   - If user declines, work in the most recent existing version

3. **Load context** by reading:
   - The main manuscript file: `versions/indirect-support/main_[LATEST_DATE].tex`
   - All section files in: `sections/indirect-support/[LATEST_DATE]/*.tex`
   - Variables: `variables/indirect-support.json`
   - Available figures in: `figures/indirect-support/`
   - Available tables in: `Tables/`

### Writing Style Requirements

When writing or editing prose for this manuscript, follow these **academic paper style** guidelines:

**The 90/10 Rule**: Approximately 90% of sentences should contain at least ONE of:
- A **figure reference** (e.g., `Figure \ref{fig:validation-genetics}a`)
- A **quantitative value/metric** using template variables (e.g., `{{RARE_CMC_AUC:.3f}}`)
- A **citation** (e.g., `\cite{minikel_refining_2024}`)

**Sentence Construction Principles:**
- Lead with data, not interpretation
- Quantify claims whenever possible using variables from `indirect-support.json`
- Reference specific figure panels when describing results (e.g., "Figure 2a" not just "Figure 2")
- Use precise statistical language (confidence intervals, p-values, effect sizes)
- Avoid vague qualifiers ("significant" without numbers, "many", "several")

**Good Example:**
```latex
Indirect support significantly predicted direct genetic support for every held-out
chromosome across all 12 traits (Supplementary Table \ref{tab:loco-validation};
trait-level $\beta$ range {{MIN_LOCO_BETA}} to {{MAX_LOCO_BETA}}, all $p$={{MAX_LOCO_BETA_P}}).
```

**Bad Example:**
```latex
Our method showed significant improvement over baseline approaches in several metrics.
```

### Variable Usage and Creation

**Using Existing Variables:**
- Always use `{{VARIABLE_NAME}}` syntax for numerical values in `variables/indirect-support.json`
- Use formatting specifiers: `{{VAR:.2f}}` (decimals), `{{VAR:.2e}}` (scientific), `{{VAR:,}}` (thousands)

**Creating New Variables (ENCOURAGED):**
When a sentence would be stronger with a specific metric that doesn't exist yet:

1. **Add the variable to `variables/indirect-support.json`** with a `null` value:
   ```json
   "NEW_METRIC_NAME": null
   ```

2. **Use it in the prose** with appropriate formatting:
   ```latex
   The effect size was {{NEW_METRIC_NAME:.2f}}.
   ```

3. **Add a LaTeX comment** explaining what analysis is needed:
   ```latex
   % TODO: NEW_METRIC_NAME - Calculate the Cohen's d effect size comparing indirect
   % vs direct support predictions. This would quantify the practical significance
   % of the improvement shown in Figure 2a.
   The effect size was {{NEW_METRIC_NAME:.2f}}.
   ```

### Proactive Commentary (ENCOURAGED)

Claude should actively annotate the manuscript with comments suggesting improvements that cannot be addressed through prose edits alone. Use LaTeX comment blocks:

**Analysis Ideas:**
```latex
% ANALYSIS IDEA: Consider a sensitivity analysis holding out each geneset library
% individually to quantify which libraries contribute most to predictive power.
% This would strengthen the claim about model robustness and help readers
% understand which data sources are most valuable.
```

**Figure Suggestions:**
```latex
% FIGURE SUGGESTION: A scatter plot showing indirect vs direct support scores
% colored by trait category would help visualize the orthogonality claim made
% in this paragraph. Could replace or supplement the current density plot.
```

**Missing Evidence:**
```latex
% MISSING EVIDENCE: This claim about temporal stability would be strengthened
% by showing the correlation between 2018 and 2024 predictions. Consider adding
% {{TEMPORAL_CORRELATION_R2}} variable.
```

**Structural Suggestions:**
```latex
% STRUCTURE: This paragraph combines two distinct points (validation results
% and biological interpretation). Consider splitting into two paragraphs with
% the interpretation following the full presentation of results.
```

**Comment Prefixes:**
- `% ANALYSIS IDEA:` - Suggested new analyses
- `% FIGURE SUGGESTION:` - Ideas for figures or figure modifications
- `% MISSING EVIDENCE:` - Gaps that need data/citations
- `% STRUCTURE:` - Organizational improvements
- `% TODO:` - Specific actionable items (especially for new variables)
- `% QUESTION:` - Clarifications needed from the user

### File Locations

| Resource | Path |
|----------|------|
| Main manuscript versions | `versions/indirect-support/main_MMDDYYYY.tex` |
| Section files | `sections/indirect-support/MMDDYYYY/*.tex` |
| Variables (JSON) | `variables/indirect-support.json` |
| Figures | `figures/indirect-support/` |
| Tables | `Tables/` |
| References | `references.bib` |

### Build Workflow

After making edits, always use the build system:
```bash
python scripts/build.py
```

To create a new dated version:
```bash
python scripts/make_today_version.py versions/indirect-support/main_[PREVIOUS_DATE].tex
```

---

## Documentation

**For detailed documentation, see the [`docs/`](docs/) folder:**
- [Quick Reference](docs/QUICK_REFERENCE.md) - Common commands and syntax
- [Build System](docs/BUILD_SYSTEM.md) - Technical documentation
- [Canva Branding](docs/CANVA_BRANDING.md) - Design specifications
- [Examples](docs/examples/) - Template syntax examples

## Project Overview

The PIGEAN Manuscript Hub is a collaborative LaTeX manuscript writing repository for the PIGEAN project and related research manuscripts. It's designed to support reproducible research with modular organization of manuscript components.

## Key Features

### Modular Structure
- **manuscripts/**: Legacy main manuscript files
- **versions/**: Versioned main manuscript files (naming: `main_MMDDYYYY.tex`)
- **sections/**: Section `.tex` files organized by manuscript and date
- **figures/**: All figures organized by manuscript name
- **tables/**: LaTeX table files organized by manuscript and date
- **variables/**: Variable definition files using LuaLaTeX for reproducible results
- **scripts/**: Automation scripts for workflow optimization

### Variable Management System
The repository uses JSON files to define variables (e.g., `variables/indirect-support.json`). Templates use `{{variable}}` syntax with Python-style formatting. This ensures:
- Reproducibility: Update values in one place
- Consistency: Values propagate throughout the manuscript automatically
- Version control: Track changes to results over time
- Flexibility: Write manuscript first, fill in values later (undefined variables show as `XXXX`)

### Reference Management
All references are managed through the [Flannick Lab Zotero Group](https://www.zotero.org/groups/5753581/flannick_lab). The `references.bib` file is synced from the Zotero group's pigean collection.

## Available Scripts

### `build.py`
Main build script that processes templates and generates compilation-ready LaTeX files. Automatically:
- Loads variables from JSON files
- Replaces `{{variable}}` syntax with actual values
- Updates `\input` paths to point to processed files
- Optionally crops figure whitespace
- Copies supporting files to output directory

Usage:
```bash
# Auto-detect latest version
python scripts/build.py

# Build specific version
python scripts/build.py --manuscript indirect-support --date 10072025

# Build with figure cropping
python scripts/build.py --crop-figures

# Strict mode (fail on undefined variables)
python scripts/build.py --strict
```

### `make_today_version.py`
Creates a new versioned manuscript with today's date, automatically:
- Copying the main manuscript file
- Updating all section file references
- Creating new dated section directories

Usage:
```bash
python scripts/make_today_version.py versions/manuscript-name/main_MMDDYYYY.tex [--dry-run]
```

### `migrate_variables.py`
One-time migration script to convert LuaLaTeX variable files to JSON format.

Usage:
```bash
python scripts/migrate_variables.py variables/manuscript-variables.tex
python scripts/migrate_variables.py variables/manuscript-variables.tex --output variables/manuscript.json
```

### `generate_placeholders.py`
Generates placeholder figures with different caption heights (2in, 3in, 4in) for use during manuscript writing.

Usage:
```bash
python scripts/generate_placeholders.py
```

### `crop_figure_whitespace.py`
Automatically crops vertical whitespace from figure images while preserving width. Designed for the Canva workflow where figures are created at standardized dimensions (`width - side margins × height - caption height`).

Features:
- Detects and removes top/bottom whitespace automatically
- Configurable padding to preserve around content
- Preserves image width for consistent `\textwidth` usage in LaTeX
- Supports PNG, JPG, and other image formats
- Optional PDF support (requires `pdf2image` and `poppler-utils`)
- Dry-run mode to preview changes

Usage:
```bash
# Basic usage
uv run scripts/crop_figure_whitespace.py figure.png

# Custom padding (default is 10 pixels)
uv run scripts/crop_figure_whitespace.py figure.png --padding 20

# Save to different file
uv run scripts/crop_figure_whitespace.py figure.png --output figure_cropped.png

# Process multiple images
uv run scripts/crop_figure_whitespace.py fig1.png fig2.png fig3.png

# Preview without modifying
uv run scripts/crop_figure_whitespace.py figure.png --dry-run
```

This solves the common problem where Canva designs must be a fixed size, but the actual figure content may not fill the entire height. The script allows you to:
1. Design all figures in Canva at the standard paper dimensions
2. Export with consistent text sizing (for legibility)
3. Automatically crop excess whitespace while maintaining width
4. Insert in LaTeX with `\includegraphics[width=\textwidth]{figure}` without scaling issues

## Workflow Tips

### Daily Workflow
1. **Create new version**: `python scripts/make_today_version.py versions/manuscript/main_DATE.tex`
2. **Edit templates**: Edit section files in `sections/{manuscript}/{date}/`
   - Use `{{VARIABLE_NAME}}` for simple replacement
   - Use `{{VARIABLE_NAME:.2f}}` for formatted values
3. **Update variables**: Edit `variables/{manuscript}.json`
4. **Build**: `python scripts/build.py` (or with `--crop-figures`)
5. **Compile**: Compile from `current/{manuscript}/main_current.tex`

### Template Syntax

**Variables:**
```latex
% In your .tex files:
The p-value was {{PVALUE:.2e}}.
The R² was {{R2:.2f}}.
We analyzed {{NUM_TRAITS:,}} traits.

% Supported formats:
% :.2f  = decimal places
% :.2e  = scientific notation
% :,    = thousands separator
% :.1%  = percentage
```

**Figures:**
```latex
% In your .tex files:
\begin{figure}[t!]
    \centering
    {{fig:figure_1}}
    \caption{Your caption}
\end{figure}

% Define in figures/manifest.json:
{
  "figures": {
    "figure_1": {
      "source": "figures/manuscript/real/figure.png",
      "caption_height": "2in",
      "crop": true,
      "width": "\\textwidth"
    }
  }
}
```

### Adding Figures
1. Create figures in Canva using standardized dimensions
2. Export as PNG or PDF
3. Place in `figures/{manuscript-name}/` directory
4. Build with `--crop-figures` flag to auto-crop whitespace
5. Reference in LaTeX with `\includegraphics[width=\textwidth]{figures/manuscript-name/figure.png}`

### Managing Results
1. Update values in `variables/{manuscript-name}.json`
2. Run `python scripts/build.py`
3. Values automatically propagate throughout the manuscript
4. Version control tracks when results were updated

### Placeholder Workflow

**Variable Placeholders:**
Write your manuscript with placeholders for values you'll calculate later:
1. Write: `The correlation was {{NEW_ANALYSIS_R2:.2f}}.`
2. Build will show: `The correlation was XXXX.`
3. Build will warn: `⚠️ Undefined variable: NEW_ANALYSIS_R2`
4. Later, add to JSON: `"NEW_ANALYSIS_R2": 0.87`
5. Rebuild: `The correlation was 0.87.`

**Figure Placeholders:**
Write your manuscript before generating figures:
1. Add to manifest: `"future_fig": {"source": null, "caption_height": "2in"}`
2. Write: `{{fig:future_fig}}`
3. Build shows placeholder image
4. Build warns: `⚠️ future_fig - Source not found`
5. Later: create figure, update manifest, rebuild
6. Placeholder automatically replaced!

## Important Notes

- **Build system**: Run `python scripts/build.py` to generate compilation-ready LaTeX files
- **Source vs Output**: Never edit files in `current/` - they are generated from templates
- **Templates**: Source files in `sections/` and `versions/` use `{{variable}}` syntax
- **Main document**: Compile from `current/{manuscript}/main_current.tex`
- **Output structure**: `current/{manuscript}/` contains `main_current.tex`, `sections/`, `figures/`, and a `README.md` manifest
- **Notes and outlines**: Use `\begin{comment}...\end{comment}` blocks in manuscript files
- **Dry-run**: Most scripts support `--dry-run` for previewing changes
- **Git**: The `current/` directory is gitignored - only source templates are version controlled

## Contact

For questions or assistance, contact Chase via Slack.
