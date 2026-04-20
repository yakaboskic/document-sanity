# latex-builder

Build LaTeX documents from Markdown (or LaTeX) source files with variable substitution, figure management, and versioned builds.

## How it works

`latex-builder` provides a build pipeline for LaTeX manuscripts:

1. **Source files** live in `sections/<manuscript>/<version>/` as `.md` or `.tex` files
2. **Variables** are defined in `variables/<manuscript>.json` and referenced with `{{VARIABLE}}` syntax
3. **Figures** are managed via a `manifest.json` and referenced with `{{fig:id}}` syntax
4. **Versions** are snapshots created with configurable naming: date-based, fun random names, or both
5. **Build** processes all templates, substitutes variables, converts markdown to LaTeX, and outputs a clean compilation-ready directory

## Install

```bash
pip install -e .
# or with uv:
uv pip install -e .
```

## CLI

### Build a manuscript

```bash
# Auto-detect latest version
latex-builder build

# Specific manuscript and version
latex-builder build --manuscript my-paper --version 04202026

# Build and compile to PDF
latex-builder build --compile

# Verbose with strict mode
latex-builder build -v --strict
```

### Create a new version

```bash
# From an existing version, using date + fun name (default)
latex-builder new-version versions/my-paper/main_04202026.tex

# Date only
latex-builder new-version versions/my-paper/main_04202026.tex --strategy date

# Fun name only (e.g., "elegant-crimson-fox")
latex-builder new-version versions/my-paper/main_04202026.tex --strategy fun

# Both (e.g., "04202026-elegant-crimson-fox")
latex-builder new-version versions/my-paper/main_04202026.tex --strategy both

# Preview without writing
latex-builder new-version versions/my-paper/main_04202026.tex --dry-run
```

### Convert markdown to LaTeX

```bash
# Convert a single file
latex-builder convert content.md -o content.tex

# Don't escape LaTeX special chars (for source with embedded LaTeX)
latex-builder convert content.md --no-escape
```

## Project structure

A `latex-builder` project looks like:

```
my-paper/
  versions/
    my-paper/
      main_04202026.tex              # Main document (references sections)
      main_04202026-swift-fox.tex    # Another version
  sections/
    my-paper/
      04202026/
        introduction.md              # Markdown source
        methods.tex                  # Or pure LaTeX source
        results.md
      04202026-swift-fox/
        ...
  variables/
    my-paper.json                    # Variables for substitution
    shared.json                      # Shared across manuscripts
  figures/
    my-paper/
      figure1.png
    manifest.json                    # Figure definitions
  references.bib                     # Bibliography
  *.cls, *.bst                       # LaTeX class/style files
  build/                             # Generated output (gitignored)
    my-paper/
      main_current.tex
      sections/*.tex
      figures/*
      README.md
```

## Variable syntax

In your `.md` or `.tex` source files:

```
The p-value was {{PVALUE:.2e}}.
The R-squared was {{R2:.2f}}.
We analyzed {{NUM_TRAITS:,}} traits.
```

Supported format specs: `:.Nf` (decimals), `:.Ne` (scientific), `:,` (thousands), `:.N%` (percentage).

Undefined variables render as `XXXX` (configurable) and are reported in the build summary.

## Markdown source

Source files can be markdown with YAML frontmatter:

```markdown
---
title: My Paper
author: Chase
---

# Introduction

This is the **introduction** with `inline code` and a variable: {{NUM_SAMPLES:,}}.

## Methods

1. First step
2. Second step

```latex
% Raw LaTeX passes through unchanged
\begin{equation}
  E = mc^2
\end{equation}
```

> This blockquote becomes a LaTeX quote environment.
```

The markdown is converted to LaTeX during build. You can also use pure `.tex` files in any section.

## Version naming

| Strategy | Example | Description |
|----------|---------|-------------|
| `date` | `04202026` | MMDDYYYY format |
| `fun` | `elegant-crimson-fox` | Random name via [coolname](https://pypi.org/project/coolname/) |
| `both` | `04202026-elegant-crimson-fox` | Date + fun name |

## Modeled after

- **[word-builder](https://github.com/yakaboskic/word-builder)**: CLI architecture, markdown-as-source philosophy, content builder pattern
- **[pigean-manuscripts](https://github.com/yakaboskic/pigean-manuscripts)**: Build system, variable processor, figure manifest, versioning scheme
