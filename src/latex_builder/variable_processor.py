#!/usr/bin/env python3
"""
Variable replacement engine for LaTeX templates.

Supports Python-style formatting:
  {{variable}}          -> Simple replacement
  {{variable:.2f}}      -> 2 decimal places
  {{variable:.3e}}      -> Scientific notation
  {{variable:,}}        -> Thousands separator
  {{variable:.1%}}      -> Percentage

Also handles figure references:
  {{fig:figure_id}}     -> \\includegraphics command
"""

import re
import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class UndefinedVariable:
    """Track an undefined variable usage."""
    name: str
    format_spec: Optional[str]
    file_path: str
    line_number: int
    line_content: str


class VariableProcessor:
    """Process LaTeX templates with variable replacement."""

    def __init__(
        self,
        placeholder: str = "XXXX",
        figure_manifest: Optional[Any] = None,
        output_dir: Optional[Path] = None,
        crop_script: Optional[Path] = None,
        figures: Optional[dict] = None,
        figures_dir: Optional[Path] = None,
    ):
        self.variables: dict[str, Any] = {}
        self.placeholder = placeholder
        self.undefined_vars: list[UndefinedVariable] = []
        self.used_vars: set[str] = set()

        # Figure processing (FigureManifest-based)
        self.figure_manifest = figure_manifest
        self.output_dir = output_dir
        self.crop_script = crop_script

        # Figure processing (manifest.yaml-based)
        # figures: dict mapping figure_id -> FigureEntry (from manifest)
        self.figures = figures or {}
        self.figures_dir = figures_dir

    def load_variables(self, json_path: Path) -> int:
        """Load variables from a JSON file. Returns count of variables loaded."""
        if not json_path.exists():
            return 0
        with open(json_path, 'r') as f:
            data = json.load(f)
        self.variables.update(data)
        return len(data)

    def format_value(self, value: Any, format_spec: Optional[str]) -> str:
        """Format a value using Python format specification."""
        if format_spec is None or format_spec == '':
            return str(value) if not isinstance(value, str) else value

        try:
            if isinstance(value, str) and ',' in value:
                if format_spec.strip() == ',':
                    return value
                try:
                    clean = value.replace(',', '')
                    numeric = float(clean) if '.' in clean else int(clean)
                    return format(numeric, format_spec)
                except ValueError:
                    return value
            return format(value, format_spec)
        except (ValueError, TypeError):
            return str(value)

    def replace_variables(self, content: str, file_path: Optional[str] = None) -> str:
        """Replace all {{variable}}, {{variable:format}}, {{fig:name}}, and {{canva:N}} in content."""
        var_pattern = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]+))?\}\}'
        fig_pattern = r'\{\{fig:([a-zA-Z_][a-zA-Z0-9_]*)\}\}'
        canva_pattern = r'\{\{canva:(\d+)\}\}'

        lines = content.split('\n')
        result_lines = []

        for line_num, line in enumerate(lines, start=1):
            # Replace figures first (both {{fig:name}} and {{canva:N}} syntax)
            def _resolve_figure(figure_id: str) -> str:
                """Resolve a figure ID to an \\includegraphics command."""
                # Try FigureManifest first (JSON-based)
                if self.figure_manifest and self.output_dir:
                    return self.figure_manifest.generate_includegraphics(
                        figure_id, self.output_dir, self.crop_script
                    )
                # Try manifest.yaml figures
                if figure_id in self.figures:
                    fig_entry = self.figures[figure_id]
                    width = getattr(fig_entry, 'width', '\\textwidth')
                    source = getattr(fig_entry, 'source', None)
                    if source:
                        return f"\\includegraphics[width={width}]{{{source}}}"
                    return f"% FIGURE PLACEHOLDER: {figure_id} (no source)"
                return f"\\includegraphics[width=\\textwidth]{{FIGURE:{figure_id}}}"

            def replace_figure(match: re.Match) -> str:
                return _resolve_figure(match.group(1))

            def replace_canva(match: re.Match) -> str:
                return _resolve_figure(match.group(1))

            line = re.sub(fig_pattern, replace_figure, line)
            line = re.sub(canva_pattern, replace_canva, line)

            # Then replace variables
            def replace_var(match: re.Match) -> str:
                var_name = match.group(1)
                format_spec = match.group(2)
                self.used_vars.add(var_name)

                if var_name in self.variables:
                    value = self.variables[var_name]
                    if value is None:
                        self.undefined_vars.append(UndefinedVariable(
                            name=var_name, format_spec=format_spec,
                            file_path=file_path or "<unknown>",
                            line_number=line_num, line_content=line.strip(),
                        ))
                        return self.placeholder
                    return self.format_value(value, format_spec)
                else:
                    self.undefined_vars.append(UndefinedVariable(
                        name=var_name, format_spec=format_spec,
                        file_path=file_path or "<unknown>",
                        line_number=line_num, line_content=line.strip(),
                    ))
                    return self.placeholder

            result_line = re.sub(var_pattern, replace_var, line)
            result_lines.append(result_line)

        return '\n'.join(result_lines)

    def process_file(self, input_path: Path, output_path: Path) -> None:
        """Process a template file and write the result."""
        content = input_path.read_text(encoding='utf-8')
        processed = self.replace_variables(content, str(input_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(processed, encoding='utf-8')

    def get_unused_variables(self) -> list[str]:
        """Get list of variables defined but never used."""
        return sorted(set(self.variables.keys()) - self.used_vars)

    def has_undefined_variables(self) -> bool:
        """Check if any undefined variables were encountered."""
        return len(self.undefined_vars) > 0

    def print_report(self, verbose: bool = False) -> None:
        """Print a summary report of variable usage."""
        print(f"\n  Variable Report")
        print(f"  {'='*50}")
        print(f"    Defined:   {len(self.variables)}")
        print(f"    Used:      {len(self.used_vars)}")
        print(f"    Undefined: {len(self.undefined_vars)}")

        if self.undefined_vars:
            print(f"\n    WARNING: Undefined variables ({len(self.undefined_vars)}):")
            print(f"    These will be replaced with '{self.placeholder}'")

            by_name: dict[str, list[UndefinedVariable]] = {}
            for uv in self.undefined_vars:
                by_name.setdefault(uv.name, []).append(uv)

            for var_name, usages in sorted(by_name.items()):
                fmts = [u.format_spec for u in usages if u.format_spec]
                fmt_str = f":{fmts[0]}" if fmts else ""
                print(f"      - {var_name}{fmt_str}")
                for usage in usages[:3]:
                    rel_path = Path(usage.file_path).name
                    print(f"          {rel_path}:{usage.line_number}")
                if len(usages) > 3:
                    print(f"          ... and {len(usages) - 3} more")

        if verbose:
            unused = self.get_unused_variables()
            if unused:
                print(f"\n    INFO: Unused variables ({len(unused)}):")
                for var in unused[:10]:
                    print(f"      - {var}")
                if len(unused) > 10:
                    print(f"      ... and {len(unused) - 10} more")
