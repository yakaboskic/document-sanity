"""`document-sanity check`: build every target, the way you'd share them.

For each document under `src/` it runs, in order:

- **preview**: `preview --check` — every ```latex block's preview is current
  (GitHub, the HTML viewer and Word all read them);
- **pdf**: the LaTeX build, compiled with pdflatex (skipped with a warning
  when no TeX is installed, or with `--no-pdf`). `! …` lines in the log are
  errors;
- **refs**: every `{{VARIABLE}}` is defined, every `\\cite{key}` is in
  `references.bib` and every `\\ref{label}` has a `\\label`;
- **html**: the interactive viewer;
- **word**: the .docx, plus the project's Word layout pass
  (`scripts/finalize_word_layout.py`, as `make word` runs it) when there is one.

The builders' own chatter is captured and shown only for a failing step (or
with `--verbose`). `build_document` is also what `document-sanity site` uses.
"""

from __future__ import annotations

import contextlib
import io
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

WORD_LAYOUT_PASS = "scripts/finalize_word_layout.py"
STEPS = ("preview", "pdf", "refs", "html", "word")
BUILD_STEPS = ("pdf", "html", "word")

_CITE = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}")
_REF = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref|pageref|nameref)\{([^}]*)\}")


@dataclass
class Step:
    name: str
    status: str  # "ok" | "error" | "warn" | "skip"
    detail: str = ""
    notes: list[str] = field(default_factory=list)
    output: Path | None = None


@dataclass
class DocResult:
    doc: str
    steps: list[Step] = field(default_factory=list)

    def step(self, name: str) -> Step | None:
        return next((s for s in self.steps if s.name == name), None)

    @property
    def errors(self) -> list[Step]:
        return [s for s in self.steps if s.status == "error"]

    @property
    def warnings(self) -> list[Step]:
        return [s for s in self.steps if s.status == "warn"]


def _run(fn: Callable[[], object], verbose: bool) -> tuple[object, str, BaseException | None]:
    """Call `fn` with its stdout/stderr captured (unless verbose)."""
    if verbose:
        try:
            return fn(), "", None
        except Exception as e:  # noqa: BLE001 — reported as a failed step
            return None, "", e
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            return fn(), buf.getvalue(), None
        except Exception as e:  # noqa: BLE001
            return None, buf.getvalue(), e


def _tail(text: str, n: int = 12) -> list[str]:
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    return lines[-n:]


