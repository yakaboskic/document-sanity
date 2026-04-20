#!/usr/bin/env python3
"""
Migrate LuaLaTeX variable files to JSON format.

Usage:
    python scripts/migrate_variables.py variables/indirect-support-variables.tex
    python scripts/migrate_variables.py variables/indirect-support-variables.tex --output variables/indirect-support.json
"""

import re
import json
import argparse
import sys
from pathlib import Path


def parse_lua_variables(tex_content: str) -> dict:
    """Extract variables from LuaLaTeX dictionary definition."""
    variables = {}

    # Find the dictionary = { ... } block
    dict_pattern = r'dictionary\s*=\s*\{([^}]*)\}'
    match = re.search(dict_pattern, tex_content, re.DOTALL)

    if not match:
        raise ValueError("Could not find 'dictionary = { ... }' block in file")

    dict_content = match.group(1)

    # Parse each line: var_name = "value",
    line_pattern = r'(\w+)\s*=\s*"([^"]*)"'
    matches = re.findall(line_pattern, dict_content)

    for var_name, value in matches:
        # Remove var__ prefix if present (keeping it simpler)
        clean_name = var_name.replace('var__', '')

        # Try to convert to number if possible
        clean_value = value.strip()

        # Try parsing as float/int
        try:
            # Check for scientific notation
            if 'e' in clean_value.lower():
                variables[clean_name] = float(clean_value)
            # Remove commas for number parsing
            elif ',' in clean_value:
                # Keep as string if it has commas (formatting preference)
                variables[clean_name] = clean_value
            # Check if it's a number
            elif '.' in clean_value:
                variables[clean_name] = float(clean_value)
            else:
                # Try as int
                try:
                    variables[clean_name] = int(clean_value)
                except ValueError:
                    variables[clean_name] = clean_value
        except ValueError:
            # Keep as string
            variables[clean_name] = clean_value

    return variables


def main():
    parser = argparse.ArgumentParser(
        description="Migrate LuaLaTeX variable files to JSON format"
    )
    parser.add_argument(
        'input_file',
        help='Path to LuaLaTeX variable .tex file'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output JSON file path (default: replaces .tex with .json in variables/)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print JSON without writing file'
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1

    # Read input file
    with open(input_path, 'r') as f:
        tex_content = f.read()

    # Parse variables
    try:
        variables = parse_lua_variables(tex_content)
    except Exception as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        return 1

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Replace -variables.tex with .json
        output_name = input_path.stem.replace('-variables', '') + '.json'
        output_path = input_path.parent / output_name

    # Create JSON
    json_content = json.dumps(variables, indent=2, sort_keys=True)

    if args.dry_run:
        print(f"Would write to: {output_path}")
        print("\nJSON content:")
        print(json_content)
    else:
        # Write JSON file
        with open(output_path, 'w') as f:
            f.write(json_content)

        print(f"✓ Migrated {len(variables)} variables")
        print(f"✓ Written to: {output_path}")
        print(f"\nYou can now delete: {input_path}")
        print(f"And remove luacode from your .tex files")

    return 0


if __name__ == '__main__':
    sys.exit(main())
