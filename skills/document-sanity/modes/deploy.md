# deploy: GitHub Pages, or any static host

## First: say this, and wait for a yes

> A GitHub Pages site is **public**: anyone with the link can read it, even
> when the repository is private. Every document under `src/` gets published
> (old versions and drafts included, unless we name the ones to publish) as
> an HTML viewer, a PDF and a Word file, with every number's provenance
> (file paths and commands). OK to publish?

Don't go on without an explicit yes. If some documents shouldn't be public,
work out which ones with the user and name only those (below).

## Notices stop it

A document whose manifest sets `metadata.notice` (a CUI banner, a
distribution statement, "proprietary") is refused by both `pages init` and
the `site` build the workflow runs. Don't work around it. Show the user the
notice and either leave that document out, or, **only if the user explicitly
says to publish it anyway**, add `--allow-notice`. A notice added later stops
the next deploy rather than publishing.

## GitHub Pages

Once the user has said yes:

```bash
uv run document-sanity pages init --yes                      # every document
uv run document-sanity pages init --yes manuscript           # only these
uv run document-sanity pages init --yes --no-pdf             # HTML + Word only
```

`--yes` records that the owner agreed; without it the command asks (or, with
no terminal, refuses). It writes `.github/workflows/pages.yml`. On every
push to `main` it installs the pinned document-sanity (`uv sync --locked`),
runs `document-sanity site`, and deploys `site/`:

```
site/index.html                    one card per document: read online · PDF · Word
site/<doc>/index.html              the HTML viewer
site/<doc>/<doc>.pdf, <doc>.docx
```

**PDFs need TeX on the runner.** The workflow installs a TeX Live subset from
Ubuntu's packages (pdflatex, bibtex, latex-recommended + latex-extra), about
a minute or two per run. If a template uses a package outside it, the deploy
fails on a missing `.sty`. `--no-pdf` skips TeX and publishes HTML and Word
only. Mention the trade-off; let the user pick.

Then:

- Try it locally first: `uv run document-sanity site` builds exactly what the
  workflow uploads (`python3 -m http.server --directory site 8000` to look).
- Work through the `!` notes it printed (a missing `uv.lock`, a pin to a
  branch instead of a release tag).
- **Turning Pages on is a repository setting. Ask first.** Then either the
  user does it (Settings → Pages → Source: GitHub Actions), or with their OK:
  `gh api -X POST repos/OWNER/REPO/pages -f build_type=workflow` (`-X PUT` if
  Pages is already on with another source).
- **Pushing is the user's call too.** Commit the workflow and `uv.lock`, then
  ask before `git push`.

The site appears at `https://OWNER.github.io/REPO/`. Use `--branch` when the
deploy branch isn't `main`, and `--only-repo OWNER/NAME` to stop forks from
deploying.

## Any other static host

```bash
uv run document-sanity site [DOC…] [--no-pdf]       # → site/
```

Every link is relative, so `site/` works under any URL prefix. Upload it
(`aws s3 sync site/ s3://…`, `rclone`, Netlify drop, an intranet share). The
same public-by-default warning applies to anything reachable without a
login. Ask before uploading.
