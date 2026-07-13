# second_brain

An **LLM-maintained knowledge wiki** for any domain you choose, built in the style of Andrej Karpathy's
knowledge system.

The core idea is an **inverted relationship with knowledge**: you don't organize, link, or maintain notes
by hand. You **drop in raw sources and ask questions** — an LLM (Claude Code) reads everything, writes the
concept articles, connects them, and keeps the whole thing coherent. You read and navigate the result in
**Obsidian**.

> Obsidian here is a *reader*, not a builder. Notes are created by Claude, not hand-authored.

---

## The pipeline

```
Clippings/  ──/compile──▶  Sources/ + Concepts/ + Maps/  ──/ask──▶  answers (filed back in)
   (raw in)                      (the wiki)                          ▲
                                      └──────────/lint──────────────┘
                                            (health checks)
```

1. **Raw in** — you clip a source into `Clippings/`.
2. **Compile** — Claude turns raw sources into a linked wiki.
3. **Navigate** — you browse in Obsidian (wikilinks, backlinks, graph).
4. **Ask** — questions answered *only* from your own vault, with citations.
5. **File back in** — useful answers become notes, so the base compounds.
6. **Lint** — periodic health check keeps it coherent (incl. stale-claim tracking).

---

## Folder layout

| Folder       | What's in it | Who writes it |
|--------------|--------------|---------------|
| `Clippings/` | **Raw input** — clipped articles, papers, notes. Immutable; never edited by the compiler. | You |
| `Sources/`   | One **summary note per source**: key claims, takeaways, links to the concepts it supports. | Claude |
| `Concepts/`  | **Atomic concept articles** — one idea per file. The heart of the wiki, cross-linked. | Claude |
| `Maps/`      | **Maps of Content** — hub notes grouping concepts by theme. `Maps/Index.md` is the entry point. | Claude |
| `tools/fetch/` | **Change-detection layer** — hashes each source in `Clippings/` against a manifest so *edited* sources get re-compiled, not just new ones. See below. | System |

`CLAUDE.md` holds the full conventions and rules Claude follows. You don't need to read it to use the
system — it's there so Claude has the right context automatically whenever it runs in this folder.

---

## Setup (one minute)

> **`second-brain` is the generic, blank template vault** — the canonical scaffolding. Don't fill it with
> content; clone it per context instead (`cp -R second-brain my-new-topic`, or use it as a GitHub
> *template repository*), then set that clone's Domain. Keep each real context in its **own repo**.

1. Open this folder as a vault in **Obsidian**, and open it in **Claude Code**.
2. **Set your domain:** edit the _Domain_ section near the top of `CLAUDE.md` to say what this vault is
   about (e.g. "machine learning research"). This tunes how concepts are extracted and named. Leave it
   generic to extract across any topic.
3. (Optional) Install the **Obsidian Web Clipper** browser extension to save web articles straight into
   `Clippings/` as markdown.

---

## Daily workflow

### 1. Add sources
Clip web articles with the Web Clipper, or drop any markdown, PDF, or text file into `Clippings/`.

### 2. Compile
In Claude Code, from this folder:

```
/compile
```

Claude reads every new clipping, writes a Source summary, extracts atomic Concepts (extending existing
ones instead of duplicating), links everything both ways, and slots each concept into a Map. It reports
what it created, plus any gaps, contradictions, or time-bound claims it noticed.

Restrict to specific sources with an argument, e.g. `/compile the Smith 2024 paper`. Passing an explicit
source now **re-reads and updates** its Source even if one already exists (re-running the conflict and
`⏳` rules and bumping `updated:`) — so an edited clipping no longer goes stale.

### Change detection (`tools/fetch/`)
`/compile` on its own only spots *new* clippings — an edited same-name source would be treated as
already-done and go stale. The fetch layer closes that gap. Run:

```
python3 tools/fetch/run.py            # hash Clippings/ vs the manifest, print what changed
python3 tools/fetch/run.py --dry-run  # same, but don't touch the manifest
```

It sha256-hashes every file in `Clippings/` against `tools/fetch/manifest.json` and prints the
**changed** set (new + content-changed), which you can hand straight to `/compile <changed>`. Unchanged
sources are skipped; upstream deletions are reported, never auto-applied. Sources are declared in
`tools/fetch/sources.yaml` — this template ships only the dependency-free `local` adapter (hashing files
already in `Clippings/`); remote adapters (GitHub, Confluence, …) and scheduled CI are a later phase and
plug into the same `adapters/` seam. No third-party Python packages required.

### 3. Browse
Open the vault in Obsidian. Start at `Maps/Index.md`, follow `[[wikilinks]]`, use **backlinks** to see what
references a concept, and the **graph view** to see the shape of what you know.

### 4. Ask
Query your accumulated knowledge:

```
/ask <your question>
```

Answers are drawn **only from this vault** (no open-web facts, no hallucination), cite the specific notes
used, and synthesize across sources — surfacing agreements, tensions, and gaps. Claude then offers to
**file the answer back into the wiki**, which is how the base compounds over time.

### 5. Lint (periodically)
```
/lint
```

A health check: broken links and stale frontmatter are fixed automatically; duplicate concepts,
contradictions (ranked by source recency when dated), provisional `⏳` claims, undated sources, and gaps
are reported for your review, with suggestions for what to clip next.

---

## Commands

These live in `.claude/commands/` and are **scoped to this folder** — they only exist when Claude Code
runs inside this vault.

| Command            | Does |
|--------------------|------|
| `/compile`         | Build/update the wiki from raw sources in `Clippings/`. |
| `/ask <question>`  | Answer from the vault, with citations; offer to file the answer back in. |
| `/lint`            | Health-check the wiki — orphans, broken links, duplicates, contradictions, stale claims, gaps. |

---

## Conventions (the short version)

- **Filenames are link targets.** Notes are named exactly as they're referred to, so `[[A Concept]]` just works.
- **One concept per note.** Five ideas in a source → five concept notes.
- **Merge, don't duplicate.** Existing concepts get extended, not re-created.
- **Everything links.** Sources → Concepts → Maps; no orphans.
- **Cite the vault, not the web.** `/ask` is grounded strictly in your notes.
- **Date your sources.** Filling `published:` lets the system rank conflicting sources by recency.
- **Time-bound claims get a `⏳`** and a row in `Maps/Time-Bound Claims.md` so they're re-verified later.

Full details are in `CLAUDE.md`.

---

## Getting started

1. Set your domain in `CLAUDE.md` (see Setup).
2. Clip a few sources into `Clippings/`.
3. Run `/compile`.
4. Run `/ask` against what you've built.

The vault starts empty (apart from this README, `CLAUDE.md`, the `Maps/` scaffolding, and the
`tools/fetch/` pipeline). Your first `/compile` will populate `Sources/`, `Concepts/`, and `Maps/` —
start at `Maps/Index.md`.
