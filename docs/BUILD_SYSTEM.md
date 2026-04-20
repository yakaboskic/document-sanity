# Build System Documentation

Comprehensive documentation for the PIGEAN manuscript build system.

## Overview

The build system transforms LaTeX templates with variable and figure placeholders into compilation-ready LaTeX files. It provides:

- **Variable substitution** with Python-style formatting
- **Figure management** with automatic processing and placeholders
- **Template preservation** - source files never modified
- **Reproducible builds** - `current/` directory can be regenerated anytime
- **Collaboration-ready** - simplified output structure for Overleaf sharing

## Architecture

```
┌─────────────────┐
│  Source Files   │
│  (Templates)    │
└────────┬────────┘
         │
         ├─ sections/*/MMDDYYYY/*.tex     (LaTeX templates with {{...}})
         ├─ versions/*/main_MMDDYYYY.tex  (Main files with \input{...})
         ├─ variables/*.json               (Variable definitions)
         └─ figures/manifest.json          (Figure definitions)
         │
         ▼
┌─────────────────┐
│   build.py      │
│  (Processor)    │
└────────┬────────┘
         │
         ├─ Load variables from JSON
         ├─ Load figure manifest
         ├─ Process section templates
         │  └─ Replace {{variable}} and {{fig:id}}
         ├─ Process main file
         │  └─ Update \input{} paths
         ├─ Process figures
         │  └─ Crop and copy to current/
         ├─ Copy supporting files
         └─ Generate README manifest
         │
         ▼
┌─────────────────┐
│  Output Files   │
│  (Compiled)     │
└─────────────────┘
         │
         └─ current/{manuscript}/
            ├─ main_current.tex   (Main file to compile)
            ├─ sections/*.tex     (Processed section files)
            ├─ figures/           (Processed figures)
            ├─ README.md          (Build manifest)
            └─ *.bib, *.cls       (Supporting files)
            │
            ▼
         pdflatex main_current.tex
            │
            ▼
         main_current.pdf
```

## Components

### 1. Variable Processor (`variable_processor.py`)

**Responsibilities:**
- Parse `{{variable}}` and `{{variable:format}}` syntax
- Load variables from JSON files
- Format values using Python format specifications
- Track undefined variables for reporting
- Replace `{{fig:id}}` with `\includegraphics` commands

**Key Features:**
- Supports nested variable lookups
- Python-style formatting (`.2f`, `.2e`, `,`, `.1%`)
- Graceful handling of undefined variables (uses `XXXX` placeholder)
- Line-by-line processing with error tracking

**Example:**
```python
processor = VariableProcessor(placeholder="XXXX")
processor.load_variables(Path("variables/manuscript.json"))
content = processor.replace_variables(template_content, "file.tex")
```

### 2. Figure Manifest (`figure_manifest.py`)

**Responsibilities:**
- Load figure definitions from `manifest.json`
- Resolve figure paths and check existence
- Generate `\includegraphics` commands with correct paths
- Handle missing figures with appropriate placeholders
- Process figures (crop, copy) during build

**Manifest Schema:**
```json
{
  "figures": {
    "figure_id": {
      "source": "path/to/figure.png",  // or null for placeholder
      "caption_height": "2in",          // placeholder size selector
      "crop": true,                     // whether to crop whitespace
      "width": "\\textwidth"            // LaTeX width specification
    }
  },
  "placeholders": {
    "2in": "path/to/placeholder-2in.png",
    "3in": "path/to/placeholder-3in.png"
  }
}
```

**Key Features:**
- Type-safe figure references
- Automatic placeholder selection by caption height
- Integration with crop script
- Relative path calculation from output location

### 3. Build Script (`build.py`)

**Responsibilities:**
- Orchestrate the entire build process
- Auto-detect latest manuscript version
- Process all templates and generate output
- Report errors and warnings
- Validate build completeness

**Build Process:**

1. **Initialization**
   - Parse command-line arguments
   - Determine manuscript and date
   - Load variable processor and figure manifest

2. **Variable Loading**
   - Load manuscript-specific variables
   - Load shared variables (if exist)
   - Report total variable count

