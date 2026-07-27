---
description: Quick vault health snapshot — counts, unprocessed clippings, time-bound claims, recent activity
---

Report a quick status snapshot of the vault. **Read-only** — change nothing, bump nothing. This is
the cheap alternative to `/lint`: no duplicate/contradiction analysis, just the numbers.

## Steps

1. **Counts.** Count notes per folder: `Concepts/*.md` (excluding `_INDEX.md`), `Sources/*.md`,
   `Maps/*.md`.

2. **Unprocessed clippings.** From the vault root, run `python3 tools/fetch/run.py --dry-run`.
   Its stdout lists clippings that are new or content-changed since their hash was last recorded —
   i.e. clipped but not yet compiled. Empty output means the wiki is up to date with `Clippings/`.

3. **Time-bound claims.** Count tracked rows in `Maps/Time-Bound Claims.md`. If any exist, name
   the oldest (these are the `⏳` claims awaiting re-verification).

4. **Recent activity.** List notes whose `updated:` frontmatter falls within the last 7 days
   (search `updated:` across `Concepts/`, `Sources/`, `Maps/` and compare against today).

5. **Report.** A short table (counts, unprocessed, time-bound, recent) plus a one-line verdict.
   Suggest the follow-up only when warranted: unprocessed clippings → `/compile`; time-bound
   claims or a long gap since the last check → `/lint`.
