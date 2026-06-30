---
description: Health-check the wiki — orphans, broken links, duplicates, contradictions, time-bound claims, gaps
---

Run a health check over the wiki. Follow `CLAUDE.md` conventions. Optional focus: $ARGUMENTS

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

## Output

Group findings by severity:
- **Fixed automatically** (broken links, frontmatter, ⏳/tracker drift) — list what you changed.
- **Needs review** (duplicates, contradictions, time-bound claims likely stale, undated sources) — describe the issue and your recommendation.
- **Opportunities** (gaps, suggested new concepts/connections, what to clip next) — a short prioritized list.

Apply only mechanical fixes directly; pause for confirmation before merges or large restructures.