3. **Section Processing**
   - Find all `.tex` files in `sections/{manuscript}/{date}/`
   - Process each file through variable processor
   - Write to `current/{manuscript}/sections/` (flattened structure)

4. **Main File Processing**
   - Read `versions/{manuscript}/main_{date}.tex`
   - Replace variables in main file
   - Update `\input{sections/...}` to `\input{sections/...}` (simplified paths)
   - Write to `current/{manuscript}/main_current.tex`

5. **Figure Processing**
   - Process each figure in manifest
   - Crop if requested (uses `crop_figure_whitespace.py`)
   - Copy to `current/{manuscript}/figures/`
   - Or copy placeholder if source missing

6. **Supporting Files**
   - Copy `.bib`, `.bst`, `.cls`, `.eps` to `current/{manuscript}/`

7. **README Generation**
   - Create `README.md` manifest with build information
   - Track source date, build time, and configuration

8. **Reporting**
   - Variable usage report (defined, used, undefined)
   - Figure processing report (processed, placeholders)
   - Build status (success or warnings)

**Command-Line Options:**
```bash
python scripts/build.py [options]

Options:
  --manuscript, -m TEXT     Manuscript name (default: auto-detect)
  --date, -d TEXT           Date MMDDYYYY (default: auto-detect latest)
  --crop-figures            Crop whitespace from figures during build
  --placeholder TEXT        Placeholder for undefined variables (default: XXXX)
  --strict                  Fail if undefined variables are found
  --verbose, -v             Verbose output
```

### 4. Migration Script (`migrate_variables.py`)

**Responsibilities:**
- Convert LuaLaTeX variable files to JSON
- Parse Lua dictionary syntax
- Infer data types (float, int, string)
- Handle scientific notation

**Usage:**
```bash
python scripts/migrate_variables.py variables/old-variables.tex
# Creates: variables/old.json
```

### 5. Versioning Script (`make_today_version.py`)

**Responsibilities:**
- Create new dated manuscript version
- Copy main file with updated date
- Copy all section files to new dated directory
- Update section file references in main file

**Integration with Build System:**
- Works on source templates (not `current/` directory)
- Preserves template syntax (`{{...}}`)
- Creates new dated directories
- Updates `\input` paths automatically

### 6. Figure Tools

#### Placeholder Generator (`generate_placeholders.py`)
- Creates placeholder images with different sizes
- Uses PIL to draw styled placeholders
- Generates 2in, 3in, 4in variants
- Saves at 300 DPI

#### Crop Script (`crop_figure_whitespace.py`)
- Detects and removes vertical whitespace
- Preserves figure width (important for `\textwidth`)
- Configurable padding
- Supports PNG, JPG, PDF (with dependencies)

## Template Syntax

### Variable Syntax

**Basic:**
```latex
{{VARIABLE_NAME}}
```

**With Formatting:**
```latex
{{VARIABLE_NAME:format_spec}}
```

**Format Specifications:**
- `:.Nf` - Fixed decimal places (e.g., `:.2f` → `0.30`)
- `:.Ne` - Scientific notation (e.g., `:.2e` → `7.51e-13`)
- `:,` - Thousands separator (e.g., `:,` → `6,488`)
- `:.N%` - Percentage (e.g., `:.1%` → `58.0%`)

**Pattern:** `\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]+))?\}\}`

### Figure Syntax

**Basic:**
```latex
{{fig:figure_id}}
```

Expands to:
```latex
\includegraphics[width=\textwidth]{../figures/path/to/figure.png}
```

**Pattern:** `\{\{fig:([a-zA-Z_][a-zA-Z0-9_]*)\}\}`

## Error Handling

### Undefined Variables

**Behavior:**
- Replaced with placeholder (default: `XXXX`)
- Warning message with file and line number
- Build continues (unless `--strict`)

**Example:**
```
⚠️  WARNING: Undefined variables found (3):
  • NEW_ANALYSIS_R2:.2f
      methods_10072025.tex:42
```

### Missing Figures

**Behavior:**
- Uses placeholder with appropriate caption height
- Warning message with reason
- Build continues

**Example:**
```
⚠️  Figures using placeholders (2):
  • future_figure - Source not found: None
  • analysis_plot - Not defined in manifest
```

### Build Failures

