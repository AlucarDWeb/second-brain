---
name: lint
description: Health-check the wiki — orphans, broken links, duplicates, contradictions, time-bound claims, gaps
---

Run a health check over the wiki. Follow `CLAUDE.md` conventions. Optional focus: $ARGUMENTS

The lint is split in two: **mechanical checks run as a script** (deterministic, O(vault) in Python,
O(1) in context), and **judgment checks run here** (meaning-level duplicates, contradictions, gaps).
Never re-derive by hand what the script already computed.

## Part 1 — mechanical (script)

Run `python3 lint_mechanical.py --quiet` and relay its report. It covers broken wikilinks, orphans,
Concepts in no Map, Sources citing no Concept, frontmatter problems, undated sources,
⏳↔[[Time-Bound Claims]] drift, `_INDEX.md` drift, clippings↔sources reconciliation, and
scale-threshold flags.

Apply the mechanical fixes it points at directly:
- broken links → correct the target (or create a stub if the concept should exist);
- frontmatter → fill the missing field;
- index drift → `python3 generate_index.py`;
- ⏳ drift → add the missing tracker row, or move a finished row to [[Time-Bound Claims Archive]].
Re-run the script after fixing to confirm it comes back clean.

## Part 2 — judgment (LLM, pre-filtered)

These need meaning, not mechanics — but candidate *selection* for duplicates is mechanical and runs
as a script.

1. **Duplicate / near-duplicate concepts — `dedup_check.py`, deterministic.**
   Run `python3 dedup_check.py --audit` (unlinked suspect pairs, worst first) plus
   `python3 dedup_check.py --alias-gaps` and `--alias-collisions`. Lexical scoring over names and aliases,
   IDF-weighted from the corpus itself — no language assumption, no embeddings, seconds.
   For each candidate pair, open both notes and judge:
   - **same idea** → report; propose a merge — do NOT merge without human confirmation;
   - **distinct but related** → add `## Related` links both ways (mechanical — apply directly,
     bump `updated:`);
   - **genuinely unrelated** → leave it and note it; recurring noise means raise `--threshold`.
   An `--alias-gaps` hit is a defect on its own (a concept with <2 aliases is invisible to name dedup);
   an `--alias-collisions` hit means one alias points at two concepts — fix the alias, not the notes.
   Do **not** use `uv run semantic.py pairs` for this: measured on this vault, unrelated concepts sit at
   ~0.88 cosine and nothing real scores above 0.84, so it nominates 40 neighbours and finds no duplicate.
   Semantic `search --top 5` stays a *retrieval* aid inside `/ask`.

2. **Contradictions** — claims in the notes that disagree. Start with the `--audit`
   candidates from step 1 — similar-but-unlinked concepts are where contradictions hide. (Report with both sides quoted — human
   review.) Where both sources carry a `published:` date, note which is newer and recommend it as
   current; if undated, say you can't rank them. Record unresolved conflicts in
   [[Time-Bound Claims]].
3. **Stale time-bound claims** — read [[Time-Bound Claims]] (open rows only; resolved history lives in
   [[Time-Bound Claims Archive]]) and call out the rows most likely stale ("planned" features,
   "currently"/"for now" states, oldest `As of` dates). Recommend what to re-verify.
4. **Unsupported concepts** — Concept notes with an empty `## Sources`. (Report.)

5. **Gaps** — concepts referenced but never defined; questions the sources circle but never answer;
   obvious adjacent concepts missing. (Report; if useful, use web search to propose what to clip
   next — but do NOT add web content as fact; anything pulled in must first become a Source note via
   `/compile`.)

## Output

Group findings by severity:
- **Fixed automatically** (mechanical-script findings you fixed) — list what you changed, and confirm
  the script re-run is clean.
- **Needs review** (duplicates, contradictions, time-bound claims likely stale, undated sources) —
  describe the issue and your recommendation.
- **Opportunities** (gaps, suggested new concepts/connections, what to clip next) — a short
  prioritized list.

State which mode you used (whole-index or sharded, and which Maps). Apply only mechanical fixes
directly; pause for confirmation before merges or large restructures.
