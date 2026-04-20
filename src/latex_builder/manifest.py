#!/usr/bin/env python3
"""
Unified manifest parser for latex-builder.

The manifest.yaml is the single source of configuration for each version.
It contains metadata, section ordering, variables, figures, and tables --
all with optional provenance tracking.

Provenance format:
  Each variable, figure, or table can have a provenance block that records
  where the value/file came from and how it was generated.

Variable formats:
  # Simple (no provenance)
  MY_VAR: 42

  # Full (with provenance)
  MY_VAR:
    value: 42
    provenance:
      source: "data/results.csv"
      command: "python scripts/extract.py --metric accuracy"
      description: "Classification accuracy on held-out test set"
      updated: "2026-04-20"

Figure formats:
  my_figure:
    source: figures/plot.png
    width: "\\textwidth"
    provenance:
      data:
        - "data/validation_results.csv"
        - "data/trait_metadata.csv"
      command: "python scripts/plot_validation.py --output figures/plot.png"
      description: "Validation scatter plot"

Table formats:
  my_table:
    source: tables/results.md
    format: markdown  # or csv, latex
    provenance:
      data: ["data/raw_results.csv"]
      command: "python scripts/make_table.py"
      description: "Summary statistics table"
"""

import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class Provenance:
    """Provenance record for a variable, figure, or table."""
    source: Optional[str] = None           # Source file that produced this
    data: list[str] = field(default_factory=list)  # Input data files
    command: Optional[str] = None          # Command to regenerate
    description: Optional[str] = None      # Human description
    updated: Optional[str] = None          # When last updated

    @classmethod
    def from_dict(cls, d: dict) -> 'Provenance':
        data = d.get('data', [])
        if isinstance(data, str):
            data = [data]
        return cls(
            source=d.get('source'),
            data=data,
            command=d.get('command'),
            description=d.get('description'),
            updated=d.get('updated'),
        )


@dataclass
class VariableEntry:
    """A variable with optional provenance."""
    name: str
    value: Any                              # The actual value (or None for placeholder)
    provenance: Optional[Provenance] = None

    @property
    def is_placeholder(self) -> bool:
        return self.value is None


@dataclass
class FigureEntry:
    """A figure definition with optional provenance."""
    id: str
    source: Optional[str] = None
    width: str = "\\textwidth"
    caption_height: str = "2in"
    crop: bool = True
    provenance: Optional[Provenance] = None

    @property
    def is_placeholder(self) -> bool:
        return self.source is None


@dataclass
class TableEntry:
    """A table definition with optional provenance."""
    id: str
    source: Optional[str] = None
    format: str = "latex"                   # latex, markdown, csv
    provenance: Optional[Provenance] = None


@dataclass
class AuthorInfo:
    """Author metadata."""
    name: str
    email: Optional[str] = None
    affiliations: list[int] = field(default_factory=list)
    equal_contribution: bool = False


@dataclass
class Metadata:
    """Document metadata."""
    title: Optional[str] = None
    authors: list[AuthorInfo] = field(default_factory=list)
    affiliations: dict[int, dict] = field(default_factory=dict)
    abstract: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    template: str = "article"
    document_class: Optional[str] = None


