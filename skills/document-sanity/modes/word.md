# word: the .docx template, styles, and the layout pass

`document-sanity word` renders the same markdown into a Word document. The
template contributes headers, footers, theme, page layout and named styles;
`docs/*.md` contribute the body.

```bash
make word VERSION=<doc>      # → out/<doc>/word/main.docx
```

Every Word build (`word`, so `make word`, `check` and `site` too) ends with
a layout pass: table rows kept together with a repeating header, headings
kept with the next paragraph, figures kept with their captions, and
equations sized to the surrounding text. `--no-layout` skips it. Don't
hand-edit the .docx to fix pagination; rebuild.

A project made from an older template may still have
`scripts/finalize_word_layout.py`, run by its `make word`. The build does
that pass itself now, so the script changes nothing: with the user's OK,
delete it and its line in the Makefile's `word` target.

## Which template

In order:

1. `--template path.docx` on the command line;
2. `templates/<name>.docx`, where `<name>` is `metadata.word_template`
   (falling back to `metadata.template`);
3. the only `.docx` in `templates/`, if there's exactly one.

Only the template's section properties (headers, footers, margins, theme)
survive; its body is replaced. A template should be a shell.

The starter's `templates/article.docx` has a header logo
(`templates/logo.png`), "page X of N", a footer line and a diagonal DRAFT
watermark (`templates/watermark.png`). Swap either PNG in place: the .docx
points at them. A watermark's colour and transparency must be baked into the
image. Don't build a VML text watermark (it hangs Word's watermark dialog).

## Styles: the round trip

Styles (colours, fonts, sizes, spacing for Title, Heading 1–3, body, caption,
code) come from the template's `styles.xml` and theme, unless the manifest
names a styles file:

```yaml
metadata:
  word_template: article      # → templates/article.docx
  word_styles: article        # → styles/article.yaml (wins over the template's)
```

Every Word build writes what it used to `out/<doc>/word/styles.yaml`. To
change the look:

```bash
make word VERSION=<doc>
cp out/<doc>/word/styles.yaml styles/<name>.yaml     # then edit it
# point metadata.word_styles at <name>, rebuild
```

`styles/` and `templates/` are shared by every document. Ask before changing
the ones another document uses; make a new `<name>` instead.

## Adopting someone else's look

The user has a `.docx` whose design they want (an agency template, a
co-author's draft):

```bash
uv run document-sanity word --extract-styles --template inputs/agency.docx \
  --output styles/agency.yaml
```

Then `word_styles: agency`. For their headers, footers and page layout too,
copy the file to `templates/agency.docx` (emptied of body text, with the
user's OK) and set `word_template: agency`.

## HTML styles

`metadata.html_styles: <name>` loads `styles/<name>.css` after the viewer's
own styles, for the HTML side of the same design.

## What Word can't do

- Figures embed as PNG/JPG (no PDF or SVG): give every figure a raster
  sibling (`figures` mode).
- A ```latex block renders from its **preview block**: the figure, pipe
  table or `$$…$$` that `preview` wrote under it. No preview, no figure in
  Word. Previews flatten what markdown can't hold (merged header cells,
  subfigure panels), so prefer markdown or `{{tab:…}}` tables when Word
  matters.
- Math in `$…$` and `$$…$$` becomes native Word equations. Template macros
  with arguments don't expand.
- Variables substitute, but Word has no provenance panel.
