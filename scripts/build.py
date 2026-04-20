#!/usr/bin/env python3
r"""
Build preprocessed LaTeX manuscript from templates.

This script:
  1. Loads variables from JSON files
  2. Processes section templates (replaces {{variable}} syntax)
  3. Processes main file (updates \input paths)
  4. Optionally crops figures
  5. Copies supporting files
  6. Generates a README manifest tracking source versions

Output structure:
  current/
    {manuscript}/
      main_current.tex
      sections/
        *.tex
      figures/
        ...
      README.md (manifest of source versions)

Usage:
    python scripts/build.py                                    # Auto-detect latest
    python scripts/build.py --manuscript indirect-support      # Auto-detect latest date
    python scripts/build.py --manuscript indirect-support --date 11182025
    python scripts/build.py --crop-figures                     # Include figure cropping
    python scripts/build.py --strict                           # Fail on undefined vars
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
import subprocess

# Import our variable processor and figure manifest
from variable_processor import VariableProcessor
from figure_manifest import FigureManifest


class ManuscriptBuilder:
    """Build preprocessed LaTeX manuscript from templates."""

    def __init__(
        self,
        manuscript: str,
        date: str,
        root_dir: Path,
        crop_figures: bool = False,
        placeholder: str = "XXXX",
        strict: bool = False,
        verbose: bool = False
    ):
        self.manuscript = manuscript
        self.date = date
        self.root_dir = root_dir
        self.crop_figures = crop_figures
        self.placeholder = placeholder
        self.strict = strict
        self.verbose = verbose

        # Source paths
        self.sections_dir = root_dir / "sections" / manuscript / date
        self.versions_dir = root_dir / "versions" / manuscript
        self.main_file = self.versions_dir / f"main_{date}.tex"
        self.variables_dir = root_dir / "variables"
        # Support both "figures/" and "Figures/" directory naming
        if (root_dir / "Figures").exists():
            self.figures_dir = root_dir / "Figures"
        else:
            self.figures_dir = root_dir / "figures"

        # Output paths - new "current" structure
        self.current_dir = root_dir / "current"
        self.out_dir = self.current_dir / manuscript
        self.out_sections_dir = self.out_dir / "sections"
        self.out_main_file = self.out_dir / "main_current.tex"
        self.out_figures_dir = self.out_dir / "figures"
        self.out_readme = self.out_dir / "README.md"

        # Figure manifest
        # Figure paths are relative to project root (where main.tex wrapper lives)
        self.figure_manifest_path = self.figures_dir / "manifest.json"
        self.figure_manifest = None
        figure_path_prefix = f"current/{manuscript}/figures"
        if self.figure_manifest_path.exists():
            self.figure_manifest = FigureManifest(
                self.figure_manifest_path,
                root_dir,
                figure_path_prefix=figure_path_prefix
            )

        # Variable processor
        self.crop_script_path = root_dir / "scripts" / "crop_figure_whitespace.py"
        self.processor = VariableProcessor(
            placeholder=placeholder,
            figure_manifest=self.figure_manifest,
            output_dir=self.out_dir,
            crop_script=self.crop_script_path if self.crop_script_path.exists() else None
        )

        # Track build metadata
        self.build_metadata = {
            'manuscript': manuscript,
            'source_date': date,
            'build_time': datetime.now().isoformat(),
            'sections': [],
            'variables_file': None,
            'canva_source': None
        }

    def load_variables(self) -> None:
        """Load variables from JSON files."""
        print(f"\n📚 Loading variables...")

        # Load manuscript-specific variables
        manuscript_vars = self.variables_dir / f"{self.manuscript}.json"
        count_manuscript = 0
        if manuscript_vars.exists():
            count_manuscript = self.processor.load_variables(manuscript_vars)
            print(f"  ✓ Loaded {count_manuscript} from {manuscript_vars.name}")
            self.build_metadata['variables_file'] = manuscript_vars.name

        # Load shared variables (if exists)
        shared_vars = self.variables_dir / "shared.json"
        count_shared = 0
        if shared_vars.exists():
            count_shared = self.processor.load_variables(shared_vars)
            print(f"  ✓ Loaded {count_shared} from {shared_vars.name}")

        total = count_manuscript + count_shared
        if total == 0:
            print(f"  ⚠️  No variables found in {self.variables_dir}")
        else:
            print(f"  📊 Total variables: {total}")

    def process_sections(self) -> int:
        """Process all section template files."""
        print(f"\n📄 Processing sections...")

        if not self.sections_dir.exists():
            print(f"  ⚠️  Sections directory not found: {self.sections_dir}")
            return 0

        # Find all .tex files in sections directory
        section_files = sorted(self.sections_dir.glob("*.tex"))

        if not section_files:
            print(f"  ⚠️  No .tex files found in {self.sections_dir}")
            return 0

        # Ensure output directory exists
        self.out_sections_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for section_file in section_files:
            output_file = self.out_sections_dir / section_file.name

            if self.verbose:
                print(f"  • {section_file.name}")

            self.processor.process_file(section_file, output_file)
            self.build_metadata['sections'].append(section_file.name)
            count += 1

        print(f"  ✓ Processed {count} section files")
        return count

    def process_main_file(self) -> None:
        r"""Process main manuscript file and update \input paths."""
        print(f"\n📝 Processing main file...")

        if not self.main_file.exists():
            print(f"  ✗ Main file not found: {self.main_file}")
            sys.exit(1)

        # Read main file
        with open(self.main_file, 'r') as f:
            content = f.read()

        # Replace variables in main file (in case there are any)
        content = self.processor.replace_variables(content, str(self.main_file))

        # Update \input{sections/...} paths to be relative to project root
        # (since main.tex wrapper at root will \input this file)
        def update_input_path(match):
            original_path = match.group(1)
            # Check if it's a section path
            if original_path.startswith('sections/'):
                # Flatten and prefix with current/{manuscript}/sections/
                # e.g., sections/indirect-support/11182025/intro.tex -> current/indirect-support/sections/intro.tex
                parts = original_path.split('/')
                filename = parts[-1]
                return f"\\input{{current/{self.manuscript}/sections/{filename}}}"
            return match.group(0)

        content = re.sub(r'\\input\{([^}]+)\}', update_input_path, content)

        # Ensure output directory exists
        self.out_main_file.parent.mkdir(parents=True, exist_ok=True)

        # Write output
        with open(self.out_main_file, 'w') as f:
            f.write(content)

        print(f"  ✓ Written to: {self.out_main_file}")

    def crop_figures_if_needed(self) -> int:
        """Crop figures if requested (flattened output structure)."""
        if not self.crop_figures:
            return 0

        print(f"\n🖼️  Cropping figures...")

        # Find crop script
        crop_script = self.root_dir / "scripts" / "crop_figure_whitespace.py"
        if not crop_script.exists():
            print(f"  ⚠️  Crop script not found: {crop_script}")
            return 0

        # Find all figures for this manuscript
        manuscript_figures_dir = self.figures_dir / self.manuscript
        if not manuscript_figures_dir.exists():
            print(f"  ⚠️  Figures directory not found: {manuscript_figures_dir}")
            return 0

        # Create output directory
        self.out_figures_dir.mkdir(parents=True, exist_ok=True)

        # Get all PNG and JPG files
        figure_files = list(manuscript_figures_dir.rglob("*.png"))
        figure_files.extend(manuscript_figures_dir.rglob("*.jpg"))
        figure_files.extend(manuscript_figures_dir.rglob("*.jpeg"))

        if not figure_files:
            print(f"  ℹ️  No PNG/JPG figures found")
            return 0

        count = 0
        for figure_file in figure_files:
            # Flatten: just use the filename, not the nested path
            output_file = self.out_figures_dir / figure_file.name

            # Skip if file with same name already exists
            if output_file.exists():
                if self.verbose:
                    print(f"  ⚠️  Skipping duplicate: {figure_file.name}")
                continue

            try:
                # Run crop script
                result = subprocess.run(
                    ['python', str(crop_script), str(figure_file), '--output', str(output_file)],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    if self.verbose:
                        print(f"  • {figure_file.name}")
                    count += 1
                else:
                    print(f"  ⚠️  Failed to crop {figure_file.name}: {result.stderr}")
            except Exception as e:
                print(f"  ⚠️  Error cropping {figure_file.name}: {e}")

        print(f"  ✓ Cropped {count} figures")
        return count

    def copy_figures(self) -> int:
        """Copy figures to output directory (flattened structure)."""
        print(f"\n🖼️  Copying figures...")

        manuscript_figures_dir = self.figures_dir / self.manuscript
        if not manuscript_figures_dir.exists():
            print(f"  ℹ️  No figures directory found")
            return 0

        # Create/clear output directory
        if self.out_figures_dir.exists():
            shutil.rmtree(self.out_figures_dir)
        self.out_figures_dir.mkdir(parents=True, exist_ok=True)

        # Copy all image files to flat structure
        extensions = ['*.png', '*.jpg', '*.jpeg', '*.pdf', '*.eps']
        count = 0

        for ext in extensions:
            for figure_file in manuscript_figures_dir.rglob(ext):
                # Flatten: just use the filename, not the nested path
                output_file = self.out_figures_dir / figure_file.name
                # Skip if file with same name already exists (avoid overwriting)
                if not output_file.exists():
                    shutil.copy2(figure_file, output_file)
                    count += 1
                elif self.verbose:
                    print(f"  ⚠️  Skipping duplicate: {figure_file.name}")

        # Also copy placeholder figures from root figures directory
        for placeholder in self.figures_dir.glob("placeholder-*.png"):
            output_file = self.out_figures_dir / placeholder.name
            if not output_file.exists():
                shutil.copy2(placeholder, output_file)
                count += 1

        print(f"  ✓ Copied {count} files")
        return count

    def copy_supporting_files(self) -> None:
        """Copy .bib, .bst, .cls files to output directory."""
        print(f"\n📚 Copying supporting files...")

        extensions = ['.bib', '.bst', '.cls', '.eps']
        count = 0

        for ext in extensions:
            for file in self.root_dir.glob(f"*{ext}"):
                output_file = self.out_dir / file.name
                shutil.copy2(file, output_file)
                if self.verbose:
                    print(f"  • {file.name}")
                count += 1

        print(f"  ✓ Copied {count} files")

    def generate_readme(self) -> None:
        """Generate README manifest with build information."""
        print(f"\n📋 Generating build manifest...")

        # Get Canva source info from manifest
        if self.figure_manifest and self.figure_manifest.canva_config:
            self.build_metadata['canva_source'] = self.figure_manifest.canva_config.get('source')

        # Format build time nicely
        build_dt = datetime.fromisoformat(self.build_metadata['build_time'])
        build_time_str = build_dt.strftime("%Y-%m-%d %H:%M:%S")

        readme_content = f"""# {self.manuscript} - Current Build

