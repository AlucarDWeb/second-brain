#!/usr/bin/env python3
"""Mechanical vault lint — every check here is deterministic and O(vault) in
Python so the LLM never has to walk the vault for them. `/lint` runs this first
and keeps only the judgment checks (duplicate meaning, contradictions, gaps).

Checks:
  1. Broken wikilinks (targets resolving to no note title, alias, or clipping)
  2. Orphans — no links at all; Concepts in no themed Map; Sources citing no Concept
  3. Frontmatter — missing/blank required fields, bad date formats, undated sources
  4. ⏳ markers ↔ Time-Bound Claims tracker reconciliation (note-level)
  5. Concepts/_INDEX.md drift (vs generate_index.py output)
  6. Clippings ↔ Sources reconciliation (unprocessed clippings, broken `clipping:` pointers)
  7. Scale thresholds (lint sharding, Map tiering)

Always exits 0 — it reports; humans/the LLM decide. `--quiet` prints only
sections with findings plus the summary.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_views import (  # noqa: E402
    WIKILINK_RE,
    load_notes,
    parse_frontmatter,
    wikilink_target,
)
from generate_index import build_index  # noqa: E402

VAULT = Path(__file__).resolve().parent
CLIPPINGS = VAULT / "Clippings"
TRACKER = VAULT / "Maps" / "Time-Bound Claims.md"
TRACKER_ARCHIVE = VAULT / "Maps" / "Time-Bound Claims Archive.md"
INDEX = VAULT / "Concepts" / "_INDEX.md"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Maps that are trackers/hubs, not thematic MOCs — membership in them doesn't
# make a Concept "mapped".
NON_THEMED_MAPS = {"Index", "Time-Bound Claims", "Time-Bound Claims Archive"}

REQUIRED_FM = {
    "concept": ["type", "created", "updated"],
    "source": ["type", "created", "clipping"],
    "map": ["type", "created", "updated"],
}
DATE_FIELDS = ["created", "updated", "published"]


def section(title: str, items: list[str], quiet: bool) -> int:
    if not items and quiet:
        return 0
    status = f"{len(items)} finding(s)" if items else "ok"
    print(f"\n== {title} — {status}")
    for it in items:
        print(f"   {it}")
    return len(items)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quiet", action="store_true", help="only print sections with findings")
    args = ap.parse_args()

    notes, alias_index = load_notes()
    clipping_files = [p for p in CLIPPINGS.iterdir() if p.is_file() and not p.name.startswith(".")]
    clipping_stems = {p.stem for p in clipping_files}
    clipping_names = {p.stem: p.name for p in clipping_files}
    valid_targets = {t.lower() for t in notes} | set(alias_index) | {
        s.lower() for s in clipping_stems
    }

    outbound: dict[str, set[str]] = defaultdict(set)   # title -> resolved note targets
    inbound: dict[str, set[str]] = defaultdict(set)
    broken: list[str] = []
    for title, note in notes.items():
        for raw in WIKILINK_RE.findall(note["body"]):
            target = wikilink_target(raw)
            low = target.lower()
            if low in alias_index:
                resolved = alias_index[low]
                outbound[title].add(resolved)
                inbound[resolved].add(title)
            elif low not in valid_targets:
                broken.append(f"{note['folder']}/{title}.md → [[{target}]]")

    findings = 0
    findings += section("1. Broken wikilinks", broken, args.quiet)

    # ---- 2. Orphans -------------------------------------------------------
    orphans: list[str] = []
    unmapped: list[str] = []
    citeless: list[str] = []
    for title, note in notes.items():
        if not outbound.get(title) and not inbound.get(title):
            orphans.append(f"{note['folder']}/{title}.md — no inbound or outbound links")
        if note["type"] == "concept":
            mapped = any(
                notes[src]["type"] == "map" and src not in NON_THEMED_MAPS
                for src in inbound.get(title, ())
            )
            if not mapped:
                unmapped.append(f"Concepts/{title}.md — in no themed Map")
        if note["type"] == "source":
            cites = any(notes[t]["type"] == "concept" for t in outbound.get(title, ()))
            if not cites:
                citeless.append(f"Sources/{title}.md — links no Concept")
    findings += section("2a. Orphan notes (isolated)", orphans, args.quiet)
    findings += section("2b. Concepts in no themed Map", unmapped, args.quiet)
    findings += section("2c. Sources citing no Concept", citeless, args.quiet)

    # ---- 3. Frontmatter ---------------------------------------------------
    fm_issues: list[str] = []
    undated: list[str] = []
    for title, note in notes.items():
        fm, ntype = note["fm"], note["type"]
        loc = f"{note['folder']}/{title}.md"
        if ntype not in REQUIRED_FM:
            fm_issues.append(f"{loc} — unknown type: {fm.get('type')!r}")
            continue
        for field in REQUIRED_FM[ntype]:
            if not fm.get(field):
                fm_issues.append(f"{loc} — missing/blank `{field}:`")
        for field in DATE_FIELDS:
            val = fm.get(field)
            if val and isinstance(val, str) and not DATE_RE.match(val):
                fm_issues.append(f"{loc} — `{field}: {val}` not YYYY-MM-DD")
        if ntype == "source" and not fm.get("published"):
            undated.append(f"Sources/{title}.md")
    findings += section("3a. Frontmatter issues", fm_issues, args.quiet)
    findings += section(
        "3b. Undated sources (`published:` blank — can't be conflict-ranked)",
        undated,
        args.quiet,
    )

    # ---- 4. ⏳ ↔ tracker reconciliation -----------------------------------
    # The convention tracks ⏳ lines in *Concept* notes (and non-tracker Maps).
    # Markers inside Source notes are just the source's own record of provisional
    # wording — counted for info, never reconciled.
    marked_notes: dict[str, int] = {}
    source_markers = 0
    for title, note in notes.items():
        # Skip tracker/hub Maps — they mention ⏳ when describing the convention.
        if note["type"] == "map" and title in NON_THEMED_MAPS:
            continue
        n = sum(1 for line in note["body"].splitlines() if "⏳" in line)
        if not n:
            continue
        if note["type"] == "source":
            source_markers += n
        else:
            marked_notes[title] = n

    # Open rows, each with the set of notes its Note column links. A row is
    # satisfied while ANY of its notes still carries a ⏳ marker (the claim may
    # be marked in just one of several linked notes).
    open_rows: list[tuple[str, set[str]]] = []
    if TRACKER.exists():
        text = TRACKER.read_text(encoding="utf-8")
        open_part = text.split("## Resolved")[0]
        for row in re.finditer(r"^\|(.+)\|\s*$", open_part, re.M):
            line = row.group(1)
            first_cell = line.split("|", 1)[0].strip()
            if first_cell == "Claim" or set(first_cell) <= {"-", " ", ":"}:
                continue
            # Cells can contain literal pipes inside backticks, so cell-splitting
            # is unreliable — take every wikilink in the row. Source-note links
            # (the "As of" column) are harmless: they never carry ⏳ markers.
            linked = {wikilink_target(raw) for raw in WIKILINK_RE.findall(line)}
            if linked:
                open_rows.append((first_cell, linked))
    tracked_open = set().union(*(linked for _, linked in open_rows)) if open_rows else set()

    untracked = [
        f"{notes[t]['folder']}/{t}.md — {n} ⏳ marker(s), no Open tracker row"
        for t, n in sorted(marked_notes.items())
        if t not in tracked_open
    ]
    stale_rows = [
        f"tracker row \"{claim[:70]}…\" ({', '.join(sorted(linked))}) — no linked note has ⏳ "
        f"markers left (resolve or archive the row)"
        for claim, linked in open_rows
        if not any(t in marked_notes for t in linked)
    ]
    total_markers = sum(marked_notes.values())
    if not args.quiet or untracked or stale_rows:
        print(
            f"\n== 4. ⏳ reconciliation — {total_markers} markers in "
            f"{len(marked_notes)} Concept/Map notes vs {len(tracked_open)} tracked notes (Open); "
            f"{source_markers} markers in Sources (info only, not reconciled)"
        )
        for it in untracked + stale_rows:
            print(f"   {it}")
    findings += len(untracked) + len(stale_rows)

    # ---- 5. Index drift ---------------------------------------------------
    old = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""

    def _stable(text: str) -> str:
        return re.sub(r"^updated:.*$", "", text, flags=re.M)

    m = re.search(r"^created:\s*(\S+)", old, re.M)
    new = build_index("0000-00-00", m.group(1) if m else "0000-00-00")
    drift = (
        []
        if _stable(new) == _stable(old)
        else ["Concepts/_INDEX.md is stale — run `python3 generate_index.py`"]
    )
    findings += section("5. Concept index drift", drift, args.quiet)

    # ---- 6. Clippings ↔ Sources ------------------------------------------
    pointer_of: dict[str, list[str]] = defaultdict(list)   # clipping stem -> source titles
    broken_pointers: list[str] = []
    for title, note in notes.items():
        if note["type"] != "source":
            continue
        raw = note["fm"].get("clipping") or ""
        target = wikilink_target(raw.strip().strip("[]"))
        if not target:
            continue  # missing pointer already flagged in 3a
        if target in clipping_stems:
            pointer_of[target].append(title)
        else:
            broken_pointers.append(
                f"Sources/{title}.md — clipping pointer [[{target}]] matches no file in Clippings/"
            )
    unprocessed = sorted(clipping_stems - set(pointer_of))
    multi = [
        f"Clippings/{clipping_names[c]} ← {len(srcs)} sources ({', '.join(srcs)})"
        for c, srcs in sorted(pointer_of.items())
        if len(srcs) > 1
    ]
    findings += section("6a. Broken `clipping:` pointers", broken_pointers, args.quiet)
    findings += section(
        "6b. Unprocessed clippings (no Source yet — compile backlog)",
        [f"Clippings/{clipping_names[c]}" for c in unprocessed],
        args.quiet,
    )
    findings += section("6c. Clippings claimed by multiple Sources", multi, args.quiet)

    # ---- 7. Scale thresholds ----------------------------------------------
    n_concepts = sum(1 for n in notes.values() if n["type"] == "concept")
    n_sources = sum(1 for n in notes.values() if n["type"] == "source")
    themed_maps = [
        t for t, n in notes.items() if n["type"] == "map" and t not in NON_THEMED_MAPS
    ]
    thresholds: list[str] = []
    if n_concepts > 150:
        thresholds.append(
            f"{n_concepts} concepts > 150 — sharded duplicate/contradiction lint is MANDATORY"
        )
    if len(themed_maps) >= 20:
        thresholds.append(f"{len(themed_maps)} themed Maps ≥ 20 — introduce the domain-map tier")
    elif len(themed_maps) >= 15:
        thresholds.append(
            f"{len(themed_maps)} themed Maps — approaching the ~20 domain-tier threshold"
        )
    findings += section("7. Scale thresholds", thresholds, args.quiet)

    print(
        f"\nSummary: {findings} finding(s) · {n_concepts} concepts · {n_sources} sources · "
        f"{len(themed_maps)} themed maps · {len(clipping_stems)} clippings "
        f"({len(unprocessed)} unprocessed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
