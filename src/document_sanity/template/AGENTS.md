# AGENTS.md

This project is built with [document-sanity](https://github.com/yakaboskic/document-sanity).
How to work in it (onboarding sources, the edit → preview → build loop,
figures, variables, citations, Word styles, versions, checking, publishing)
lives in the **document-sanity agent skill**:

- `.claude/skills/document-sanity/` (Claude Code: `/document-sanity [mode]`)
- `.agents/skills/document-sanity/` (Codex, Cursor, Pi and other agents)

Start with its `SKILL.md`, then `modes/_shared.md`. A fresh template copy
doesn't have the skill yet: `python init.py` installs it, and
`uv run document-sanity skills` installs or refreshes it in any project. The
source is [skills/document-sanity/](https://github.com/yakaboskic/document-sanity/tree/main/skills/document-sanity).

## Ground rules, in short

- **End every iteration with `make preview VERSION=<doc>`.** It refreshes the
  markdown stand-ins next to every ```latex block, which GitHub, the HTML
  viewer and Word all read. Non-negotiable.
- **Never edit `out/` or `site/`.** Edit `src/`, `templates/` or `styles/`,
  then rebuild.
- **Every number is a variable with provenance** in the document's
  `manifest.yaml`. Never invent a source or a citation; ask.
- **Always pass `VERSION=<doc>`** (or `-V <doc>`). Without it the tool picks
  the "latest" folder under `src/`, which is often not the one you mean.
- **`make check` (or `uv run document-sanity check`) before you say done.**

## This project

- `src/manuscript/` (a paper: auto title block, LaTeX-numbered sections) and
  `src/proposal/` (hand-numbered sections, `metadata.render: false`,
  `templates/proposal.tex`) are **starters**. For new material, make a new
  document with `uv run document-sanity new-version --source <starter> --name
  <new>` rather than overwriting one.
- Both share `templates/article.docx`, `styles/article.yaml` and
  `styles/article.css`. Changing them changes every document; ask first.
- `document-sanity word` lays the file out itself (table, heading and figure
  pagination, equation sizing), so `make word`, `check` and `site` all get it.
  Fix layout in the sources or `styles/`, never in `out/`.
- The Makefile is the human interface: `make help`. When you add a target,
  add it to the README's table.

Add project-specific notes for agents below (house style, reviewers'
preferences, which document is the live one).
