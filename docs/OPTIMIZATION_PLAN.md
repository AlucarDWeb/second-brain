# Optimization Plan for knowledge-brain Vault (v2)

**Status:** Candidate
**Date:** 2026-07-27
**Scope:** Only improvements verified against the actual code
**Constraints:** Zero Python dependencies, no test suite, no CI/CD, no remote adapters

---

## Context

v1 of this plan was written from the directory layout rather than the file contents. An audit
against the code dropped roughly half of it: several "problems" don't exist (the scripts already
print progress; the manifest is empty because `Clippings/` is empty, not because of a bug), and two
fixes would have broken working behavior (`include_extensions` contradicts the intentionally
extension-agnostic glob in `sources.yaml`; the proposed schema validator required a `path` key the
real config doesn't use). What follows is only what survived, each item verified in the code.

Total effort: **~45 minutes.**

---

## 1. Untrack generated/local files from git

**Verified problem:** `git ls-files` shows these tracked despite `.gitignore` rules:

- `tools/fetch/manifest.json` — local change-detection state. It describes files in `Clippings/`,
  which is itself gitignored, so committing it records state about content git can't see, and it
  will churn on every fetch.
- `tools/fetch/adapters/__pycache__/*.pyc` — `.gitignore` has `__pycache__/`, but gitignore never
  untracks files that were already committed.

**Fix:**

```bash
# .gitignore — add:
tools/fetch/manifest.json

# then untrack (files stay on disk):
git rm --cached tools/fetch/manifest.json
git rm -r --cached tools/fetch/adapters/__pycache__
```

Nitpick while in `.gitignore`: the comment says "app.json … IS committed" but `.obsidian/app.json`
is listed right below it. Fix the comment or the rule — they currently contradict each other.

## 2. Report unresolved wikilinks from `generate_views.py`

**Verified problem:** the generator already resolves every wikilink (`resolve_links`,
`generate_views.py:131`) and already styles broken ones red in the HTML (`generate_views.py:178`)
— but it never *reports* them. The only way to notice a broken link today is to click around the
generated site or run a full `/lint`.

**Fix:** after generation, print the unresolved links alongside the existing summary line
(`generate_views.py:818`):

```
Generated views/ from 42 notes (117 resolved links).
  3 unresolved links:
    - Concepts/Foo.md -> [[Bar]]
    - ...
```

No flag needed — the data is already computed, so always print it. No non-zero exit code: there is
no CI to consume it (per constraints), and a broken link should not abort view generation.

## 3. `tools/fetch/README.md`

**Verified problem:** the module docstrings in `run.py`, `local.py`, `normalize.py`, and the
`sources.yaml` header are individually thorough, but there is no single entry point tying them
together.

**Fix:** a short README (half a page) covering:

- The loop: `sources.yaml` → adapter → sha256 vs `manifest.json` → CHANGED list for `/compile`.
- What `manifest.json` is (local state, gitignored, safe to delete — next run rebuilds it; the
  only cost is one full re-report of CHANGED).
- How to add a remote adapter (drop a module in `adapters/`, register in `ADAPTERS` in `run.py`,
  add a block in `sources.yaml`) — pointing at the existing docstrings for detail.
- Known limitation: removing/commenting a source block in `sources.yaml` makes all its manifest
  entries report as "upstream deletions" on the next run (reported only, never deleted).

## 4. `/status` command (`.claude/commands/status.md`)

**Purpose:** quick vault health snapshot without the cost of a full `/lint`. Everything it needs
already exists:

- **Counts** — Concepts (excluding `_INDEX.md`), Sources, Maps.
- **Unprocessed clippings** — `python3 tools/fetch/run.py --dry-run` (the flag already exists;
  its CHANGED output is exactly "clipped but not yet compiled").
- **Time-bound claims** — row count from `Maps/Time-Bound Claims.md`.
- **Recent activity** — notes with `updated:` within the last 7 days.

Read-only; changes nothing.

---

## Files to modify

| File | Change |
|------|--------|
| `.gitignore` | Add `tools/fetch/manifest.json`; fix `.obsidian/app.json` comment/rule contradiction |
| (git index) | `git rm --cached` manifest.json and `__pycache__` |
| `generate_views.py` | Print unresolved-links report after generation |
| `tools/fetch/README.md` | NEW — entry-point doc |
| `.claude/commands/status.md` | NEW — quick stats command |

---

## Dropped from v1 (with reasons)

| v1 item | Verdict |
|---------|---------|
| Populate manifest | No-op — `Clippings/` contains only `.gitkeep`; the empty manifest is correct, not a bug |
| Extension filtering (`include_extensions`) | Rejected — contradicts the documented extension-agnostic design in `sources.yaml`, assumed a `path:` key that doesn't exist, and would make edited PDFs invisible to change detection (the exact gap the tool closes) |
| Schema validation for `sources.yaml` | Rejected as specced — `REQUIRED_FIELDS = ["id", "type", "path"]` fails the current valid config (which uses `glob`). Revisit only when remote adapters land, validating `type` against `ADAPTERS` and letting each adapter declare its own keys |
| `--verbose` flags | Rejected — false premise; `run.py` prints per-file `[new]/[changed]` lines + summary (`run.py:193,212-227`), `generate_views.py` prints a summary (`:818`) |
| Streaming hash | Deferred — real but not the 2-line patch specced: hashing happens in `run.py:173` on `item.content`, and the adapter loads full bytes into `FetchedItem` regardless, so it requires changing the `FetchedItem` contract. Revisit if/when large binaries actually land in `Clippings/` |
| `/reindex` command | Rejected — built for "manual edits" to `Concepts/`, a workflow the system explicitly excludes (notes are LLM-authored; `_INDEX.md` is regenerated by `/compile` and reconciled by `/lint`) |
