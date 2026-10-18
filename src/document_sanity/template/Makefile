.PHONY: help install install-pinned update latex build pdf preview preview-check html word serve check site clean

VERSION ?=

help:
	@echo "Targets:"
	@echo "  install        Install the document-sanity release pinned in pyproject.toml"
	@echo "  install-pinned Install strictly from uv.lock; fail if it's stale (CI)"
	@echo "  update         Re-resolve document-sanity after moving its tag in pyproject.toml"
	@echo "  latex          Generate LaTeX artifacts in out/<version>/latex/ (no PDF compile)"
	@echo "  pdf            Build + compile to PDF (out/<version>/pdf/main.pdf)"
	@echo "  preview        Insert/refresh markdown-preview blocks in docs/"
	@echo "  preview-check  Fail if preview blocks are missing or stale (CI)"
	@echo "  html           Emit interactive HTML viewer (out/<version>/html/)"
	@echo "  word           Build a Word (.docx) document (out/<version>/word/main.docx)"
	@echo "  serve          Serve the HTML viewer on http://localhost:8000"
	@echo "  check          Build every target and check previews + references (before sharing)"
	@echo "  site           Every document's HTML, PDF and Word in site/ (what Pages publishes)"
	@echo "  clean          Remove out/ and site/"
	@echo ""
	@echo "Pass VERSION=<ver> to any target for a specific dated version; otherwise"
	@echo "document-sanity auto-detects the latest src/<ver>/ directory."

# document-sanity is pinned to a release tag in pyproject.toml. To upgrade,
# change the tag and run `make update` (or `uv lock && uv sync`).
install:
	uv sync

install-pinned:
	uv sync --locked

update:
	uv lock --upgrade-package document-sanity
	uv sync

latex:
	uv run document-sanity build $(if $(VERSION),--version $(VERSION))

# Deprecated alias for `latex`. Kept so existing scripts keep working.
build: latex

pdf:
	uv run document-sanity build --compile $(if $(VERSION),--version $(VERSION))

preview:
	uv run document-sanity preview $(if $(VERSION),--version $(VERSION))

preview-check:
	uv run document-sanity preview --check $(if $(VERSION),--version $(VERSION))

html: preview
	uv run document-sanity html $(if $(VERSION),--version $(VERSION))

word: preview
	uv run document-sanity word $(if $(VERSION),--version $(VERSION))
	uv run python scripts/finalize_word_layout.py $(if $(VERSION),--version "$(VERSION)")

serve: html
	@ver=$${VERSION:-$$(ls -1 out | grep -E '^[0-9]{8}' | sort -r | head -1)}; \
	if [ -z "$$ver" ]; then ver=$$(ls -1 out | head -1); fi; \
	echo "Serving out/$$ver/html/ at http://localhost:8000"; \
	python3 -m http.server --directory out/$$ver/html 8000

# Every document (or just VERSION): preview --check, PDF, references, HTML,
# Word + the layout pass. Exits non-zero on anything to fix.
check:
	uv run document-sanity check $(VERSION)

site:
	uv run document-sanity site

clean:
	rm -rf out/ site/
