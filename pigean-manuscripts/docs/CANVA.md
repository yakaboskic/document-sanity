# Canva Integration Guide

Complete guide for integrating Canva designs into your LaTeX manuscripts.

**Quick Navigation:**
- [Quick Start](#quick-start) - Get started in 3 steps
- [Unified Workflow](#unified-workflow) - Recommended approach
- [API Mode](#api-mode) - After Canva approval
- [OAuth Setup](#oauth-setup) - API authentication
- [Migration Guide](#migration-guide) - Upgrading from old workflow
- [Troubleshooting](#troubleshooting) - Common issues

---

## Quick Start

### 3-Step Workflow

**1. Configure manifest** (`figures/manifest.json`):
```json
{
  "canva": {
    "source": "figures/indirect-support/canva-exports/main-design.zip",
    "output_dir": "figures/indirect-support/real",
    "auto_extract": true,
    "crop": true,
    "pages": {
      "1": {"filename": "pigean-figure-1.png", "width": "\\textwidth"},
      "2": {"filename": "validation-figure-2.png", "width": "0.8\\textwidth"}
    }
  }
}
```

**2. Download from Canva:**
- Open design in Canva
- Share → Download → PNG
- Save ZIP to configured location

**3. Use in templates:**
```latex
\begin{figure}[ht!]
    \centering
    {{canva:1}}
    \caption{Main results}
    \label{fig:results}
\end{figure}
```

**4. Build:**
```bash
python scripts/build.py
```

Done! Build automatically extracts, crops, and processes figures.

---

## Unified Workflow

### Overview

The unified workflow uses a single manifest configuration and `{{canva:page}}` syntax in templates. Works with either manual ZIP imports or the Canva API.

**Benefits:**
- ✅ Simple page numbers in templates
- ✅ Single source of truth
- ✅ Automatic extraction and cropping
- ✅ Self-documenting configuration
- ✅ Works with manual or API mode

### Manifest Configuration

#### Full Example

```json
{
  "canva": {
    "comment": "Choose ONE mode: manual ZIP or API",

    "source": "figures/indirect-support/canva-exports/main-design.zip",
    "design_id": null,

    "output_dir": "figures/indirect-support/real",
    "auto_extract": true,
    "crop": true,

    "pages": {
      "1": {
        "filename": "pigean-figure-1.png",
        "caption_height": "2in",
        "width": "\\textwidth"
      },
      "2": {
        "filename": "validation-figure-2.png",
        "caption_height": "3in",
        "width": "0.8\\textwidth"
      },
      "3": {
        "filename": "methods-diagram.png",
        "caption_height": "2in",
        "width": "\\textwidth"
      }
    }
  }
}
```

#### Configuration Fields

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `source` | string | Path to downloaded ZIP (manual mode) | Required for manual mode |
| `design_id` | string | Canva design ID (API mode) | Required for API mode |
| `output_dir` | string | Where to save extracted figures | Required |
| `auto_extract` | boolean | Automatically extract ZIP on build | `true` |
| `crop` | boolean | Automatically crop whitespace | `true` |
| `pages` | object | Page-to-filename mappings | Required |

#### Page Specifications

```json
"1": {
  "filename": "output-filename.png",
  "caption_height": "2in",
  "width": "\\textwidth"
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `filename` | Output filename in `output_dir` | Required |
| `caption_height` | Placeholder height (2in/3in/4in) | `"2in"` |
| `width` | LaTeX width specification | `"\\textwidth"` |

### Template Syntax

```latex
% Canva pages (recommended)
{{canva:1}}   % Page 1 from Canva design
{{canva:2}}   % Page 2 from Canva design

% Traditional figures (still supported)
{{fig:figure_id}}

% Variables
{{VARIABLE_NAME}}
{{PVALUE:.2e}}
```

All three can be mixed in the same document.

### Build Process

When you run `python scripts/build.py`:

1. **Load manifest** - Read Canva configuration
2. **Extract ZIP** - If manual mode and `auto_extract: true`
   - Extract numbered pages (1.png, 2.png, etc.)
   - Map to configured filenames
   - Crop whitespace if enabled
3. **Process templates** - Replace `{{canva:N}}` with `\includegraphics`
4. **Copy to output** - Move processed figures to build directory

### Example Workflows

#### Example 1: Basic Usage

**Manifest:**
```json
{
  "canva": {
    "source": "figures/indirect-support/canva-exports/figures.zip",
    "output_dir": "figures/indirect-support/real",
    "pages": {
      "1": {"filename": "fig1.png"},
      "2": {"filename": "fig2.png"}
    }
  }
}
```

**Template:**
```latex
{{canva:1}}  % → \includegraphics[width=\textwidth]{../../figures/indirect-support/real/fig1.png}
{{canva:2}}
```

#### Example 2: Custom Widths

```json
{
  "canva": {
    "pages": {
      "1": {"filename": "full.png", "width": "\\textwidth"},
      "2": {"filename": "narrow.png", "width": "0.6\\textwidth"},
      "3": {"filename": "column.png", "width": "\\columnwidth"}
    }
  }
}
```

#### Example 3: Multiple Designs

Combine multiple ZIPs by renumbering:

```bash
# Extract both
unzip main.zip -d temp1
unzip supplementary.zip -d temp2

# Renumber sequentially
mv temp1/1.png combined/1.png
mv temp1/2.png combined/2.png
mv temp2/1.png combined/3.png  # Continue numbering
mv temp2/2.png combined/4.png

# Re-zip
cd combined && zip ../all-figures.zip *.png
```

Then use single manifest with all pages.

---

## API Mode

Once your Canva app is approved, you can switch to API mode for automatic downloads.

### Configuration

Change manifest from manual to API mode:

**Manual mode:**
```json
{
  "canva": {
    "source": "figures/indirect-support/canva-exports/design.zip",
    "design_id": null,
    ...
  }
}
```

**API mode:**
```json
{
  "canva": {
    "source": null,
    "design_id": "DAFxxxxxxxxxxxxxx",
    ...
  }
}
```

Everything else stays the same! Templates don't change.

### Benefits

- ✅ Automatic updates when design changes
- ✅ No manual downloads
- ✅ Same template syntax
- ✅ Same manifest structure

### When to Use

| Feature | Manual Mode | API Mode |
|---------|-------------|----------|
| Approval needed | ❌ No | ✅ Yes |
| Works immediately | ✅ Yes | ⏳ After approval |
| Update workflow | Download ZIP | Automatic |
| Best for | **Right now** | Production later |

---

## OAuth Setup

To use API mode, you need to authenticate with Canva OAuth2.

### Quick Setup (5 minutes)

**1. Create Canva App**

Visit https://www.canva.com/developers/

- Click "Create an app"
- Name: "PIGEAN Manuscript Builder"
- Redirect URI: `http://localhost:8080/callback`
- Note your Client ID and Client Secret

**2. Authenticate**

```bash
python scripts/canva_auth.py
```

Enter your Client ID and Client Secret when prompted. Browser will open for authorization.

**3. Verify**

```bash
python scripts/canva_export.py --list-designs
```

You should see your Canva designs listed.

### Find Design IDs

```bash
# List all designs
python scripts/canva_export.py --list-designs

# Search for specific design
python scripts/canva_export.py --list-designs --search "manuscript"
```

Copy the design ID and add to manifest:

```json
{
  "canva": {
    "design_id": "DAFxxxxxxxxxxxxxx"
  }
}
```

### OAuth Details

The authentication script:
- Starts local HTTP server on port 8080
- Opens browser to Canva authorization page
- Receives OAuth callback
- Exchanges code for access token
- Saves to `~/.canva_config.json` with secure permissions (chmod 600)

**Scopes requested:**
- `design:meta:read` - Read design metadata
- `design:content:read` - Read design content
- `asset:read` - Read exported assets

### Troubleshooting OAuth

**"Port 8080 is already in use"**
```bash
# Find what's using the port
lsof -i :8080
# Kill the process and try again
```

**"Invalid redirect URI"**
- Ensure redirect URI in Canva app is exactly: `http://localhost:8080/callback`

**Token expired**
```bash
# Re-authenticate to get new token
python scripts/canva_auth.py
```

---

## Migration Guide

### From Manual Import Script (Deprecated)

**Old workflow:**
```bash
python scripts/canva_manual_import.py design.zip --map 1:figure_1 2:figure_2
```

**New workflow:**

1. Configure manifest:
```json
{
  "canva": {
    "source": "figures/indirect-support/canva-exports/design.zip",
    "pages": {
      "1": {"filename": "figure-1.png"},
      "2": {"filename": "figure-2.png"}
    }
  }
}
```

2. Place ZIP at configured location

3. Build:
```bash
python scripts/build.py  # Extraction happens automatically
```

### From Traditional Figures

**Old manifest:**
```json
{
  "figures": {
    "fig1": {"source": "figures/indirect-support/real/fig1.png"},
    "fig2": {"source": "figures/indirect-support/real/fig2.png"}
  }
}
```

**Old templates:**
```latex
{{fig:fig1}}
{{fig:fig2}}
```

**New manifest:**
```json
{
  "canva": {
    "source": "figures/design.zip",
    "output_dir": "figures/indirect-support/real",
    "pages": {
      "1": {"filename": "fig1.png"},
      "2": {"filename": "fig2.png"}
    }
  }
}
```

**New templates:**
```latex
{{canva:1}}
{{canva:2}}
```

**Benefits:**
- Simpler syntax (page numbers vs IDs)
- Automatic extraction and cropping
- Self-documenting configuration

### To API Mode

When Canva approves your app, just change two fields:

```json
{
  "canva": {
    "source": null,              // Was: "figures/.../design.zip"
    "design_id": "DAFxxxxxx",    // Was: null
    // Everything else stays the same
  }
}
```

Templates don't change! `{{canva:1}}` works the same way.

---

## Before & After Comparison

### Before: Multi-Step Manual Process

**Steps:**
1. Download `design.zip` from Canva
2. Run import script with mapping
3. Update manifest with figure specs
4. Build manuscript

**Template:**
```latex
{{fig:complex_figure_id}}
```

**Issues:**
- ❌ Manual mapping every time
- ❌ Obscure figure IDs
- ❌ Configuration scattered
- ❌ Error-prone

### After: Unified Automatic Process

**Steps:**
1. Download ZIP to configured location
2. Build (automatic extraction, cropping, processing)

**Template:**
```latex
{{canva:1}}  % Simple page number
```

**Benefits:**
- ✅ No manual import
- ✅ Simple page numbers
- ✅ Single source of truth
- ✅ Automatic processing
- ✅ Self-documenting

---

## Troubleshooting

### "Canva ZIP not found"

```
⚠️  Canva ZIP not found: figures/indirect-support/canva-exports/main-design.zip
```

**Solution:** Download from Canva and place at specified location.

### "Page N not found in ZIP"

```
⚠️  Page 3 not found in ZIP
```

**Solution:**
- Add page to Canva design and re-download, OR
- Remove page from manifest, OR
- Fix page numbering

### Missing Placeholder Warnings

```
⚠️  Figures using placeholders (1):
  • canva:5 - canva_file_not_found
```

**Solution:** File hasn't been extracted. Check:
1. ZIP exists at `source` location
2. ZIP contains `5.png`
3. `auto_extract: true` in manifest
4. Re-run build

### Canva Syntax in Regular Text

To show literal syntax in document:

```latex
% This will be replaced:
{{canva:1}}

% To show syntax, use \verb or \texttt:
We use the \verb|{{canva:1}}| syntax.
```

### API Authentication Issues

**"Config file not found"**
```bash
# Run authentication first
python scripts/canva_auth.py
```

**"403 Forbidden"**
- Check app has required scopes enabled
- Re-authenticate: `python scripts/canva_auth.py`

**"Design not found"**
- Verify design ID is correct
- Check you have access to the design
- List designs to confirm: `python scripts/canva_export.py --list-designs`

---

## Best Practices

### 1. Organize by Manuscript

```
figures/
├── indirect-support/
│   └── canva-exports/
│       ├── main-figures.zip
│       └── supplementary.zip
└── other-manuscript/
    └── canva-exports/
        └── figures.zip
```

### 2. Use Descriptive Filenames

```json
"pages": {
  "1": {"filename": "main-result.png"},
  "2": {"filename": "validation-cohort-1.png"}
}
```

Not:
```json
"pages": {
  "1": {"filename": "fig1.png"}
}
```

### 3. Keep Manifest in Sync

When updating Canva design:
1. Re-download ZIP
2. Verify page count matches manifest
3. Update manifest if pages added/removed
4. Rebuild

### 4. Version Control

Git commit:
- ✅ Manifest file
- ✅ Template files
- ❌ ZIP files (too large)
- ❌ Extracted figures (generated)

Add to `.gitignore`:
```
figures/**/canva-exports/*.zip
```

### 5. Document Configuration

```json
{
  "canva": {
    "comment": "Main manuscript figures - updated 2025-10-28",
    "pages": {
      "1": {
        "filename": "overview.png",
        "comment": "Study design for Figure 1"
      }
    }
  }
}
```

---

## FAQ

**Q: Can I use both manual ZIP and API mode?**
A: No, choose one. Set either `source` (manual) or `design_id` (API).

**Q: Can I have multiple Canva designs?**
A: One design per `canva` section. For multiple, renumber pages and combine ZIPs.

**Q: Do I still need the manual import script?**
A: No! Build script handles extraction automatically. `canva_manual_import.py` is deprecated.

**Q: Can I mix Canva and non-Canva figures?**
A: Yes! Use `{{canva:N}}` for Canva, `{{fig:name}}` for others.

**Q: How do I disable auto-extraction?**
A: Set `"auto_extract": false` in manifest.

**Q: What if I don't have all pages yet?**
A: Missing pages use placeholders automatically.

---

## Related Documentation

- **[Quick Reference](QUICK_REFERENCE.md)** - Command cheatsheet
- **[Canva Branding](CANVA_BRANDING.md)** - Typography and design specs
- **[Build System](BUILD_SYSTEM.md)** - Technical documentation

---

**Last Updated:** October 2025
**Status:** Production ready
