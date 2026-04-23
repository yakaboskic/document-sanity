# Bibliography

The HTML viewer builds a numbered reference list from `references.bib`
at `src/<ver>/references.bib` (or the project root, as fallback).
Citations are hyperlinked to the list; entries link out to DOIs when
available.

## Parser

`src/document_sanity/bib.py` — a minimal BibTeX reader, no external
dependencies. It handles:

- `@article{key, field = {value}, field = "value", field = raw, ...}`
- Nested braces in field values (balanced-brace scan).
- Quoted-string field values.
- Crude LaTeX accent commands in author names and titles:
  `\'{e}` → é, `\~{n}` → ñ, `\"{o}` → ö, `\c{c}` → ç, etc.
- `\textbf`, `\textit`, `\emph` stripping.
- Curly-quote conversion (`\`\`foo''`  → ``\`` … `'`), en/em dashes
  (`--` / `---`).
- `@comment`, `@preamble`, `@string` entries are skipped.

Not supported (because the BibTeX spec is a swamp):

- `@string` substitution (`author = abbrev_name` expansion).
- Nested macros like `{\it{x}}`.
- Multi-arg `\newcommand` in `.bib` headers.

If the above bite, switch the parser out for `bibtexparser` or
`pybtex` — the rest of the pipeline only cares about a
`{key: BibEntry}` dict.

## Citation numbering

First-appearance order across all sections in the order listed in
`manifest.sections`. The first `\cite{minikel_refining_2024}` gets
`[1]`, the next *new* key gets `[2]`, and so on. Repeat citations reuse
the same number.

Implementation: `html_builder.py::CitationCollector` tracks `order` (list
of keys in appearance order) and `_numbers` (key → int). Its `.resolve()`
is passed to `md2html` as the `resolve_citation` callable.

## Cite rendering

```markdown
Drug targets with genetic support are ~2× more likely to launch
\cite{minikel_refining_2024, cohen_sequence_2006}.
```

→

```html
Drug targets with genetic support are ~2× more likely to launch
[<a class="cite" href="#ref-minikel_refining_2024" title="minikel_refining_2024">16</a>,
 <a class="cite" href="#ref-cohen_sequence_2006" title="cohen_sequence_2006">1</a>].
```

- `\cite{key}` and `\citep{key}` and `\citet{key}` (any `\cite...`
  variant) are all accepted.
- Multiple comma-separated keys produce comma-separated links inside a
  single `[…]` bracket.
- Missing keys render as `?` with a red `.cite-missing` class so you
  can see them during review without breaking the build.

## Entry rendering

Each bib entry becomes:

```html
<li id="ref-minikel_refining_2024" value="16">
  <span class="bib-number">[16]</span>
  <span class="bib-body">
    <span class="bib-author">Eric V. Minikel, …</span>.
    <span class="bib-title">Refining the impact of genetic evidence …</span>.
    <em class="bib-venue">Nature</em>
    <strong>629</strong>, 624–629 (2024).
    <a href="https://doi.org/10.1038/s41586-024-07316-0"
       target="_blank" rel="noopener">https://doi.org/10.1038/s41586-024-07316-0</a>
  </span>
</li>
```

The two-child structure — `.bib-number` + `.bib-body` — is load-bearing.
CSS uses `display: grid; grid-template-columns: 2.5rem 1fr;` so the
`[N]` sits in the first column and the prose flows in the second. An
earlier version had each element (`.bib-author`, `.bib-title`, the
`.` separators, etc.) as siblings of `.bib-number`, which made the grid
auto-flow stack every part into its own row — visually catastrophic.

## Field priority

Display order in the rendered `<li>`:

1. **Author** — formatted `"First Last, First Last"`, truncated to 8
   names with " et al." appended.
2. **Title** — cleaned of LaTeX markup.
3. **Venue** — one of `journal`, `booktitle`, `publisher` (first match
   wins), italicized.
4. **Volume** (bold), **Number** (parenthesized), **Pages** (with `--`
   converted to en-dash), **Year** (parenthesized).
5. **DOI link** if `doi` is present; else `url`; else nothing.

## Placement

The `_bibliography` pseudo-section in `manifest.sections` controls where
the PDF build places `\bibliography{references}`. The HTML build ignores
it — instead, the full references section is always emitted at the
**end** of the generated HTML, after all other sections. That's typical
for web reading (scroll to references at the bottom), while the PDF
conventionally places references after the discussion.

If you want the HTML bibliography mid-document too, it's a small
addition: pick up the `_bibliography` pseudo-section in
`html_builder.build_html` and emit the bibliography HTML at that point
instead of at the end.

## Related code

| File | Responsibility |
|---|---|
| `src/document_sanity/bib.py::parse_bib` | BibTeX reader. |
| `src/document_sanity/bib.py::render_entry_html` | Per-entry `<li>` rendering. |
| `src/document_sanity/html_builder.py::CitationCollector` | First-appearance numbering. |
| `src/document_sanity/md2html.py::_cite` | Per-cite hyperlink emission. |
