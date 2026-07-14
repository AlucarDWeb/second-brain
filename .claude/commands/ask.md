---
description: Answer a question using only this vault's notes, with citations; offer to file the answer back in
---

Answer the following question **strictly from this vault** (Concepts/, Sources/, Maps/, Clippings/):

**$ARGUMENTS**

## Rules

1. **Vault-only.** Use only notes in this vault. Do **not** pull facts from the open web or from your own
   training knowledge. This keeps answers grounded in what the human has actually read.
2. **Retrieve — index-first.** Don't grep the whole vault or read broadly. Follow this order:
   1. **Read `Concepts/_INDEX.md`** (the generated dedup index: one line per concept — name · aliases ·
      one-line definition). It's small and cheap; use it as the map of what exists. Read `Maps/Index.md`
      too when the question spans a theme.
   2. **Shortlist by name/alias/definition.** Match the question against the index entries (titles *and*
      aliases — aliases are load-bearing) to pick the handful of Concepts that actually matter.
   3. **Read only those Concepts**, then follow their wikilinks and `## Sources` to pull in connected
      context (related Concepts, the Source notes behind each claim).
   4. Only fall back to a broad `Concepts/`/`Sources/` search if the index shortlist comes up empty or the
      question clearly isn't concept-shaped. If `_INDEX.md` is missing or stale, search directly.
3. **Synthesize across notes.** The value is connecting ideas from multiple sources — point out agreements,
   tensions, and gaps between them, not just a single lookup.
4. **Cite.** Reference the specific notes used, e.g. `[[Concept]]` and `[[Source Note]]`, so the human can trace
   every claim back to a note.
5. **Admit gaps.** If the vault can't fully answer, say exactly what's missing and suggest what to clip next.
   Never fill the gap by inventing or web-searching.

## File back in

After answering, offer to **file the synthesis back into the wiki** (the compounding step): either as a new
Concept/Map note or appended to an existing one, per `CLAUDE.md` conventions. Do it if the human confirms.