def _rel(root: Path, path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


# ── static references ────────────────────────────────────────────────────────

def _blank(text: str) -> str:
    """Comments, inline code and non-LaTeX fences replaced by spaces (lines kept)."""
    def spaces(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    text = re.sub(r"<!--.*?-->", spaces, text, flags=re.S)
    text = re.sub(
        r"^(\s*)(`{3,}|~{3,})(?!\s*latex\b).*?^\1\2", spaces, text, flags=re.S | re.M
    )
    return re.sub(r"(?<!`)`[^`\n]+`(?!`)", spaces, text)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def reference_findings(root: Path, doc: str, manifest) -> list[str]:
    """Unknown citation keys and \\ref labels, as `path:line  message`."""
    from .bib import load_bib
    from .labels import collect_labels

    src_dir = root / "src" / doc
    bib = load_bib(root, doc)
    labels = collect_labels(manifest, src_dir)
    sources: list[tuple[str, str]] = []
    for section in manifest.sections:
        path = src_dir / section
        if section.startswith("_"):
            continue
        if not path.is_file():
            sources.append((f"src/{doc}/manifest.yaml", f"\\missing{{{section}}}"))
            continue
        sources.append((_rel(root, path), path.read_text(encoding="utf-8")))
    if manifest.metadata.abstract:
        sources.append((f"src/{doc}/manifest.yaml (abstract)", manifest.metadata.abstract))

    findings: list[str] = []
    for where, raw in sources:
        if raw.startswith("\\missing{"):
            findings.append(f"{where}  section {raw[9:-1]} is listed but doesn't exist")
            continue
        text = _blank(raw)
        for m in _CITE.finditer(text):
            for key in (k.strip() for k in m.group(1).split(",")):
                if key and key != "*" and key not in bib:
                    hint = " (no references.bib)" if not bib else ""
                    findings.append(f"{where}:{_line(text, m.start())}  \\cite{{{key}}}: not in references.bib{hint}")
        for m in _REF.finditer(text):
            for key in (k.strip() for k in m.group(1).split(",")):
                if key and key not in labels:
                    findings.append(f"{where}:{_line(text, m.start())}  \\ref{{{key}}}: no \\label{{{key}}}")
    return findings


def undefined_variable_findings(root: Path, undefined) -> list[str]:
    """`path:line  {{NAME}}: …` for each undefined variable, lines in the markdown.

    The processor sees the converted LaTeX, so its line numbers aren't the
    source's; look the token up in the source file instead.
    """
    findings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for uv in undefined:
        if (uv.name, uv.file_path) in seen:
            continue
        seen.add((uv.name, uv.file_path))
        message = f"{{{{{uv.name}}}}}: not defined under `variables:`"
        path = Path(uv.file_path)
        lines = []
        if path.is_file():
            token = re.compile(r"\{\{\s*" + re.escape(uv.name) + r"\s*(?::[^}]*)?\}\}")
            text = _blank(path.read_text(encoding="utf-8"))
            lines = [_line(text, m.start()) for m in token.finditer(text)]
        where = _rel(root, path) if path.is_file() else uv.file_path
        for line in lines or [None]:
            findings.append(f"{where}{f':{line}' if line else ''}  {message}")
    return findings


def _latex_errors(log: Path) -> list[str]:
    """`! …` error lines from a pdflatex log, with the `l.N` context line."""
    if not log.is_file():
        return []
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    found = []
    for i, line in enumerate(lines):
        if line.startswith("! "):
            context = next((ln.strip() for ln in lines[i + 1:i + 8] if ln.startswith("l.")), "")
            found.append(f"{line[2:].strip()}" + (f"  ({context})" if context else ""))
    return found


# ── one document, every target ───────────────────────────────────────────────

def build_document(
    root: Path,
    doc: str,
    *,
    pdf: bool = True,
    require_tex: bool = False,
    compiler: str = "pdflatex",
    preview: bool = True,
    verbose: bool = False,
) -> DocResult:
    """Run every step for `root/src/<doc>`; outputs land in `out/<doc>/`.

    `require_tex` turns "no TeX installed" from a skipped PDF into an error
    (what a deploy wants).
    """
    from .build import ManuscriptBuilder

    result = DocResult(doc)
    out = root / "out" / doc

    if preview:
        from .preview import run as preview_run

        code, text, exc = _run(lambda: preview_run(root, doc, check=True), verbose)
        if exc is not None:
            result.steps.append(Step("preview", "error", f"{type(exc).__name__}: {exc}", _tail(text)))
        elif code:
            drift = [ln.strip() for ln in text.splitlines() if ln.startswith("  src/")]
            result.steps.append(Step(
                "preview", "error",
                f"stale preview blocks — run `document-sanity preview -V {doc}`",
                drift or _tail(text),
            ))
        else:
            result.steps.append(Step("preview", "ok", "every preview block is current"))

    # LaTeX (always: it is cheap and catches conversion errors), then the PDF.
    builder_box: list[ManuscriptBuilder] = []

    def latex() -> bool:
        builder = ManuscriptBuilder(root_dir=root, version=doc, compiler=compiler)
        builder_box.append(builder)
        return builder.build()

    ok, text, exc = _run(latex, verbose)
    if exc is not None or not ok or not builder_box:
        why = f"{type(exc).__name__}: {exc}" if exc else "the LaTeX build failed"
        result.steps.append(Step("pdf", "error", why, _tail(text)))
        for name in ("refs", "html", "word"):
            result.steps.append(Step(name, "skip", "skipped: the LaTeX build failed"))
        return result
    builder = builder_box[0]

    if not pdf:
        result.steps.append(Step("pdf", "skip", "skipped (--no-pdf); LaTeX tree built", output=out / "latex" / "main.tex"))
    elif shutil.which(compiler) is None:
        status = "error" if require_tex else "warn"
        result.steps.append(Step(
            "pdf", status,
            f"{compiler} not found — install TeX (MacTeX / TeX Live), or pass --no-pdf",
            output=out / "latex" / "main.tex",
        ))
    else:
        compiled, text, exc = _run(builder.compile_to_pdf, verbose)
        errors = _latex_errors(out / "latex" / "main.log")
        target = out / "pdf" / "main.pdf"
        if exc is not None or not compiled:
            why = f"{type(exc).__name__}: {exc}" if exc else f"{compiler} produced no PDF"
            result.steps.append(Step("pdf", "error", why, errors or _tail(text), output=out / "latex" / "main.log"))
        elif errors:
            result.steps.append(Step(
                "pdf", "error", f"{len(errors)} LaTeX error(s) — see {_rel(root, out / 'latex' / 'main.log')}",
                errors[:10], output=target,
            ))
        else:
            result.steps.append(Step("pdf", "ok", _rel(root, target), output=target))

    findings = undefined_variable_findings(root, builder.processor.undefined_vars)
    findings += reference_findings(root, doc, builder.manifest)
    if findings:
        result.steps.append(Step("refs", "error", f"{len(findings)} unresolved reference(s)", findings))
    else:
        result.steps.append(Step("refs", "ok", "every variable, citation and \\ref resolves"))

    from .html_builder import build_html

    ok, text, exc = _run(lambda: build_html(root_dir=root, version=doc), verbose)
    index = out / "html" / "index.html"
    if exc is not None or not ok:
        why = f"{type(exc).__name__}: {exc}" if exc else "the HTML build failed"
        result.steps.append(Step("html", "error", why, _tail(text)))
    else:
        result.steps.append(Step("html", "ok", _rel(root, index), output=index))

    from .docx_builder import WordBuilder

    word = WordBuilder(root_dir=root, version=doc)
    try:
        word._resolve_template()  # noqa: SLF001 — same rules the build uses
    except FileNotFoundError:
        result.steps.append(Step(
            "word", "warn",
            "skipped: no Word template (templates/<name>.docx, see metadata.word_template)",
        ))
        return result
    ok, text, exc = _run(word.build, verbose)
    docx = out / "word" / "main.docx"
    if exc is not None or not ok:
        why = f"{type(exc).__name__}: {exc}" if exc else "the Word build failed"
        result.steps.append(Step("word", "error", why, _tail(text)))
        return result
    layout = root / WORD_LAYOUT_PASS
    if layout.is_file():
        proc = subprocess.run(
            [sys.executable, str(layout), "--root", str(root), "--version", doc],
            capture_output=True, text=True, cwd=root,
        )
        if verbose:
            print(proc.stdout, end="")
        if proc.returncode != 0:
            result.steps.append(Step(
                "word", "error", f"{WORD_LAYOUT_PASS} failed (exit {proc.returncode})",
                _tail(proc.stdout + proc.stderr), output=docx,
            ))
            return result
        result.steps.append(Step("word", "ok", f"{_rel(root, docx)} (+ {WORD_LAYOUT_PASS})", output=docx))
    else:
        result.steps.append(Step("word", "ok", _rel(root, docx), output=docx))
    return result
