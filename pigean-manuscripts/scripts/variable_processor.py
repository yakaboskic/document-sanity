#!/usr/bin/env python3
"""
Variable replacement engine for LaTeX templates.

Supports Python-style formatting:
  {{variable}}          -> Simple replacement
  {{variable:.2f}}      -> 2 decimal places
  {{variable:.3e}}      -> Scientific notation
  {{variable:,}}        -> Thousands separator
  {{variable:.1%}}      -> Percentage
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

# Import figure manifest processor
try:
    from figure_manifest import FigureManifest
except ImportError:
    FigureManifest = None


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
        figure_manifest: Optional['FigureManifest'] = None,
        output_dir: Optional[Path] = None,
        crop_script: Optional[Path] = None
    ):
        self.variables: Dict[str, Any] = {}
        self.placeholder = placeholder
        self.undefined_vars: List[UndefinedVariable] = []
        self.used_vars: set = set()

        # Figure processing
        self.figure_manifest = figure_manifest
        self.output_dir = output_dir
        self.crop_script = crop_script

    def load_variables(self, json_path: Path) -> int:
        """Load variables from a JSON file."""
        if not json_path.exists():
            return 0

        with open(json_path, 'r') as f:
            data = json.load(f)

        self.variables.update(data)
        return len(data)

    def format_value(self, value: Any, format_spec: Optional[str]) -> str:
        """Format a value using Python format specification."""
        if format_spec is None or format_spec == '':
            # No format specified, return as string
            if isinstance(value, str):
                return value
            else:
                return str(value)

        try:
            # Handle special case: if value is already a formatted string with commas
            # and format_spec is just for display, keep it as is
            if isinstance(value, str) and ',' in value:
                # If asking for comma formatting, already have it
                if format_spec.strip() == ',':
                    return value
                # Otherwise try to parse and reformat
                try:
                    # Remove commas and try to parse as number
                    clean_value = value.replace(',', '')
                    if '.' in clean_value:
                        numeric_value = float(clean_value)
                    else:
                        numeric_value = int(clean_value)
                    return format(numeric_value, format_spec)
                except ValueError:
                    # Can't parse, return as is
                    return value

            # Standard formatting
            return format(value, format_spec)
        except (ValueError, TypeError) as e:
            # If formatting fails, return value as string
            return str(value)

    def replace_variables(
        self,
        content: str,
        file_path: Optional[str] = None
    ) -> str:
        """
        Replace all {{variable}}, {{variable:format}}, {{fig:name}}, and {{canva:page}} in content.

        Args:
            content: Template content with {{...}} placeholders
            file_path: Optional file path for error reporting

        Returns:
            Content with variables, figures, and Canva pages replaced
        """
        # Pattern to match {{variable}} or {{variable:format}}
        var_pattern = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]+))?\}\}'

        # Pattern to match {{fig:figure_id}}
        fig_pattern = r'\{\{fig:([a-zA-Z_][a-zA-Z0-9_]*)\}\}'

        # Pattern to match {{canva:page_num}}
        canva_pattern = r'\{\{canva:(\d+)\}\}'

        lines = content.split('\n')
        result_lines = []

        for line_num, line in enumerate(lines, start=1):
            # First replace Canva pages
            def replace_canva(match: re.Match) -> str:
                page_num = match.group(1)

                if self.figure_manifest and self.output_dir:
                    return self.figure_manifest.generate_canva_includegraphics(
                        page_num,
                        self.output_dir,
                        self.crop_script
                    )
                else:
                    # No manifest, return placeholder
                    return f"\\includegraphics[width=\\textwidth]{{CANVA:PAGE-{page_num}}}"

            line = re.sub(canva_pattern, replace_canva, line)

            # Then replace figures
            def replace_figure(match: re.Match) -> str:
                figure_id = match.group(1)

                if self.figure_manifest and self.output_dir:
                    return self.figure_manifest.generate_includegraphics(
                        figure_id,
                        self.output_dir,
                        self.crop_script
                    )
                else:
                    # No manifest, return placeholder
                    return f"\\includegraphics[width=\\textwidth]{{FIGURE:{figure_id}}}"

            line = re.sub(fig_pattern, replace_figure, line)

            # Then replace variables
            def replace_var(match: re.Match) -> str:
                var_name = match.group(1)
                format_spec = match.group(2)  # May be None

                # Track usage
                self.used_vars.add(var_name)

                # Check if variable is defined and not null
                if var_name in self.variables:
                    value = self.variables[var_name]
                    # Treat null values as undefined (render as placeholder)
                    if value is None:
                        self.undefined_vars.append(UndefinedVariable(
                            name=var_name,
                            format_spec=format_spec,
                            file_path=file_path or "<unknown>",
                            line_number=line_num,
                            line_content=line.strip()
                        ))
                        return self.placeholder
                    return self.format_value(value, format_spec)
                else:
                    # Track undefined variable
                    self.undefined_vars.append(UndefinedVariable(
                        name=var_name,
                        format_spec=format_spec,
                        file_path=file_path or "<unknown>",
                        line_number=line_num,
                        line_content=line.strip()
                    ))
                    return self.placeholder

            result_line = re.sub(var_pattern, replace_var, line)
            result_lines.append(result_line)

        return '\n'.join(result_lines)

    def process_file(self, input_path: Path, output_path: Path) -> None:
        """
        Process a template file and write the result.

        Args:
            input_path: Path to template file
            output_path: Path to write processed file
        """
        # Read template
        with open(input_path, 'r') as f:
            content = f.read()

        # Replace variables
        processed = self.replace_variables(content, str(input_path))

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write output
        with open(output_path, 'w') as f:
            f.write(processed)

    def get_unused_variables(self) -> List[str]:
        """Get list of variables defined but never used."""
        defined = set(self.variables.keys())
        unused = defined - self.used_vars
        return sorted(unused)

    def get_undefined_variables(self) -> List[UndefinedVariable]:
        """Get list of undefined variables that were encountered."""
        return self.undefined_vars

    def has_undefined_variables(self) -> bool:
        """Check if any undefined variables were encountered."""
        return len(self.undefined_vars) > 0

    def print_report(self, verbose: bool = False) -> None:
        """Print a summary report of variable usage."""
        print(f"\n📊 Variable Report")
        print(f"{'='*60}")
        print(f"  Defined:   {len(self.variables)}")
        print(f"  Used:      {len(self.used_vars)}")
        print(f"  Undefined: {len(self.undefined_vars)}")

        if self.undefined_vars:
            print(f"\n⚠️  WARNING: Undefined variables found ({len(self.undefined_vars)}):")
            print(f"  These will be replaced with '{self.placeholder}'")
            print()

            # Group by variable name
            by_name: Dict[str, List[UndefinedVariable]] = {}
            for uv in self.undefined_vars:
                if uv.name not in by_name:
                    by_name[uv.name] = []
                by_name[uv.name].append(uv)

            for var_name, usages in sorted(by_name.items()):
                format_specs = [u.format_spec for u in usages if u.format_spec]
                format_str = f":{format_specs[0]}" if format_specs else ""
                print(f"  • {var_name}{format_str}")
                for usage in usages[:3]:  # Show first 3 usages
                    rel_path = Path(usage.file_path).name
                    print(f"      {rel_path}:{usage.line_number}")
                if len(usages) > 3:
                    print(f"      ... and {len(usages) - 3} more")

        if verbose:
            unused = self.get_unused_variables()
            if unused:
                print(f"\n💡 INFO: Unused variables in JSON ({len(unused)}):")
                for var in unused[:10]:
                    print(f"  • {var}")
                if len(unused) > 10:
                    print(f"  ... and {len(unused) - 10} more")


def test_formatting():
    """Test the formatting functionality."""
    processor = VariableProcessor()
    processor.variables = {
        'NUMBER': 1234.5678,
        'PVALUE': 1.23e-10,
        'FORMATTED_NUM': '1,234',
    }

    tests = [
        ('{{NUMBER}}', '1234.5678'),
        ('{{NUMBER:.2f}}', '1234.57'),
        ('{{NUMBER:,.2f}}', '1,234.57'),
        ('{{PVALUE:.2e}}', '1.23e-10'),
        ('{{FORMATTED_NUM}}', '1,234'),
        ('{{UNDEFINED}}', 'XXXX'),
    ]

    print("Testing formatting:")
    for template, expected in tests:
        result = processor.replace_variables(template)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {template:30} -> {result:20} (expected: {expected})")


if __name__ == '__main__':
    # Run tests
    test_formatting()
