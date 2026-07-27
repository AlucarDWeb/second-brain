# knowledge_brain — an LLM-maintained knowledge wiki

This is a **Karpathy-style knowledge system**: a personal wiki that can hold **any knowledge domain you
choose** (see _Domain_ below). The defining idea is an **inverted relationship with knowledge** — the
human dumps raw sources in; **the LLM (you) does the connecting, writing, and maintenance.** The human
asks questions; you keep the wiki coherent.

The human reads and navigates this vault in **Obsidian**. Obsidian here is a *reader*, not a builder —
notes are created and maintained by you (Claude), not hand-authored in the app.

## Domain

> **Set this once.** Replace this line with the subject this vault is about — e.g. "machine learning
> research", "constitutional law", "personal finance", "company X engineering docs". The domain tunes how
> `/compile` names and groups concepts. If left generic, extract whatever concepts the sources contain
> across any topic.

## The pipeline

```
Clippings/  ──/compile──▶  Sources/ + Concepts/ + Maps/  ──/ask──▶  answers (filed back in)
   (raw in)                      (the wiki)                          ▲
                                      └──────────/lint──────────────┘
                                            (health checks)
```

1. **Raw in** — the human drops sources into `Clippings/` (via the Obsidian Web Clipper, or any markdown/PDF/text).
2. **Compile** (`/compile`) — you read raw sources, write a per-source summary, extract atomic concepts, and link everything.
3. **Navigate** — the human browses Concepts/Maps in Obsidian via wikilinks, backlinks, and the graph.
4. **Ask** (`/ask`) — questions answered **only from this vault**, with citations. No open-web hallucination.
5. **File back in** — useful answers/syntheses are saved back as notes, so the base compounds.
6. **Lint** (`/lint`) — periodic health check: orphans, broken links, duplicate concepts, gaps, contradictions, stale claims.

## Directory layout

| Folder       | Role | Authored by |
|--------------|------|-------------|
| `Clippings/` | **Raw input.** Untouched source material — clipped articles, papers, notes. Read-only to the compiler. | Human |
| `Sources/`   | One **summary note per raw source**: key claims, takeaways, links to the concepts it supports. | You |
| `Concepts/`  | **Atomic concept articles** — one idea per file. The heart of the wiki. Linked to each other and to Sources. `Concepts/_INDEX.md` is a generated dedup index (not a concept). | You |
| `Maps/`      | **Maps of Content (MOCs)** — index/hub notes that group concepts by theme. `Maps/Index.md` is the top-level entry point. | You |

Never edit files in `Clippings/` — it's the immutable record of what was actually read.

## Note conventions

**Filenames are the link targets.** Obsidian wikilinks resolve by filename, so name files exactly as the
concept/source is referred to. Use Title Case, spaces allowed, no path prefix in links (`[[A Concept Name]]`).

### Concept note (`Concepts/<Concept Name>.md`)
```markdown
---
type: concept
tags: []
aliases: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <Concept Name>

One-paragraph definition in your own words.

## Key points
- ...

## Related
- [[Another Concept]] — how it relates
- [[A Contrasting Concept]] — tension/contrast

## Sources
- [[Source Note Title]]
```

### Source note (`Sources/<Source Title>.md`)
```markdown
---
type: source
url: <original url if any>
author: <author>
published: YYYY-MM-DD   # date the source was authored/last-modified — NOT the clip date
clipping: "[[original clipping filename]]"
created: YYYY-MM-DD     # date you clipped/compiled it
---

# <Source Title>

> One-line what-this-is.

## Summary
2–4 sentences.

## Key claims
- Claim → supports [[Concept]]

## Concepts introduced / touched
- [[Concept A]], [[Concept B]]
```

**`published:` is the recency signal — capture it.** It is what lets conflict detection decide which of two
disagreeing sources supersedes the other. Use the source's authored/published date (for a wiki page, its
**last-modified** date; for an article, the byline date). If the clipping's frontmatter has it blank and you
can't determine it, leave it blank and note "undated source" when reporting conflicts (you can flag the
disagreement but not rank it). `created:` is just the clip date and must never be used as a recency proxy.

### Map note (`Maps/<Theme>.md`)
```markdown
---
type: map
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <Theme>

Short framing of the theme.

## Concepts
- [[Concept A]]
- [[Concept B]]
```

## Rules of the system

