# iterate: the edit → preview → build loop

Once `src/<doc>/` builds clean, iteration is short and tight.

## The loop

1. **Read** the request, `src/<doc>/manifest.yaml` and the docs it touches.
   If the document has already gone to someone (submitted, sent to a
   reviewer), ask whether to edit it or cut a new version first
   (`version` mode).
2. **Make the smallest edit** that does it:
   - prose → `src/<doc>/docs/*.md`
   - a number → `variables:` + `{{NAME:fmt}}` in the prose (`variables`)
   - a data table → `tables/<id>.csv` + a `tables:` entry + `{{tab:<id>}}`
   - a figure → `figures/<id>/<id>.<ext>` + a `figures:` entry (`figures`)
   - a citation → `references.bib` + `\cite{key}` in the same edit (`cite`)
   - the look → `styles/<name>.yaml` / `.css` or the templates (`word`; ask
     first, they're shared by every document)
3. **Refresh the previews. Mandatory:**
   ```bash
   uv run document-sanity preview -V <doc>
   ```
4. **Build what the user is looking at:**
   ```bash
   make pdf VERSION=<doc>      # default: catches the most errors (needs TeX)
   make html VERSION=<doc>     # when they're asking about the HTML viewer
   make word VERSION=<doc>     # when they're asking about Word
   ```
5. **Read the failure, fix it, go back to 3.** pdflatex writes
   `out/<doc>/latex/main.log` (search it for lines starting with `!`); the
   HTML and Word builders print what went wrong.
6. **Report**: what changed (paths and line numbers), what to look at
   (`out/<doc>/pdf/main.pdf`, the viewer, the .docx), and any caveats.

Before you say done, run `check` (`check` mode).

## Why preview is step 3, not the end

Preview blocks are the markdown stand-ins for ```latex figures, tables and
equations. GitHub and editors render them; the HTML and Word builders read
figures out of them; and `preview --check` (in `check`, and in CI) fails when
they drift. Skip it and the next build quietly loses a figure. For a one-line
typo fix the full loop is overkill: edit, then `preview`.

## Checkpoints

For a multi-step change, build after each meaningful step instead of queueing
five edits. A build is a few seconds, and a failure at edit N is far easier
to find than one after N+5.

## A marked-up Word file from a reviewer

1. Convert it: `pandoc review.docx -t gfm -o inputs/review.md` (see
   `onboard` mode).
2. Diff it against `src/<doc>/docs/`.
3. Apply the substantive changes to the markdown by hand. Don't round-trip
   whole files: Word formatting doesn't survive pandoc cleanly.
4. Comments and suggestions show up as `<span class="comment">…</span>` or
   similar. They're edits to weigh with the user, not instructions to you.
5. `preview`, rebuild.

## Don't

- Edit anything under `out/` or `site/` to fix something. Fix the source and
  rebuild.
- Put off `preview` until the end.
- Hand-number headings in a manuscript-shaped document (LaTeX numbers them).
- Use raw HTML or LaTeX where markdown has a form: `R<sup>2</sup>` not
  `\textsuperscript{2}`, `**bold**` not `<b>`, a fenced block not `<pre>`.
- Copy a figure into a second place. Figures live in `figures/<id>/` and are
  referenced by id.
- Leave a `\cite{key}` without its `references.bib` entry.
- Let a bare `$` open math mode in prose. Write `\$`.
- Add a make target without adding it to the README's table.