class Manifest:
    """Parse and provide access to a version's manifest.yaml."""

    def __init__(self, manifest_path: Path):
        self.path = manifest_path
        self.raw: dict = {}
        self.metadata = Metadata()
        self.sections: list[str] = []
        self.variables: dict[str, VariableEntry] = {}
        self.figures: dict[str, FigureEntry] = {}
        self.tables: dict[str, TableEntry] = {}

        if manifest_path.exists():
            self._load()

    def _load(self) -> None:
        """Load and parse the manifest.yaml."""
        with open(self.path, 'r') as f:
            self.raw = yaml.safe_load(f) or {}

        self._parse_metadata()
        self._parse_sections()
        self._parse_variables()
        self._parse_figures()
        self._parse_tables()

    def _parse_metadata(self) -> None:
        raw = self.raw.get('metadata', {})
        if not raw:
            return

        authors = []
        for a in raw.get('authors', []):
            if isinstance(a, str):
                authors.append(AuthorInfo(name=a))
            elif isinstance(a, dict):
                authors.append(AuthorInfo(
                    name=a.get('name', ''),
                    email=a.get('email'),
                    affiliations=a.get('affiliations', []),
                    equal_contribution=a.get('equal_contribution', False),
                ))

        affiliations = {}
        for k, v in raw.get('affiliations', {}).items():
            affiliations[int(k)] = v if isinstance(v, dict) else {'name': str(v)}

        self.metadata = Metadata(
            title=raw.get('title'),
            authors=authors,
            affiliations=affiliations,
            abstract=raw.get('abstract'),
            keywords=raw.get('keywords', []),
            template=raw.get('template', 'article'),
            document_class=raw.get('document_class'),
        )

    def _parse_sections(self) -> None:
        self.sections = self.raw.get('sections', [])

    def _parse_variables(self) -> None:
        raw = self.raw.get('variables', {})
        for name, val in raw.items():
            if isinstance(val, dict) and 'value' in val:
                # Full form with provenance
                prov = None
                if 'provenance' in val:
                    prov = Provenance.from_dict(val['provenance'])
                self.variables[name] = VariableEntry(
                    name=name,
                    value=val['value'],
                    provenance=prov,
                )
            else:
                # Simple form: key: value
                self.variables[name] = VariableEntry(name=name, value=val)

    def _parse_figures(self) -> None:
        raw = self.raw.get('figures', {})
        for fig_id, spec in raw.items():
            if not isinstance(spec, dict):
                continue
            # Normalize figure IDs to strings (YAML may parse numeric keys as int)
            fig_id_str = str(fig_id)
            prov = None
            if 'provenance' in spec:
                prov = Provenance.from_dict(spec['provenance'])
            self.figures[fig_id_str] = FigureEntry(
                id=fig_id_str,
                source=spec.get('source'),
                width=spec.get('width', '\\textwidth'),
                caption_height=spec.get('caption_height', '2in'),
                crop=spec.get('crop', True),
                provenance=prov,
            )

    def _parse_tables(self) -> None:
        raw = self.raw.get('tables', {})
        for tbl_id, spec in raw.items():
            if not isinstance(spec, dict):
                continue
            prov = None
            if 'provenance' in spec:
                prov = Provenance.from_dict(spec['provenance'])
            self.tables[tbl_id] = TableEntry(
                id=tbl_id,
                source=spec.get('source'),
                format=spec.get('format', 'latex'),
                provenance=prov,
            )

    def get_variable_values(self) -> dict[str, Any]:
        """Get a flat dict of variable name -> value (for the variable processor)."""
        return {name: entry.value for name, entry in self.variables.items()}

    def get_template_name(self) -> str:
        return self.metadata.template

    def save(self, path: Optional[Path] = None) -> None:
        """Serialize manifest back to YAML."""
        path = path or self.path
        data = {}

        # Metadata
        meta = {}
        if self.metadata.title:
            meta['title'] = self.metadata.title
        if self.metadata.authors:
            meta['authors'] = []
            for a in self.metadata.authors:
                entry: dict[str, Any] = {'name': a.name}
                if a.email:
                    entry['email'] = a.email
                if a.affiliations:
                    entry['affiliations'] = a.affiliations
                if a.equal_contribution:
                    entry['equal_contribution'] = True
                meta['authors'].append(entry)
        if self.metadata.affiliations:
            meta['affiliations'] = self.metadata.affiliations
        if self.metadata.abstract:
            meta['abstract'] = self.metadata.abstract
        if self.metadata.keywords:
            meta['keywords'] = self.metadata.keywords
        if self.metadata.template != 'article':
            meta['template'] = self.metadata.template
        if self.metadata.document_class:
            meta['document_class'] = self.metadata.document_class
        if meta:
            data['metadata'] = meta

        # Sections
        if self.sections:
            data['sections'] = self.sections

        # Variables
        if self.variables:
            vars_out: dict[str, Any] = {}
            for name, entry in self.variables.items():
                if entry.provenance:
                    v: dict[str, Any] = {'value': entry.value}
                    prov: dict[str, Any] = {}
                    if entry.provenance.source:
                        prov['source'] = entry.provenance.source
                    if entry.provenance.data:
                        prov['data'] = entry.provenance.data
                    if entry.provenance.command:
                        prov['command'] = entry.provenance.command
                    if entry.provenance.description:
                        prov['description'] = entry.provenance.description
                    if entry.provenance.updated:
                        prov['updated'] = entry.provenance.updated
                    v['provenance'] = prov
                    vars_out[name] = v
                else:
                    vars_out[name] = entry.value
            data['variables'] = vars_out

        # Figures
        if self.figures:
            figs_out: dict[str, Any] = {}
            for fig_id, entry in self.figures.items():
                spec: dict[str, Any] = {}
                if entry.source:
                    spec['source'] = entry.source
                else:
                    spec['source'] = None
                if entry.width != '\\textwidth':
                    spec['width'] = entry.width
                if entry.caption_height != '2in':
                    spec['caption_height'] = entry.caption_height
                if entry.provenance:
                    prov_d: dict[str, Any] = {}
                    if entry.provenance.data:
                        prov_d['data'] = entry.provenance.data
                    if entry.provenance.command:
                        prov_d['command'] = entry.provenance.command
                    if entry.provenance.description:
                        prov_d['description'] = entry.provenance.description
                    spec['provenance'] = prov_d
                figs_out[fig_id] = spec
            data['figures'] = figs_out

        # Tables
        if self.tables:
            tbls_out: dict[str, Any] = {}
            for tbl_id, entry in self.tables.items():
                spec_t: dict[str, Any] = {}
                if entry.source:
                    spec_t['source'] = entry.source
                if entry.format != 'latex':
                    spec_t['format'] = entry.format
                if entry.provenance:
                    prov_t: dict[str, Any] = {}
                    if entry.provenance.data:
                        prov_t['data'] = entry.provenance.data
                    if entry.provenance.command:
                        prov_t['command'] = entry.provenance.command
                    if entry.provenance.description:
                        prov_t['description'] = entry.provenance.description
                    spec_t['provenance'] = prov_t
                tbls_out[tbl_id] = spec_t
            data['tables'] = tbls_out

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
