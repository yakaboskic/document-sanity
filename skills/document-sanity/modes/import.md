# import: LaTeX → markdown

Two situations: a multi-version LaTeX project in the pigean-manuscripts
layout, or a plain `.tex` paper. For Word or PDF sources, use `onboard` mode.

## A. A pigean-style project

The source looks like:

```
old-paper/
├── versions/<manuscript>/main_<ver>.tex
├── sections/<manuscript>/<ver>/*.tex
├── variables/<manuscript>.json      # optional
└── figures/ …, *.bib
```

```bash
uv run document-sanity import --source ../old-paper --target . \
  --manuscript indirect-support --version 03302026 --name indirect-support
```

It writes `src/<name>/` with `manifest.yaml` (title, abstract, keywords,
section order, variables, figures, tables), one `docs/*.md` per section, the
bib and the figures. `--manuscript` and `--version` are auto-detected when
the source has only one. Don't point `--name` at an existing folder.

## B. A plain `.tex` paper

Convert each file, then assemble a document by hand, starting from a starter
as in `onboard` mode (step 1):

```bash
uv run document-sanity convert paper/introduction.tex -o src/<doc>/docs/introduction.md
uv run document-sanity convert paper/methods.tex --preserve-comments -o src/<doc>/docs/methods.md
```

A single-file paper: split it at its `\section`s into one `.md` each.

## What the converter does

- `\section` / `\subsection` → `#` / `##`; `\textbf`, `\textit`, `\texttt`,
  lists → markdown.
- Figures, tables, equations, align, tikz, algorithms, theorems and the like
  stay as ```latex blocks: the PDF compiles them verbatim, and `preview`
  writes the markdown stand-ins.
- `\cite`, `\ref`, `\label` and existing `{{VAR}}` tokens pass through.
- `\input{}` becomes a TODO marker. Resolve each one by hand.
- Comments are dropped, or kept as HTML comments with `--preserve-comments`.

## Then

1. Copy the old preamble's packages and `\newcommand`s into a template
   (`templates/<name>.tex`, set `metadata.template: <name>`) when the
   starter's doesn't cover them. Ask before editing a shared template.
   `preview` and the HTML viewer expand zero-argument `\newcommand` macros
   from it.
2. Hard-coded numbers in the prose → variables with provenance (`variables`).
3. Figures → `figures/<id>/<id>.<ext>` with a PNG for Word (`figures`).
4. `uv run document-sanity preview -V <doc>`, then `check <doc>` until it's
   clean. The PDF is the reference: compare it against the old one.
