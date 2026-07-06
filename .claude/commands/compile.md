---
description: Read raw sources in Clippings/ and build/update the wiki (Sources, Concepts, Maps)
---

Compile the knowledge wiki from raw sources. Follow `CLAUDE.md` conventions exactly.

Optional argument — restrict to specific sources: $ARGUMENTS
(If empty, process every clipping that does not yet have a corresponding note in `Sources/`.)

## Steps

1. **Find work.** List `Clippings/`. For each clipping, check whether a matching note exists in `Sources/`
   (match on title/`clipping:` frontmatter). Build the set of *new or changed* sources to process.
   If `$ARGUMENTS` is given, restrict to those. Report what you'll process before doing it.

2. **Read each new source** fully from `Clippings/`.

3. **Write a Source note** in `Sources/` per the template in `CLAUDE.md` (summary, key claims, concepts touched,
   frontmatter with url/author/published pulled from the clipping's frontmatter).

4. **Extract atomic concepts.** For each distinct idea in the source:
   - **Dedup lookup — read `Concepts/_INDEX.md` first.** It is a generated one-line-per-concept
     index (name · aliases · definition). Scan it — names **and** aliases — for the incoming idea
     before anything else. This is what keeps dedup working as the vault grows past what fits in one
     read. If the index looks stale or missing, fall back to scanning `Concepts/` filenames + aliases
     directly (and regenerate the index in step 7).
   - If the index surfaces a candidate, open that Concept note to confirm before extending.
   - **If it exists:** extend it — add nuance, add the new Source to its `## Sources`, add new `## Related`
     links, bump `updated:`. Do **not** create a duplicate.
   - **If it's new:** create `Concepts/<Concept Name>.md` per the template.
   - Keep each note to a single concept. Five ideas → five notes.
   - **Conflict check (do not silently overwrite):** if a new claim contradicts what an existing Concept
     already says, stop and surface it with both sides quoted. If both sources have a `published:` date,
     recommend the newer as current and update the note (noting the supersession + bumping `updated:`);
     if either is undated, flag the disagreement but state you can't rank it. Log unresolved conflicts in
     [[Time-Bound Claims]].
   - **Mark time-bound claims:** if a claim is explicitly provisional (*currently, planned, for now, not yet,
     in a near future, …*), prefix that line with `⏳` and add a row to [[Time-Bound Claims]]
     (`Maps/Time-Bound Claims.md`). Capture the source's `published:` (Confluence last-modified) so the
     claim can later be re-verified and ranked.

5. **Wire links both ways.** Every Source links its Concepts; every Concept lists its Sources and related Concepts.

6. **Update Maps.** Place each concept under at least one Map in `Maps/` (create a thematic Map if none fits).
   Update `Maps/Index.md` so every Map and major concept is reachable from it.
   - **Map tiering (scales the hub).** `Maps/Index.md` is meant to be a scannable entry point, not a
     directory listing. While there are **≤ ~15 themed Maps**, keep Index a flat list of them. Once Maps
     approach **~20**, introduce a **domain-map tier**: group themed Maps under a few domain Maps and make
     `Maps/Index.md` point only at the domain Maps. Don't create domain Maps prematurely — only when the
     flat list stops being scannable.

7. **Regenerate `Concepts/_INDEX.md`.** After creating/extending concepts, rewrite the generated dedup
   index so it reflects the current set: one line per Concept — `**[[Name]]** · aliases · one-line definition`,
   sorted, with an updated count and `updated:` date. `_INDEX.md` is **not itself a concept** — never link
   to it from Sources/Maps and never treat it as a note to compile.

8. **Regenerate the HTML visualization layer.** After all notes, Maps, and `_INDEX.md` are written,
   rebuild `views/` from the vault by running `python3 generate_views.py` from the vault root. This
   derives the standalone graph + per-note pages from the current frontmatter and wikilinks — the vault
   stays the source of truth; `views/` is wiped and rebuilt each run, so never hand-edit it. Confirm the
   run's summary line (note count + resolved links) and surface it in the report. If nothing was compiled
   in step 1 (no new/changed sources), skip this step.

9. **Report:** new Sources, new Concepts, extended Concepts, new/updated Maps, whether `views/` was
   regenerated (with its count), and any **gaps or contradictions** you noticed (for `/lint` follow-up).
   Do not invent facts — only use what the sources say.

Never modify files in `Clippings/`.