- **Atomicity** — one concept per Concept note. If a source raises five ideas, that's five concept notes (new or existing).
- **Merge, don't duplicate** — before creating a concept, `rg -i` the incoming idea's plausible names against `Concepts/_INDEX.md` (the generated dedup index — see below); each hit is a self-contained line. Extend the existing note and add the new source rather than making a near-duplicate. Surface suspected duplicates during `/lint`.
- **Aliases are load-bearing** — the `aliases:` field is what lets dedup work by name instead of full-text scan. Keep it complete: every plausible other name, abbreviation, code identifier, or phrasing for the concept goes in `aliases`. As the vault grows this is the single most important habit for keeping duplicates out.
- **Everything links** — every Source links the Concepts it supports; every Concept lists its Sources and related Concepts; every Concept belongs to at least one Map. No orphans.
- **`## Sources` caps at ~10** — a Concept's source list keeps the most significant and most recent sources up to ~10 entries, ending with `- _Full provenance: all Sources citing this concept are in the backlinks panel._` Obsidian's backlinks show every citing Source automatically; the in-note list is a curation, not a ledger, and provenance must not outgrow content.
- **Cite the vault, not the web** — `/ask` answers strictly from notes in this vault and cites the Source/Concept notes used. If the vault can't answer, say so explicitly (and optionally propose what to clip next). Web search is only for `/lint` gap-filling, and anything pulled in must be saved as a Source first.
- **Bump `updated:`** whenever you change a note.
- **Surface, don't silently fix** — when `/lint` finds contradictions or gaps, report them for human review before large changes; small mechanical fixes (broken links, missing frontmatter) can be applied directly.
- **Mark time-bound claims** — when a source states something explicitly provisional (wording like *currently, right now, for now, planned, will be, not yet, in a near future*), append a `⏳` marker to that line in the Concept note, e.g. `- ⏳ The new pricing tier is planned for next quarter.` Every `⏳` line must also be tracked in [[Time-Bound Claims]] (`Maps/Time-Bound Claims.md`) so `/lint` can resurface it for re-verification. When a later source confirms the claim changed, update the note, bump `updated:`, remove the `⏳`, and move its tracker row to [[Time-Bound Claims Archive]] — the live tracker holds only open claims.
- **Conflict-aware compile** — when a new source asserts something that contradicts an existing Concept, **never silently overwrite**. Report the conflict with both sides quoted. If both sources have a `published:` date, recommend the newer one as current (and update the note, noting the supersession); if either is undated, flag the disagreement but state you can't rank it. Record unresolved conflicts in [[Time-Bound Claims]].

## Scaling — how the structure holds as notes grow

The vault lives on disk but is maintained through a context window, so the real limit isn't disk size —
it's how much the LLM can see at once. The governing principle: **mechanical O(vault) work runs in
Python scripts (O(1) context); the LLM does only judgment** (meaning-level dedup, contradictions, gaps,
synthesis). These mechanisms keep it graceful:

- **`Concepts/_INDEX.md` — the script-generated dedup index.** One line per concept (name · aliases ·
  one-line definition). It is derived deterministically by `python3 generate_index.py` from each
  Concept's filename, `aliases:`, and the first sentence of its definition paragraph — so write that
  first sentence to stand alone. **Never hand-write index lines; never read the index whole**: `rg -i`
  names/aliases against it and consume only the matching lines. `/compile` runs the generator after
  each batch. It is **not a concept** — never link to it, never compile it.
- **Alias discipline** — see the rule above. Aliases are what make the index a reliable dedup key.
- **Mechanical lint is a script.** `python3 lint_mechanical.py` computes broken links, orphans,
  frontmatter problems, undated sources, ⏳↔tracker drift, index drift, clippings↔sources
  reconciliation, and scale-threshold flags — in seconds, with zero vault reads in context. `/lint`
  runs it first and keeps only the judgment checks.
- **Sharded `/lint` judgment checks** — duplicate/contradiction detection is all-pairs. Under ~150
  concepts, compare across the whole index at once; past that (the script flags it), shard **within
  each Map** first, then a lighter cross-Map pass. Never whole-vault at once once sharding kicks in.
- **`## Sources` caps at ~10** per Concept (see rule above) — the append-only growth vector on hot
  concepts; backlinks carry full provenance for free.
- **[[Time-Bound Claims]] stays open-only** — resolved rows move to [[Time-Bound Claims Archive]], so
  the file every compile/status touches doesn't grow with history.
- **Map tiering** — `Maps/Index.md` stays a flat list while there are ≤ ~15 themed Maps. Approaching ~20,
  introduce a **domain-map tier** (a few domain Maps grouping the themed ones; Index points only at
  domains). Don't build the tier before the flat list stops being scannable.
- **`views/` is derived and not committed** — regenerate on demand with `/views`
  (`python3 generate_views.py`); never hand-edit it.

Remaining thresholds: **~150 concepts** → `/lint` sharding becomes mandatory; **~20 Maps** → add the
domain tier. Everything else (index search, mechanical lint, source caps) is already the standing
regime — search-first is the entry step for `/ask` and `/compile` dedup at any vault size.

## Commands (scoped to this vault)

These live in `.claude/commands/` and only exist when Claude runs in this folder:

- **`/compile`** — read new/changed raw sources and build/update the wiki.
- **`/lint`** — health check: orphans, broken links, duplicate concepts, gaps, contradictions, stale claims.
- **`/ask <question>`** — answer a question from the vault, with citations; offer to file the answer back in.
- **`/status`** — cheap read-only snapshot: counts, unprocessed clippings, open time-bound claims, recent activity.
- **`/views`** — regenerate the HTML visualization layer (`views/`) and open it.
