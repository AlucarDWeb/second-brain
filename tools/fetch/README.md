# tools/fetch — change detection for the compile pipeline

Answers one question cheaply: **which clippings are new or edited since the last run?** — so
`/compile` (and, later, a scheduled workflow) only touches what actually changed.

```
sources.yaml ──▶ adapter ──▶ sha256 vs manifest.json ──▶ CHANGED list ──▶ /compile <CHANGED>
```

## Usage

```bash
python3 tools/fetch/run.py            # record hashes, print CHANGED
python3 tools/fetch/run.py --dry-run  # report CHANGED without writing anything
```

CHANGED (new + content-changed clipping basenames) is printed to stdout and, when
`$GITHUB_OUTPUT` is set, emitted as `changed=` / `changed_count=` for workflow use.

## The pieces

- **`sources.yaml`** — declarative list of sources. This build ships only the `local` type,
  which hashes files already in `Clippings/` (see its header comment for the supported YAML
  subset — PyYAML is used if installed, never required).
- **`adapters/local.py`** — reads clipping bytes, never writes (`Clippings/` is the immutable
  raw record per CLAUDE.md). Content-hashing is what makes an *edited* clipping re-detected,
  not just a new one.
- **`normalize.py`** — frontmatter injection for *remote* adapters that create new clipping
  bytes. Unused by the local adapter, by design.
- **`manifest.json`** — local state: `source_id → {sha256, upstream_modified, clipping,
  fetched_at}`. Gitignored. Safe to delete: the next run rebuilds it; the only cost is one
  full re-report of everything as CHANGED.

## Adding a remote adapter (Phase 1+)

Drop a module in `adapters/` exposing `fetch(cfg, vault_root) -> list[FetchedItem]`, register
it in `ADAPTERS` in `run.py`, and add a block in `sources.yaml`. Remote adapters return
`write=True` items (run.py writes them into `Clippings/`) and should call
`normalize.ensure_frontmatter` so the compiler gets `url`/`published`/`created`. Commented-out
stub blocks in `sources.yaml` show the intended shapes.

## Known limitations

- Removing or commenting out a source block in `sources.yaml` makes all its manifest entries
  report as "upstream deletions" on the next run. Deletions are reported only — never
  auto-removed.
- Hashing loads each file fully into memory (`FetchedItem.content` carries the bytes).
  Irrelevant at current sizes; revisit if large binaries land in `Clippings/`.
