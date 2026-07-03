---
description: Health-check the wiki — orphans, broken links, duplicates, contradictions, time-bound claims, gaps
---

Run a health check over the wiki. Follow `CLAUDE.md` conventions. Optional focus: $ARGUMENTS

**Start by reading `Concepts/_INDEX.md`** — the generated one-line-per-concept index (name · aliases ·
definition). Use it as the working set for the whole-vault checks below instead of loading every note,
and reconcile it against the actual `Concepts/` folder (see check 10). `_INDEX.md` is itself an index,
not a concept — exclude it from orphan/unsupported/frontmatter checks.

**Scale the whole-vault checks (4 & 6) by sharding, not brute force.** Duplicate and contradiction
detection are inherently all-pairs. While the concept count is small enough to hold at once, compare
across the full `_INDEX.md`. Once it isn't (**~150+ concepts**), shard: run duplicates/contradictions
**within each Map first** (concepts in the same theme are the likely collisions), then do a lighter
cross-Map pass driven by the `_INDEX.md` one-liners. Say in the output which mode you used.

## Checks

1. **Broken wikilinks** — `[[links]]` pointing to non-existent notes. (Mechanical → fix directly: create a stub or correct the target.)
2. **Orphans** — notes with no inbound or outbound links; Concepts not listed in any Map; Sources linking no Concept. (Report + propose links.)
3. **Missing/stale frontmatter** — missing `type`, missing `created`, or `updated:` older than the last edit. (Mechanical → fix directly.)
4. **Duplicate / near-duplicate concepts** — concept notes covering the same idea under different names. (Report; propose a merge — do NOT merge without human confirmation.)
5. **Unsupported concepts** — Concept notes with an empty `## Sources`. (Report.)
6. **Contradictions** — Sources/Concepts that disagree. (Report with both sides quoted — human review.) Where both sources carry a `published:` date, note which is newer and recommend it as current; if undated, say you can't rank them. Record unresolved conflicts in [[Time-Bound Claims]].
7. **Time-bound claims** — resurface every `⏳`-marked line and every row in [[Time-Bound Claims]] for re-verification. Flag any `⏳` line missing from the tracker (or tracker rows whose `⏳` was removed from the note) as drift — mechanical → reconcile directly. Call out claims most likely stale (e.g. "planned" features, "currently"/"for now" states).
8. **Undated sources** — Source notes with a blank `published:`. (Report — they block conflict ranking; recommend capturing the Confluence last-modified date.)
9. **Gaps** — concepts referenced but never defined; questions the sources circle but never answer; obvious adjacent concepts missing. (Report; if useful, use web search to propose what to clip next — but do NOT add web content as fact; anything pulled in must first become a Source note via `/compile`.)
10. **Concept index drift** — reconcile `Concepts/_INDEX.md` against the actual `Concepts/` folder: every
    concept present exactly once, aliases and one-line definitions matching the notes, correct count.
    (Mechanical → regenerate the index directly.)
11. **Map-hub scale** — if `Maps/` has grown toward **~20 Maps** and `Maps/Index.md` is a long flat list,
    flag that a domain-map tier is now warranted (see `/compile` step 6) and propose the grouping. (Report — this is a restructure, so recommend, don't apply.)

## Output

Group findings by severity:
- **Fixed automatically** (broken links, frontmatter, ⏳/tracker drift, concept-index drift) — list what you changed.
- **Needs review** (duplicates, contradictions, time-bound claims likely stale, undated sources) — describe the issue and your recommendation.
- **Opportunities** (gaps, suggested new concepts/connections, what to clip next) — a short prioritized list.

Apply only mechanical fixes directly; pause for confirmation before merges or large restructures.
