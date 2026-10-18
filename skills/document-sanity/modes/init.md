# init: start a project

Two situations. Work out which one you're in first.

## A. No project yet

Ask the user (one message, all at once, with defaults):

- the folder (new, or `.` for the current one)
- the document title, author name and email
- which starters to keep: `manuscript` (a paper: title block, abstract,
  Introduction / Methods / Results / Discussion), `proposal` (SBIR/NIH/NSF
  style: hand-numbered sections, no auto title block), or `both` (default)
- whether they want git (`--git`). Without it the folder has no `.git`, which
  is fine for people who don't want GitHub.

Then run the tool straight from its release, no install needed:

```bash
uvx --from "document-sanity @ git+https://github.com/yakaboskic/document-sanity.git@v0.2.0" \
  document-sanity init DIR --yes \
  --title "Title" --author "Name" --email "me@lab.org" --starter manuscript
```

Use the newest release tag (https://github.com/yakaboskic/document-sanity/releases)
rather than the one written here, if it's newer. A lab that keeps its own fork
of the template adds `--from gh:owner/repo[@ref]`. `GH_TOKEN` must be set for a
private fork.

`--title` and the author go into every starter's `manifest.yaml`
(`metadata.title`, `metadata.authors`); the project name (default: the
folder's name) goes into `pyproject.toml` and the README. Affiliations,
abstract and keywords stay as the template's placeholders. Edit them next.

**Knitting into an existing folder** (`DIR` has files already): `init` never
overwrites. If it lists conflicts, show the user the list and ask. Then either
move those files aside, or rerun with `--force` if they say so.

## B. A fresh template copy

The folder has an `init.py` next to `pyproject.toml`. Someone used "Use this
template" or cloned document-sanity-template. Ask the same questions, then:

```bash
python init.py --yes --title "Title" --author "Name" --email "me@lab.org" --starter both
```

`init.py` is a thin shim. It runs `document-sanity init --in-place` with the
version pinned in `pyproject.toml`, renames the project, drops the starters
the user doesn't keep, installs this skill, and removes itself.

## Then (both cases)

```bash
cd DIR
uv sync                                   # installs the pinned document-sanity, writes uv.lock
uv run document-sanity check --no-pdf     # HTML + Word build, previews current
```

`init` doesn't copy the template's `uv.lock`; the first `uv sync` writes one
that matches the pin. If the project uses git, commit it: the Pages workflow
installs with `uv sync --locked`.

PDFs need a TeX distribution with `pdflatex` and `bibtex` (MacTeX or
BasicTeX on macOS, `texlive-latex-extra` on Debian/Ubuntu). If it's missing,
`check` says so and skips the PDF; HTML and Word don't need it.

Finish by pointing at the next step: `/document-sanity onboard` to bring in
existing material, or `/document-sanity iterate` to start writing in
`src/<doc>/docs/`.