**Strict Mode:**
- Enabled with `--strict` flag
- Fails if any undefined variables found
- Useful for CI/CD pipelines

## Performance Considerations

### Build Speed

**Factors:**
- Number of section files
- Number of figures to process
- Figure cropping (slower if enabled)

**Optimization:**
- Variables cached in memory
- Files processed sequentially
- Figure processing parallelizable (future enhancement)

**Typical Build Times:**
- Small manuscript (~5 sections): 1-2 seconds
- Medium manuscript (~15 sections): 2-4 seconds
- Large manuscript (~30 sections): 4-8 seconds

### Memory Usage

**Considerations:**
- Variables stored in-memory dictionary
- Files processed one at a time
- Figure processing may temporarily use significant memory (PIL)

**Memory Profile:**
- Baseline: ~50 MB
- Per section: ~1 MB
- Per figure: ~10-50 MB (during processing)

## Testing

### Unit Tests

Key functions to test:
- Variable formatting (`format_value`)
- Pattern matching (regex)
- Figure path resolution
- Manifest loading

### Integration Tests

End-to-end scenarios:
- Build with all variables defined
- Build with undefined variables
- Build with missing figures
- Build with figure cropping

### Manual Testing

```bash
# Test basic build
python scripts/build.py --manuscript test --date 01012025

# Test with undefined variables
python scripts/build.py --verbose

# Test strict mode
python scripts/build.py --strict

# Test figure cropping
python scripts/build.py --crop-figures --verbose
```

## Extending the System

### Adding New Format Specifications

Edit `variable_processor.py`:

```python
def format_value(self, value: Any, format_spec: Optional[str]) -> str:
    # Add custom format handling
    if format_spec == 'custom':
        return custom_format(value)
    # ... existing code
```

### Adding New Figure Processing

Edit `figure_manifest.py`:

```python
def process_figure(self, figure_spec: FigureSpec, output_path: Path):
    # Add custom processing
    if figure_spec.needs_special_processing:
        special_process(figure_spec, output_path)
    # ... existing code
```

### Custom Build Steps

Edit `build.py`:

```python
def custom_build_step(self):
    """Add custom build step."""
    print(f"\n🔧 Running custom step...")
    # Custom processing here

# Call in build():
def build(self) -> bool:
    # ... existing steps
    self.custom_build_step()
    # ... continue
```

## Debugging

### Verbose Mode

```bash
python scripts/build.py --verbose
```

Shows:
- Individual files being processed
- Variable replacements
- Figure processing details
- Unused variables

### Debug Output

Add to code:
```python
if self.verbose:
    print(f"  • Processing: {file.name}")
    print(f"    Variables replaced: {count}")
```

### Common Issues

**Issue:** Build succeeds but PDF won't compile
- **Check:** LaTeX syntax in templates
- **Solution:** Verify `current/{manuscript}/` files manually

**Issue:** Figures not showing in PDF
- **Check:** Figure paths in output
- **Solution:** Verify relative paths are correct

**Issue:** Variables not replaced
- **Check:** JSON syntax in variable files
- **Solution:** Validate JSON with `python -m json.tool variables/file.json`

## Best Practices

### Development

1. **Test builds frequently** - catch errors early
2. **Use verbose mode** - understand what's happening
3. **Check `current/` files** - verify output is correct
4. **Version control** - commit source, not output

### Production

1. **Use strict mode** - ensure completeness
2. **Automate builds** - CI/CD integration
3. **Document variables** - add comments in JSON
4. **Track figure versions** - use git for manifest

### Maintenance

1. **Keep scripts updated** - follow semantic versioning
2. **Document changes** - update this file
3. **Test regressions** - maintain test suite
4. **Archive old versions** - git tags for releases

## Future Enhancements

Potential improvements:

- [ ] Parallel figure processing
- [ ] Watch mode (auto-rebuild on changes)
- [ ] Variable validation schemas
- [ ] Figure caching (skip unchanged)
- [ ] Build profiles (dev, production)
- [ ] LaTeX syntax validation
- [ ] Variable usage analysis
- [ ] Figure dimension validation
- [ ] Build artifact checksums
- [ ] Remote figure fetching

---

**Last Updated:** November 2025
**Version:** 2.0.0
