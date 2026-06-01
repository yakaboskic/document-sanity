# document-builder-template

A ready-to-clone GitHub template for manuscripts built with
[latex-builder](https://github.com/yakaboskic/latex-builder). Markdown is
the source of truth; builds produce a compilable LaTeX tree, a PDF, an
interactive HTML viewer, and optional markdown-preview blocks for GitHub.

## Clone and rename

On GitHub, click **Use this template** → **Create a new repository**.
Locally:

```bash
git clone https://github.com/<you>/<your-repo> my-paper
cd my-paper

# Rename the project in pyproject.toml
sed -i '' 's/document-builder-template/your-slug/' pyproject.toml     # macOS
sed -i    's/document-builder-template/your-slug/' pyproject.toml     # linux
```

Edit `src/initial/manifest.yaml` with your title / authors /
affiliations / abstract. Add `\newcommand` macros to
`templates/article.tex` if your writing wants custom math shortcuts
(`\prob` → `\text{Pr}`, etc.). Fill `src/<MMDDYYYY>/docs/*.md` with your
sections.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (`brew install uv` or
  `pipx install uv`)
- A TeX distribution (MacTeX / TeX Live) with `pdflatex` and `bibtex` for
  PDF builds

## Quickstart

```bash
make install              # pulls latex-builder from GitHub main and syncs venv
make pdf                  # build + compile out/<ver>/pdf/main.pdf
make html                 # interactive HTML viewer at out/<ver>/html/index.html
make serve                # also runs `make html`, opens http://localhost:8000
```

`make install` always pulls the latest `latex-builder` commit from GitHub
`main`. Use `make install-pinned` for strictly lockfile-reproducible
builds (CI).

## Workflow

1. Edit `src/<ver>/docs/*.md`. See
   [latex-builder docs](https://github.com/yakaboskic/latex-builder/tree/main/docs)
   for the opinionated conventions:
   - Figures go under `src/<ver>/figures/<figure-id>/<figure-id>.{pdf,png,html,...}`.
   - Label prefixes (`fig:`, `tab:`, `eq:`, `sec:`) drive automatic
     numbering in the HTML viewer.
   - Variables with provenance power the HTML viewer's interactive side
     panel.

2. **After editing any ```latex block**, refresh the markdown-preview:
   ```bash
   make preview
   ```
   This regenerates inline `![alt](path)` / `$$…$$` / pipe-table
   approximations so the doc renders meaningfully on GitHub, VSCode,
   Obsidian, and Cursor.

3. **Before committing**, optionally verify previews are up-to-date:
   ```bash
   make preview-check
   ```
   Returns non-zero if any ```latex block's preview is stale. Good for
   CI.

4. Build and inspect:
   ```bash
   make pdf                                     # for submission-quality output
   make html                                    # for interactive review
   ```

## Cutting a new version

```bash
# Copy src/initial/ (or the latest version) to today's date
uv run latex-builder new-version --strategy date
```

Versions are directories under `src/`. The template ships with
`src/initial/` — on first real cut, `new-version` creates
`src/MMDDYYYY/` for an archived snapshot, and subsequent `new-version`
runs increment the date from there. All commands auto-detect the latest
version; pass `VERSION=<name>` to the Makefile for a specific one
(e.g. `make pdf VERSION=initial`).

## Layout

```
.
├── pyproject.toml          # declares latex-builder as the only dep
├── Makefile                # install / build / pdf / preview / html / serve
├── .gitignore              # ignores out/ and build intermediates
├── README.md               # you are here
├── templates/
│   └── article.tex         # default LaTeX template with insertion points
│                           # replace with nature.tex + sn-jnl.cls for Nature
└── src/
    └── initial/            # starter version — use `new-version` to snapshot dated copies
        ├── manifest.yaml   # metadata, variables, figures, tables — one-stop config
        ├── docs/           # markdown sections in manifest.sections order
        │   ├── introduction.md
        │   ├── methods.md
        │   ├── results.md
        │   └── discussion.md
        ├── figures/        # <id>/<id>.{pdf,png,html} subdirectory layout
        │   └── example/
        │       └── example.png
        ├── tables/         # optional .tex tables (you can also inline them)
        └── references.bib  # bibliography
```

## References

- **latex-builder repo**: https://github.com/yakaboskic/latex-builder
- **Opinionated docs**: https://github.com/yakaboskic/latex-builder/tree/main/docs
- **Example paper project**: https://github.com/yakaboskic/pigean-indirect-support
