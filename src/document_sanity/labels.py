#!/usr/bin/env python3
"""
Cross-reference labels shared by the HTML and Word builders.

LaTeX numbers figures, tables and equations itself; the other targets need the
same numbers so that \\ref{fig:x} reads "Figure 3" everywhere. collect_labels
walks the version's sections in manifest order and numbers each \\label{key}
by its prefix (fig, tab, eq, ...), which matches LaTeX as long as each float
carries one label.
"""

from __future__ import annotations

import re
from pathlib import Path

LABEL_RE = re.compile(r'\\label\{([^{}]+)\}')

# Prefix → display name for cross-references. "fig:xyz" → "Figure 3".
LABEL_KIND_NAMES = {
    'fig': 'Figure',
    'tab': 'Table',
    'eq': 'Eq.',
    'sec': 'Section',
    'eqn': 'Eq.',
    'app': 'Appendix',
    'alg': 'Algorithm',
}


def collect_labels(manifest, src_dir: Path) -> dict[str, tuple[str, int]]:
    """Walk every section doc, find \\label{key}s in document order, and
    assign numbers by kind (fig/tab/eq/...). Returns {key: (kind_name, number)}."""
    counters: dict[str, int] = {}
    labels: dict[str, tuple[str, int]] = {}
    pseudo = {'_bibliography', '_toc'}
    for section_ref in manifest.sections:
        if section_ref in pseudo:
            continue
        doc_path = src_dir / section_ref
        if not doc_path.exists():
            continue
        content = doc_path.read_text(encoding='utf-8')
        for m in LABEL_RE.finditer(content):
            key = m.group(1)
            if key in labels:
                continue  # duplicate label, keep first
            prefix = key.split(':', 1)[0] if ':' in key else 'sec'
            kind = LABEL_KIND_NAMES.get(prefix, 'Section')
            counters[prefix] = counters.get(prefix, 0) + 1
            labels[key] = (kind, counters[prefix])
    return labels
