# version: a new version is a folder

Each folder under `src/` is a self-contained document: manifest, docs,
figures, tables, references. A new version is a copy of one, made by the
tool, so the old folder keeps exactly what it said when it went out.

## When

- Before changing something that has been sent, submitted or reviewed: the
  resubmission, the "v2 after reviewer 2", the agency's revised format.
- Before a risky rewrite the user may want to compare against.
- Not for every edit. Inside a draft, `git` (if the project uses it) is the
  history; a version is a snapshot someone received.

## Commands

```bash
uv run document-sanity new-version --source manuscript --name 10182026-resubmission
uv run document-sanity new-version --source proposal --strategy date      # → src/MMDDYYYY/
uv run document-sanity new-version --source manuscript --dry-run          # what it would copy
```

- Always pass `--source`. Without it the tool copies the "latest" folder,
  which is the newest dated name, or else the last alphabetically, and
  rarely the one you meant.
- `--name` sets the folder name. Without it, `--strategy` picks one: `date`
  (MMDDYYYY), `fun` (three random words) or `both` (the default:
  `10182026-elegant-crimson-fox`). Suggest a name that says what the version
  is for.
- It refuses to overwrite an existing folder, and records the lineage in
  `.version-log.json`.

## After

- Change the new folder only. Numbers that differ get edited in the new
  folder's `variables:` (`variables` mode); the old one keeps its values.
- `templates/` and `styles/` are shared. If the new version needs a different
  look, add a new template or styles name rather than editing the shared
  one.
- `uv run document-sanity check <new>`, and from then on pass
  `-V <new>` / `VERSION=<new>` to every command.

## Comparing versions

```bash
diff -ru src/manuscript src/10182026-resubmission | less
diff src/manuscript/docs/methods.md src/10182026-resubmission/docs/methods.md
```
