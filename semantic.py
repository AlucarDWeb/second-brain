#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["model2vec>=0.3", "numpy"]
# ///
"""Semantic layer over Concepts/ — embedding cache + similarity queries.

Embeds each Concept's identity line (name + aliases + first-sentence definition —
the same text `_INDEX.md` carries) with a small local static-embedding model
(model2vec potion-base-8M, ~30MB, downloaded once to the HF cache, offline after
that). Vectors live in a local derived cache (`.claude/cache/semantic/`) keyed by
content hash, so re-runs only embed new/changed concepts. The cache is fully
regenerable: if it ever looks wrong, delete `.claude/cache/semantic/` and re-run
`index`. This is a **candidate pre-filter**: it surfaces
likely duplicate/contradiction pairs and semantic matches; the LLM still makes
every judgment call.

Usage:
    uv run semantic.py index                 # build/refresh the cache (incremental)
    uv run semantic.py pairs                 # candidate duplicate pairs, most-similar first
    uv run semantic.py pairs --threshold 0.7 --include-linked
    uv run semantic.py search "query text"   # top concepts nearest the query
    uv run semantic.py search "query" --top 15

`pairs` and `search` refresh the cache automatically first. Pairs where either
note already wikilinks the other are excluded by default (known-related), so the
default output is "similar but unaware of each other" — the dedup signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_index import one_liner  # noqa: E402
from generate_views import parse_frontmatter  # noqa: E402

VAULT = Path(__file__).resolve().parent
CONCEPTS = VAULT / "Concepts"
CACHE_DIR = VAULT / ".claude" / "cache" / "semantic"
MANIFEST = CACHE_DIR / "manifest.json"
VECTORS = CACHE_DIR / "vectors.npz"

MODEL_NAME = "minishlab/potion-base-8M"
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]")


def load_concepts() -> dict[str, dict]:
    """name -> {text: embed text, links: set of wikilinked concept names}."""
    out: dict[str, dict] = {}
    for path in sorted(CONCEPTS.glob("*.md"), key=lambda p: p.stem.casefold()):
        if path.name == "_INDEX.md":
            continue
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        aliases = fm.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        alias_str = ", ".join(a for a in aliases if a)
        text = path.stem
        if alias_str:
            text += f". Also known as: {alias_str}"
        text += f". {one_liner(body)}"
        links = {m.group(1).strip() for m in WIKILINK_RE.finditer(body)}
        out[path.stem] = {"text": text, "links": links}
    return out


def refresh_cache(quiet: bool = False) -> tuple[list[str], np.ndarray, dict[str, dict]]:
    """Incrementally (re)embed changed concepts; return (names, unit vectors, concepts)."""
    concepts = load_concepts()
    manifest = {"model": None, "hashes": {}}
    vectors: dict[str, np.ndarray] = {}
    if MANIFEST.exists() and VECTORS.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        with np.load(VECTORS) as z:
            vectors = {k: z[k] for k in z.files}
    if manifest.get("model") != MODEL_NAME:
        manifest = {"model": MODEL_NAME, "hashes": {}}
        vectors = {}

    hashes = {n: hashlib.sha256(c["text"].encode()).hexdigest() for n, c in concepts.items()}
    stale = [
        n for n, h in hashes.items()
        if manifest["hashes"].get(n) != h or n not in vectors
    ]
    removed = [n for n in list(vectors) if n not in concepts]
    for n in removed:
        vectors.pop(n)
        manifest["hashes"].pop(n, None)

    if stale:
        from model2vec import StaticModel  # deferred: model load only when embedding

        model = StaticModel.from_pretrained(MODEL_NAME)
        embedded = model.encode([concepts[n]["text"] for n in stale])
        for n, vec in zip(stale, np.asarray(embedded, dtype=np.float32)):
            vectors[n] = vec / (np.linalg.norm(vec) or 1.0)
            manifest["hashes"][n] = hashes[n]
        _save_cache(vectors, manifest)
    elif removed:
        _save_cache(vectors, manifest)

    if not quiet:
        print(
            f"cache: {len(vectors)} concepts · {len(stale)} (re)embedded · "
            f"{len(removed)} removed",
            file=sys.stderr,
        )
    names = sorted(vectors, key=str.casefold)
    matrix = np.stack([vectors[n] for n in names]) if names else np.empty((0, 0))
    return names, matrix, concepts


def _save_cache(vectors: dict[str, np.ndarray], manifest: dict) -> None:
    """Write cache files with sorted keys so identical content serializes identically."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if vectors:
        np.savez(VECTORS, **dict(sorted(vectors.items())))
    elif VECTORS.exists():
        VECTORS.unlink()
    MANIFEST.write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def cmd_pairs(args: argparse.Namespace) -> int:
    names, matrix, concepts = refresh_cache()
    if len(names) < 2:
        print("Fewer than two concepts — nothing to compare.")
        return 0
    sim = matrix @ matrix.T
    iu, ju = np.triu_indices(len(names), k=1)
    order = np.argsort(sim[iu, ju])[::-1]
    rows = []
    for k in order:
        score = float(sim[iu[k], ju[k]])
        if score < args.threshold:
            break
        a, b = names[iu[k]], names[ju[k]]
        linked = b in concepts[a]["links"] or a in concepts[b]["links"]
        if linked and not args.include_linked:
            continue
        rows.append((score, a, b, linked))
        if len(rows) >= args.top:
            break
    if not rows:
        print(f"No unlinked pairs at similarity ≥ {args.threshold}.")
        return 0
    for score, a, b, linked in rows:
        tag = "linked" if linked else "UNLINKED"
        print(f"{score:.3f}  {tag:8s}  [[{a}]] ↔ [[{b}]]")
    print(
        f"\n{len(rows)} candidate pair(s) at ≥ {args.threshold} "
        "(judge each: duplicate to merge, contradiction, or just neighbors to link).",
        file=sys.stderr,
    )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    names, matrix, concepts = refresh_cache()
    if not names:
        print("No concepts embedded.")
        return 0
    from model2vec import StaticModel

    model = StaticModel.from_pretrained(MODEL_NAME)
    q = np.asarray(model.encode([args.query]), dtype=np.float32)[0]
    q /= np.linalg.norm(q) or 1.0
    scores = matrix @ q
    for idx in np.argsort(scores)[::-1][: args.top]:
        name = names[idx]
        print(f"{float(scores[idx]):.3f}  [[{name}]]  ·  {concepts[name]['text']}")
    return 0


def cmd_index(_args: argparse.Namespace) -> int:
    refresh_cache()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("index", help="build/refresh the embedding cache (incremental)")

    p = sub.add_parser("pairs", help="candidate duplicate/contradiction pairs")
    p.add_argument("--threshold", type=float, default=0.75, help="min cosine similarity (default 0.75)")
    p.add_argument("--top", type=int, default=40, help="max pairs to print (default 40)")
    p.add_argument("--include-linked", action="store_true", help="also show pairs that already wikilink each other")

    s = sub.add_parser("search", help="top concepts nearest a query")
    s.add_argument("query")
    s.add_argument("--top", type=int, default=10, help="results to print (default 10)")

    args = ap.parse_args()
    return {"index": cmd_index, "pairs": cmd_pairs, "search": cmd_search}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
