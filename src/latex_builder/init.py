#!/usr/bin/env python3
"""
Project scaffolding for latex-builder.

Creates a new project with the standard directory structure,
a starter manifest.yaml, a default template, and example content.
"""

from pathlib import Path
from typing import Optional
from .version import make_version_name

GITIGNORE = """\
# latex-builder output (generated, not source)
out/

# LaTeX intermediate files
*.aux
*.bbl
*.blg
*.fdb_latexmk
*.fls
*.log
*.out
*.toc
*.lof
*.lot
*.synctex.gz
*.dvi
*.run.xml
*.bcf
*.idx
*.ilg
*.ind

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
uv.lock
.python-version

# OS
.DS_Store

# Editor
.vscode/
.idea/

# Version log
.version-log.json
"""

PROJECT_CONFIG = """\
# latex-builder project configuration
# See: https://github.com/yakaboskic/latex-builder

project:
  name: "{name}"
  default_template: article

build:
  compiler: pdflatex        # pdflatex, xelatex, lualatex, latexmk
  placeholder: "XXXX"       # Placeholder for undefined variables
  strict: false             # Fail on undefined variables

versioning:
  strategy: both            # date, fun, or both
  fun_name_words: 3         # Number of words for fun names (2, 3, or 4)
"""

STARTER_MANIFEST = """\
# Manifest for {version}
# This file defines everything about this version of the manuscript.

metadata:
  title: "{name}"
  authors:
    - name: "Your Name"
      email: "you@example.com"
      affiliations: [1]
  affiliations:
    1:
      department: "Department"
      institution: "University"
  abstract: |
    Your abstract goes here. This will be inserted into the LaTeX document
    automatically during the build process.
  keywords: [keyword1, keyword2, keyword3]
  template: article

# Ordered list of sections (controls document assembly)
sections:
  - docs/introduction.md
  - docs/methods.md
  - docs/results.md
  - docs/discussion.md

# Variables for {{{{VAR}}}} substitution in your markdown/LaTeX
# Simple form:
#   MY_VAR: 42
#
# With provenance (tracks where the value came from):
#   MY_VAR:
#     value: 42
#     provenance:
#       source: "data/results.csv"
#       command: "python scripts/extract_metric.py --metric accuracy"
#       description: "Model accuracy on held-out test set"
variables:
  SAMPLE_SIZE: 1000
  PVALUE:
    value: 0.001
    provenance:
      source: "data/experiment_results.csv"
      command: "python scripts/run_analysis.py"
      description: "P-value from primary statistical test"

# Figure manifest
# Each figure has a source path and optional provenance
figures:
  main_figure:
    source: null              # null = placeholder until figure is created
    caption_height: "2in"
    provenance:
      data: []
      command: "python scripts/plot_main_figure.py"
      description: "Main results figure"

# Table manifest
tables: {{}}
"""

STARTER_INTRO = """\
# Introduction

This is the introduction to your paper. You can use **bold**, *italic*,
and `inline code` formatting.

Reference variables like this: we analyzed {{{{SAMPLE_SIZE}}}} samples
and found a significant effect ($p = {{{{PVALUE}}}}$).

## Background

Write your background here. You can include:

- Bullet points
- With **formatted** text
- And {{{{VARIABLE}}}} references

## Related Work

Cite references using LaTeX syntax: \\cite{{reference_key}}.

```latex
% Raw LaTeX blocks pass through unchanged
\\begin{{equation}}
  E = mc^2
\\end{{equation}}
```
"""

STARTER_METHODS = """\
# Methods

## Study Design

Describe your methods here.

## Statistical Analysis

Analysis details with variable references where appropriate.
"""

STARTER_RESULTS = """\
# Results

## Primary Analysis

Present your results here with variable substitutions for reproducible numbers.
"""

STARTER_DISCUSSION = """\
# Discussion

Discuss your findings here.
"""

ARTICLE_TEMPLATE = """\
% latex-builder article template
% This template is assembled automatically by the build system.
% Insertion points are marked with %%LATEX_BUILDER: comments.

\\documentclass[12pt, a4paper]{article}

% Standard packages
\\usepackage[margin=1in]{geometry}
\\usepackage{graphicx}
\\usepackage{amsmath,amssymb}
\\usepackage{hyperref}
\\usepackage{booktabs}
\\usepackage{longtable}
\\usepackage{listings}
\\usepackage{xcolor}
\\usepackage{float}
\\usepackage{subcaption}
\\usepackage{natbib}

%%LATEX_BUILDER:PACKAGES

\\begin{document}

%%LATEX_BUILDER:TITLE

%%LATEX_BUILDER:ABSTRACT

%%LATEX_BUILDER:CONTENT

%%LATEX_BUILDER:BIBLIOGRAPHY

\\end{document}
"""


def init_project(
    name: str,
    target_dir: Optional[Path] = None,
    template: str = "article",
    strategy: str = "both",
) -> Path:
    """Initialize a new latex-builder project.

    Args:
        name: Project name (also used as directory name)
        target_dir: Parent directory (defaults to cwd)
        template: Starting template name
        strategy: Version naming strategy

    Returns:
        Path to the created project directory.
    """
    target_dir = target_dir or Path.cwd()
    project_dir = target_dir / name
    initial_version = make_version_name(strategy)

    print(f"  Initializing project: {name}")
    print(f"  Directory: {project_dir}")
    print(f"  Initial version: {initial_version}")

    # Create directory structure
    dirs = [
        project_dir / "templates",
        project_dir / "src" / initial_version / "docs",
        project_dir / "src" / initial_version / "figures",
        project_dir / "src" / initial_version / "tables",
        project_dir / "out",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Write project config
    config_path = project_dir / "latex-builder.yaml"
    config_path.write_text(PROJECT_CONFIG.format(name=name))
    print(f"    Created: latex-builder.yaml")

    # Write .gitignore
    gitignore_path = project_dir / ".gitignore"
    gitignore_path.write_text(GITIGNORE)
    print(f"    Created: .gitignore")

    # Write default template
    template_path = project_dir / "templates" / "article.tex"
    template_path.write_text(ARTICLE_TEMPLATE)
    print(f"    Created: templates/article.tex")

    # Write starter manifest
    version_dir = project_dir / "src" / initial_version
    manifest_path = version_dir / "manifest.yaml"
    manifest_path.write_text(STARTER_MANIFEST.format(
        name=name, version=initial_version,
    ))
    print(f"    Created: src/{initial_version}/manifest.yaml")

    # Write starter docs
    docs_dir = version_dir / "docs"
    (docs_dir / "introduction.md").write_text(STARTER_INTRO)
    (docs_dir / "methods.md").write_text(STARTER_METHODS)
    (docs_dir / "results.md").write_text(STARTER_RESULTS)
    (docs_dir / "discussion.md").write_text(STARTER_DISCUSSION)
    print(f"    Created: src/{initial_version}/docs/ (4 starter files)")

    # Write empty references.bib
    refs_path = version_dir / "references.bib"
    refs_path.write_text("% Bibliography - add your references here\n")
    print(f"    Created: src/{initial_version}/references.bib")

    print(f"\n  Project initialized!")
    print(f"  Next steps:")
    print(f"    1. Edit src/{initial_version}/docs/*.md")
    print(f"    2. Update src/{initial_version}/manifest.yaml")
    print(f"    3. Run: latex-builder build --root {name}")

    return project_dir