This directory contains the **current built version** of the manuscript, ready for sharing with collaborators.

## Build Information

| Field | Value |
|-------|-------|
| **Manuscript** | `{self.build_metadata['manuscript']}` |
| **Source Version** | `{self.build_metadata['source_date']}` |
| **Built At** | {build_time_str} |
| **Variables File** | `{self.build_metadata['variables_file'] or 'N/A'}` |
| **Canva Source** | `{self.build_metadata['canva_source'] or 'N/A'}` |

## Source Files

**Main file:** `versions/{self.manuscript}/main_{self.date}.tex`

**Sections from:** `sections/{self.manuscript}/{self.date}/`
"""

        if self.build_metadata['sections']:
            readme_content += "\n**Processed sections:**\n"
            for section in self.build_metadata['sections']:
                readme_content += f"- `{section}`\n"

        readme_content += f"""
## Directory Structure

```
current/{self.manuscript}/
├── main_current.tex      ← Compile this file
├── sections/
│   └── *.tex             ← Processed section files
├── figures/
│   └── ...               ← Figure files
├── *.bib, *.bst, *.cls   ← Supporting files
└── README.md             ← This file
```

## How to Compile

```bash
cd current/{self.manuscript}
pdflatex main_current.tex
bibtex main_current
pdflatex main_current.tex
pdflatex main_current.tex
```

