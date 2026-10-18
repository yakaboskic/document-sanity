# check: is it actually right?

Run this before telling the user something is done, and report what each step
said, including warnings.

## 1. One command

```bash
uv run document-sanity check <doc>       # or no DOC: every document under src/
```

For each document it runs, and prints one line per step:

| Step | Passes when |
|---|---|
| `preview` | every ```latex block's preview is current (`preview --check`) |
| `pdf` | the LaTeX build works and pdflatex compiles it with no `!` errors |
| `refs` | every `{{VAR}}` is defined, every `\cite` key is in `references.bib`, every `\ref` has a `\label` |
| `html` | the viewer builds → `out/<doc>/html/index.html` |
| `word` | the .docx builds (plus `scripts/finalize_word_layout.py`) → `out/<doc>/word/main.docx` |

It exits non-zero on any `✗`. Fix what it reports; don't silence it. A
stale preview: `uv run document-sanity preview -V <doc>`, then check again.

No TeX installed: the `pdf` step is a `!` warning, not a pass. Say the PDF
wasn't built. `--no-pdf` skips it on purpose.

`check` doesn't run draw.io. If a composed figure's panels changed, also run
`uv run document-sanity drawio status <fig> -V <doc>`.

## 2. Look at it

`check` proves it builds, not that it reads right. Open what the user will
look at:

- PDF: `out/<doc>/pdf/main.pdf`
- HTML: `python3 -m http.server --directory out/<doc>/html 8000` (runs until
  stopped), then http://localhost:8000. Click a variable to see its
  provenance panel.
- Word: `out/<doc>/word/main.docx`

If you can drive a browser or read the PDF, look at the section you changed.
If you can't, say so and ask the user to look.

## What "done" means

`check` is clean (or every warning is explained), the preview blocks are
current, and someone has looked at the change. Say which of those you did.
