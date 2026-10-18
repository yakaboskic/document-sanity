# Introduction <!-- \label{sec:introduction} -->

Welcome to the `document-sanity` starter template. This paragraph
demonstrates **bold**, *italic*, `inline code`, and inline math:
$E = mc^2$.

Variable substitution happens at build time — we have
{{NUM_SAMPLES:,}} samples in total, achieving an overall R<sup>2</sup>
of {{R2:.2f}} ($p = {{PVAL:.2e}}$). In the HTML viewer, clicking those
values pops up their provenance (source files, command, updated date)
because the manifest declares a `provenance:` block for them.

Cite with `\cite{key}` — the HTML viewer will number it and link to the
rendered `<li>` in the references section:
\cite{example_paper_2024}.

Cross-reference with `\ref{...}` — see Figure \ref{fig:example} for the
framework overview, and the method details in Section
\ref{sec:methods}.

## Background

Lists work as you'd expect:

- First bullet item.
- Second item with *formatted* text and a [link](https://example.com).
- Third item with a reference to \cite{another_paper_2023}.

## Numbered steps

1. Install `document-sanity` (see [README](../../../README.md)).
2. Edit this file or add new sections.
3. Run `make html` to preview, `make pdf` to export.
