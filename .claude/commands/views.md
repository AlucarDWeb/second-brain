---
description: Regenerate the HTML visualization layer (views/) from the vault
---

Rebuild the standalone HTML visualization layer under `views/` from the current vault.

`/compile` already does this as its final step; run `/views` on its own when you want to refresh the
site without recompiling — e.g. after a `/lint` fix, a manual note edit, or to regenerate after pulling
changes.

## Steps

1. **Run the generator.** From the vault root, run `python3 generate_views.py`. It reads every note in
   `Concepts/`, `Sources/`, `Maps/` (skipping `_INDEX.md`), parses frontmatter + `[[wikilinks]]`, and
   derives:
   - `views/index.html` — force-directed graph of the whole vault (nodes colored by type, sized by link
     degree, searchable, click-to-open). Vanilla-canvas, no external dependencies.
   - `views/notes/<slug>.html` — one curated-typography page per note, with resolved wikilinks, a
     metadata panel, and backlinks.
   - `views/assets/app.css` + `views/assets/graph.js` — shared, local, offline.

2. **Report** the generator's summary line (note count + resolved links) and the path to open
   (`views/index.html`). If the run flags any unexpected drop in resolved links vs. note count, note it —
   it can signal broken wikilinks worth a `/lint`.

## Notes

- The vault is the **source of truth**; `views/` is fully derived. The generator wipes and rebuilds
  `views/` each run — never hand-edit anything under it.
- Zero third-party dependencies (Python 3 stdlib only); the output is fully offline and opens over
  `file://`.
