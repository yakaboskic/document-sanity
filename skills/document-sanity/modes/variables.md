# variables: numbers (and tables) with provenance

Every number a document claims is declared once in its
`src/<doc>/manifest.yaml` and written as a token. The PDF and Word get the
value; the HTML viewer makes it clickable and shows `inputs → command →
value`.

## Declare

```yaml
variables:
  NUM_SAMPLES: 1247                      # simple form: just the value
  PVAL:                                  # full form: value + provenance
    value: 0.0087
    provenance:
      description: Two-sided p-value, BH-adjusted across 12 tests.
      source: data/results.csv           # one input, or…
      data: [data/raw.csv, data/meta.tsv]  # several (hides `source` in the graph)
      command: python scripts/fit.py --out data/results.csv
      updated: "2026-04-21"
```

Names are `[A-Za-z_][A-Za-z0-9_]*`; UPPER_SNAKE by convention.

## Use

```markdown
We analyzed {{NUM_SAMPLES:,}} samples ($p = {{PVAL:.2e}}$, R<sup>2</sup> = {{R2:.2f}}).
```

| Spec | Gives |
|---|---|
| `:,` | 1,247 |
| `:.2f` | 0.87 |
| `:.2e` | 8.70e-03 (the HTML viewer typesets it as × 10⁻³ inside math) |
| `:.1%` | 87.0% |
| any Python `format()` spec | `:03d` → 042 |

Tokens work in `docs/*.md`, in ```latex blocks, inside `$…$` math, and in the
manifest's `abstract:` and `notice:`. A literal `{{` in prose is written
`\{\{`.

## Data tables

A table produced by an analysis is a file, not a pasted grid:

```yaml
tables:
  subgroup_summary:
    source: tables/subgroup_summary.csv
    format: csv              # csv | tsv | markdown | latex
    provenance:
      description: Effect size by subgroup.
      command: python scripts/subgroup_summary.py --out tables/subgroup_summary.csv
      updated: "2026-04-21"
```

Write `{{tab:subgroup_summary}}` where it goes. It becomes a pipe table at
build time, so PDF, HTML and Word render it the same. `format: latex` files
are used from a ```latex block with `\input{tables/<file>.tex}` instead.

## Rules

- **Never invent provenance.** If the user gives a number without saying
  where it came from, ask for the file, the command and when it was computed.
  If they don't know, leave those fields out. An empty field is honest; a
  plausible one isn't.
- `source`, `data` and `command` are informational. The build never runs
  them. Don't run `command:` yourself unless the user asks you to recompute.
- `updated:` is when the value was produced, not when you typed it.
- **Changing a number** that a sent or submitted version showed: cut a new
  version (`version` mode) and change it there, so the old folder keeps what
  it said. Edit in place only when the old value was simply wrong and the
  user says so.
- Never type the number into the prose next to the token, and never
  hard-code a number a variable already holds.

## Check

An undefined token renders as `XXXX` in every output (red in the HTML
viewer). `uv run document-sanity check <doc>` lists each one with its file
and line; `out/<doc>/available_variables.txt` lists what's defined.