Or use latexmk:
```bash
cd current/{self.manuscript}
latexmk -pdf main_current.tex
```

## Notes

- This directory is **auto-generated** by `scripts/build.py`
- Do NOT edit files here directly - edit the source files instead
- Source templates use `{{{{variable}}}}` syntax for reproducible values
- Source templates use `{{{{canva:N}}}}` syntax for Canva figures

## Rebuilding

To rebuild from source:
```bash
python scripts/build.py --manuscript {self.manuscript}
```

---
*Auto-generated by build.py*
"""

        with open(self.out_readme, 'w') as f:
            f.write(readme_content)

        print(f"  ✓ Written to: {self.out_readme}")

    def print_summary(self) -> bool:
        """Print summary and check for issues."""
        print(f"\n{'='*60}")
        print(f"📊 Build Summary")
        print(f"{'='*60}")

        # Print variable report
        self.processor.print_report(verbose=self.verbose)

        # Print figure report if manifest exists
        if self.figure_manifest:
            self.figure_manifest.print_report()

        # Check for errors
        has_errors = False

        if self.processor.has_undefined_variables():
            if self.strict:
                print(f"\n❌ Build failed: undefined variables found (strict mode)")
                has_errors = True
            else:
                print(f"\n⚠️  Build completed with warnings")

        if not has_errors:
            print(f"\n✅ Build complete!")
            print(f"\n📂 Output directory: {self.out_dir}")
            print(f"📝 Main file: {self.out_main_file}")
            print(f"\n💡 To compile:")
            print(f"   cd {self.out_dir}")
            print(f"   pdflatex main_current.tex")

        return not has_errors

    def build(self) -> bool:
        """Run the complete build process."""
        print(f"\n{'='*60}")
        print(f"🔨 Building manuscript: {self.manuscript} ({self.date})")
        print(f"{'='*60}")

        # Clean output directory if it exists
        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # Load variables
        self.load_variables()

        # Extract Canva ZIP if configured (before processing sections)
        if self.figure_manifest:
            crop_script = self.root_dir / "scripts" / "crop_figure_whitespace.py"
            self.figure_manifest.extract_canva_zip(self.out_dir, crop_script)

        # Process sections
        self.process_sections()

        # Process main file
        self.process_main_file()

        # Handle figures
        if self.crop_figures:
            self.crop_figures_if_needed()
        else:
            self.copy_figures()

        # Copy supporting files
        self.copy_supporting_files()

        # Generate README manifest
        self.generate_readme()

        # Print summary
        success = self.print_summary()

        return success


def find_latest_version(root_dir: Path, manuscript: Optional[str] = None) -> Tuple[str, str]:
    """Find the latest manuscript version."""
    versions_dir = root_dir / "versions"

    if not versions_dir.exists():
        raise ValueError(f"Versions directory not found: {versions_dir}")

    # If manuscript not specified, find all manuscripts
    if manuscript is None:
        manuscripts = [d.name for d in versions_dir.iterdir() if d.is_dir()]
        if not manuscripts:
            raise ValueError(f"No manuscripts found in {versions_dir}")
        if len(manuscripts) > 1:
            raise ValueError(
                f"Multiple manuscripts found: {manuscripts}. "
                "Please specify --manuscript"
            )
        manuscript = manuscripts[0]

    manuscript_dir = versions_dir / manuscript
    if not manuscript_dir.exists():
        raise ValueError(f"Manuscript not found: {manuscript}")

    # Find all main_*.tex files
    main_files = list(manuscript_dir.glob("main_*.tex"))
    if not main_files:
        raise ValueError(f"No main_*.tex files found in {manuscript_dir}")

    # Extract dates and find latest
    dates = []
    for file in main_files:
        match = re.search(r'main_(\d{8})\.tex$', file.name)
        if match:
            dates.append(match.group(1))

    if not dates:
        raise ValueError(f"No valid main_MMDDYYYY.tex files found")

    # Parse MMDDYYYY format and find latest by actual date
    def parse_date(date_str: str) -> datetime:
        """Parse MMDDYYYY string to datetime."""
        return datetime.strptime(date_str, "%m%d%Y")

    latest_date = max(dates, key=parse_date)
    return manuscript, latest_date


def main():
    parser = argparse.ArgumentParser(
        description="Build preprocessed LaTeX manuscript from templates"
    )
    parser.add_argument(
        '--manuscript', '-m',
        help='Manuscript name (default: auto-detect)'
    )
    parser.add_argument(
        '--date', '-d',
        help='Date (MMDDYYYY) (default: auto-detect latest)'
    )
    parser.add_argument(
        '--crop-figures',
        action='store_true',
        help='Crop whitespace from figures during build'
    )
    parser.add_argument(
        '--placeholder',
        default='XXXX',
        help='Placeholder for undefined variables (default: XXXX)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Fail if undefined variables are found'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--export-canva',
        action='store_true',
        help='Export figures from Canva before building'
    )

    args = parser.parse_args()

    # Determine root directory (parent of scripts/)
    root_dir = Path(__file__).parent.parent

    try:
        # Auto-detect manuscript and/or date if not specified
        manuscript = args.manuscript
        date = args.date

        if manuscript is None or date is None:
            detected_manuscript, detected_date = find_latest_version(root_dir, manuscript)
            if manuscript is None:
                manuscript = detected_manuscript
            if date is None:
                date = detected_date
            print(f"Auto-detected: {manuscript} ({date})")

        # Export from Canva if requested
        if args.export_canva:
            print(f"\n{'='*60}")
            print(f"📥 Exporting figures from Canva")
            print(f"{'='*60}")
            try:
                result = subprocess.run(
                    ['python', 'scripts/canva_export.py', '--from-manifest', manuscript],
                    cwd=root_dir,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(result.stdout)
                else:
                    print(f"⚠️  Canva export encountered issues:")
                    print(result.stderr)
                    print("Continuing with build...")
            except Exception as e:
                print(f"⚠️  Could not export from Canva: {e}")
                print("Continuing with build...")

        # Build
        builder = ManuscriptBuilder(
            manuscript=manuscript,
            date=date,
            root_dir=root_dir,
            crop_figures=args.crop_figures,
            placeholder=args.placeholder,
            strict=args.strict,
            verbose=args.verbose
        )

        success = builder.build()
        return 0 if success else 1

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
