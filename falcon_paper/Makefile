.PHONY: help install install-pinned update build pdf preview preview-check html serve clean

VERSION ?=

help:
	@echo "Targets:"
	@echo "  install        Pull the latest latex-builder from GitHub main and sync"
	@echo "                 the venv. Use this by default — latex-builder changes often."
	@echo "  install-pinned Install strictly from uv.lock (no upgrade). Reproducible / CI."
	@echo "  update         Alias for 'install' — re-resolve latex-builder to GitHub HEAD."
	@echo "  build          Generate LaTeX artifacts in out/<version>/latex/"
	@echo "  pdf            Build + compile to PDF (out/<version>/pdf/main.pdf)"
	@echo "  preview        Insert/refresh markdown-preview blocks in docs/"
	@echo "  preview-check  Fail if preview blocks are missing or stale (CI)"
	@echo "  html           Emit interactive HTML viewer (out/<version>/html/)"
	@echo "  serve          Serve the HTML viewer on http://localhost:8000"
	@echo "  clean          Remove out/"
	@echo ""
	@echo "Pass VERSION=<ver> to any target for a specific dated version; otherwise"
	@echo "latex-builder auto-detects the latest src/<ver>/ directory."

# Default install = always pull latest main. `uv sync` alone respects uv.lock,
# which pins latex-builder to a specific commit and silently skips git updates;
# `uv lock --upgrade-package` re-resolves the git dep to the current HEAD.
install: update
update:
	uv lock --upgrade-package latex-builder
	uv sync

install-pinned:
	uv sync

build:
	uv run latex-builder build $(if $(VERSION),--version $(VERSION))

pdf:
	uv run latex-builder build --compile $(if $(VERSION),--version $(VERSION))

preview:
	uv run latex-builder preview $(if $(VERSION),--version $(VERSION))

preview-check:
	uv run latex-builder preview --check $(if $(VERSION),--version $(VERSION))

html:
	uv run latex-builder html $(if $(VERSION),--version $(VERSION))

serve: html
	@ver=$${VERSION:-$$(ls -1 out | grep -E '^[0-9]{8}' | sort -r | head -1)}; \
	echo "Serving out/$$ver/html/ at http://localhost:8000"; \
	python3 -m http.server --directory out/$$ver/html 8000

clean:
	rm -rf out/
