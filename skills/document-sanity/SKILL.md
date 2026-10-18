---
name: document-sanity
description: >-
  Write, build and ship papers and proposals with document-sanity: markdown
  sections plus one manifest.yaml per document become a PDF (LaTeX), an
  interactive HTML viewer and a Word .docx, with every number carrying its
  provenance. Use in a document-sanity project (a pyproject.toml that depends
  on document-sanity, with src/<doc>/manifest.yaml folders) to start a
  project, onboard Word/PDF/LaTeX sources, edit sections, add a variable,
  figure, table or citation, tune the Word template, cut a new version,
  check every build, or publish on GitHub Pages.
argument-hint: "[init | onboard | iterate | figures | variables | cite | word | version | import | check | deploy]"
user-invocable: true
license: MIT
metadata:
  version: "0.2.0"
  family: sanitism
---

# document-sanity, the router

One manifest is the source of truth, every output is generated, every number
carries its provenance, and a new version of a document is a folder. That's
the whole Sanitism bit: built for autists to communicate their work, sanely.

**The skill explains; the CLI does.** When a command exists for a step, run
it. Don't hand-write what a command generates.

## 1. Find the project root

Walk up from the current directory to the nearest folder that has **both**

- a `pyproject.toml` whose dependencies include `document-sanity`, and
- at least one `src/<doc>/manifest.yaml`.

Call that folder `ROOT`. Run every command from `ROOT` and resolve every path
in the mode files against it, never against the shell's starting directory.

- Neither found: there's no project yet. Use `init` mode.
- `src/<doc>/manifest.yaml` but no such `pyproject.toml` (an older paper repo,
  or the tool's own checkout): commands still work through
  `uv run document-sanity … --root ROOT`, but say what's missing.
- An `init.py` next to `pyproject.toml`: a fresh "Use this template" copy that
  hasn't been named yet. `init` mode, case B.

## 2. Check the tool against this skill

```bash
uv run document-sanity --version
```

This skill was written for the version in `metadata.version` above. If the
CLI reports a different version, **the CLI wins**: before you rely on a flag
or command named here, read `uv run document-sanity <command> --help`. Then
suggest `uv run document-sanity skills --force` to bring this skill up to
date with the installed tool.

If `uv run` can't find the tool, the project isn't installed yet: run
`uv sync` first, as in `init` mode.

## 3. Route

Always read `modes/_shared.md` first, then the mode's file. Mode files sit
next to this `SKILL.md`.

| `$mode` | Read | For |
|---|---|---|
| *(empty)* | the menu below | |
| `init` | `modes/init.md` | start a project, or name a fresh template copy |
| `onboard` | `modes/onboard.md` | turn Word / markdown / PDF / CSV sources into a new document |
| `iterate` | `modes/iterate.md` | edit an existing document: the edit → preview → build loop |
| `figures` | `modes/figures.md` | figures, multi-format artifacts, draw.io compositions |
| `variables` | `modes/variables.md` | a number (or table) with its provenance |
| `cite` | `modes/cite.md` | citations, the bibliography, `\ref` / `\label` |
| `word` | `modes/word.md` | the .docx template, Word styles, the layout pass |
| `version` | `modes/version.md` | a new version (a folder) of a document |
| `import` | `modes/import.md` | an existing LaTeX project or `.tex` file → markdown |
| `check` | `modes/check.md` | is it actually right? (run before saying "done") |
| `deploy` | `modes/deploy.md` | GitHub Pages or another static host (public!) |

When `$mode` is free text rather than a mode name, pick the closest one: "fix
the typo in methods" is `iterate`, "here's the Word draft from my co-author"
is `onboard` (new document) or `iterate` (tracked changes against one we
have), "the sample size changed" is `variables`, "make it look like the
agency's template" is `word`, "snapshot this before submission" is `version`,
"put it online" is `deploy`. Say which mode you picked.

## Menu

```
document-sanity, one markdown source, three printouts

  /document-sanity init       start a project (or name a fresh template copy)
  /document-sanity onboard    Word / PDF / CSV / figures → a new src/<doc>/
  /document-sanity iterate    edit → preview → build, until it's right
  /document-sanity figures    figures/<id>/<id>.{pdf,png,svg,html}, draw.io sync
  /document-sanity variables  {{NUMBERS}} with provenance; {{tab:data}} tables
  /document-sanity cite       \cite{} and references.bib; \ref{} and \label{}
  /document-sanity word       the .docx template, styles, pagination pass
  /document-sanity version    snapshot a document into a new folder
  /document-sanity import     LaTeX → markdown
  /document-sanity check      every target builds, every reference resolves
  /document-sanity deploy     GitHub Pages (public!) or any static host
```
