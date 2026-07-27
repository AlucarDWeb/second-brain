---
description: Answer a question using only this vault's notes, with citations; offer to file the answer back in
---

Answer the following question **strictly from this vault** (Concepts/, Sources/, Maps/, Clippings/):

**$ARGUMENTS**

## Rules

1. **Vault-only.** Use only notes in this vault. Do **not** pull facts from the open web or from your own
   training knowledge. This keeps answers grounded in what the human has actually read.
2. **Retrieve — search-first.** Never read `Concepts/_INDEX.md` whole (it grows without bound), and never
   read folders broadly. Follow this order:
   1. **`rg` the index.** Extract the question's key terms (product names, code identifiers, plausible
      synonyms) and search them: `rg -i '<term>' Concepts/_INDEX.md`. Each matching line is
      self-contained (name · aliases · one-line definition) — that's the shortlist. Aliases are
      load-bearing, so try 2–4 term variants before concluding something isn't there. Read
      `Maps/<Theme>.md` (via `ls Maps/`) when the question spans a whole theme.
   2. **Read only the shortlisted Concepts** — usually 2–5 notes.
   3. **Follow links one hop, budgeted.** Pull in directly-linked related Concepts and the specific
      Source notes behind the claims you're using — aim for **≤ ~10 notes total**; go past that only
      when the question demonstrably needs more (say so in the answer). Don't transitively expand the
      graph.
   4. Only fall back to a broader `rg` across `Concepts/`/`Sources/` **bodies** if the index search
      comes up empty or the question isn't concept-shaped.
3. **Synthesize across notes.** The value is connecting ideas from multiple sources — point out agreements,
   tensions, and gaps between them, not just a single lookup.
4. **Cite.** Reference the specific notes used, e.g. `[[Concept]]` and `[[Source Note]]`, so the human can trace
   every claim back to a note.
5. **Admit gaps.** If the vault can't fully answer, say exactly what's missing and suggest what to clip next.
   Never fill the gap by inventing or web-searching.

## File back in

After answering, offer to **file the synthesis back into the wiki** (the compounding step): either as a new
Concept/Map note or appended to an existing one, per `CLAUDE.md` conventions. Do it if the human confirms.
