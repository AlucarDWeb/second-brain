# Optimization Plan for knowledge-brain Vault

**Status:** Approved  
**Date:** 2026-07-25  
**Scope:** Comprehensive improvements (performance, robustness, commands)  
**Constraints:** Zero Python dependencies, no test suite, no CI/CD, no remote adapters  

---

## Executive Summary

The vault has a solid foundation (zero dependencies, clean architecture, coherent command system) with immediate gaps that should be fixed. This plan covers Phase 1 (immediate fixes), Phase 2 (performance), and Phase 3 (command enhancements).

---

## Phase 1: Immediate Fixes

### 1.1 Add manifest.json to .gitignore

**Problem:** `manifest.json` tracks local change state and shouldn't be committed.

**Fix:**
```gitignore
# In .gitignore
tools/fetch/manifest.json
```

### 1.2 Populate Manifest

**Problem:** `tools/fetch/manifest.json` is empty `{}` — every run hashes all clippings as if new.

**Fix:**
```bash
cd tools/fetch && python3 run.py
```

### 1.3 Add File Type Filtering

**Problem:** `local` adapter hashes PDFs, EPUBs, images byte-by-byte even though `/compile` can only read text files.

**Fix:** Add `include_extensions` to `sources.yaml`:
```yaml
sources:
  - id: local_clippings
    type: local
    path: ../Clippings
    include_extensions: [.md, .txt]
```

Modify `adapters/local.py` to filter by extension before hashing.

### 1.4 Create Documentation

**Problem:** `tools/fetch/` has no README.

**Fix:** Create `tools/fetch/README.md` explaining:
- How `run.py` works
- What `manifest.json` tracks
- How to add remote adapters (future reference)

---

## Phase 2: Performance Improvements

### 2.1 Streaming Hash for Large Files

**Problem:** `local.py` uses `p.read_bytes()` — loads entire file into memory.

**Fix:**
```python
def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
```

**Impact:** Negligible for small files, essential for large PDFs.

### 2.2 Broken Link Detection

**Problem:** Broken wikilinks only caught at `/lint` time.

**Fix:** Add `--check-links` flag to `generate_views.py`:
```bash
python3 generate_views.py --check-links
# Exits non-zero with list of unresolved [[links]]
```

### 2.3 Schema Validation for sources.yaml

**Problem:** Typos in YAML are silently ignored.

**Fix:** Add validation in `run.py`:
```python
REQUIRED_FIELDS = ["id", "type", "path"]

def validate_source(src: dict) -> bool:
    return all(k in src for k in REQUIRED_FIELDS)
```

### 2.4 Verbose Mode

**Problem:** Scripts run silently — no progress indication.

**Fix:** Add `--verbose` flag to both scripts:
- `python3 tools/fetch/run.py --verbose`
- `python3 generate_views.py --verbose`

Logs per-file processing and summary statistics.

---

## Phase 3: Command Enhancements

### 3.1 `/status` Command

**Purpose:** Quick vault statistics without full `/lint`.

**Output:**
- Concept/Source/Map counts
- Unprocessed clippings count (from manifest diff)
- Time-bound claims needing review
- Recent changes (last 7 days, from `updated:` frontmatter)

### 3.2 `/reindex` Command

**Purpose:** Regenerate `_INDEX.md` after manual edits.

**Behavior:**
- Scan `Concepts/` folder
- Rebuild `Concepts/_INDEX.md` with current concept list
- Bump `updated:` date

---

## Files to Modify

| File | Changes |
|------|---------|
| `.gitignore` | Add `tools/fetch/manifest.json` |
| `tools/fetch/manifest.json` | Populate via `run.py` |
| `tools/fetch/sources.yaml` | Add `include_extensions` |
| `tools/fetch/adapters/local.py` | Streaming hash + extension filter |
| `tools/fetch/run.py` | Schema validation + `--verbose` |
| `generate_views.py` | `--check-links` flag + `--verbose` |
| `.claude/commands/status.md` | NEW — quick stats command |
| `.claude/commands/reindex.md` | NEW — regenerate index command |
| `tools/fetch/README.md` | NEW — documentation |

---

## Implementation Priority

| Phase | Effort | Impact |
|-------|--------|--------|
| **Phase 1** | ~30 min | High — fixes immediate gaps |
| **Phase 2** | ~1-2 hrs | Medium — performance robustness |
| **Phase 3** | ~30 min | Medium — workflow convenience |

---

## Skipped Items (Per Constraints)

- Test suite (`pytest`, `unittest`)
- Remote adapters (GitHub, Confluence, web)
- CI/CD (GitHub Actions)
- Semantic search (requires dependencies)
- New Python dependencies

---

## Open Items

- [ ] Confirm extension filter: `.md` only, or `.md` + `.txt`?
- [ ] Confirm verbose output granularity (per-file vs summary)