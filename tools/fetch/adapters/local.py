"""Local adapter — the dependency-free core of change detection.

It fetches nothing over the network: it simply reads the files the human has already
dropped into Clippings/ and hands their bytes to run.py, which hashes them against the
manifest. This is what turns "was this clipping already compiled?" from a fragile
name match into a real content diff — so an *edited* clipping is re-detected.

Because these files ARE the immutable raw record, items are returned with `write=False`:
run.py records their hash in the manifest but never rewrites Clippings/ (per CLAUDE.md).
"""

from __future__ import annotations

import glob
import os
from datetime import datetime, timezone
from pathlib import Path


def _iso_mtime(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def fetch(cfg: dict, vault_root: Path):
    from adapters import FetchedItem

    prefix = cfg.get("id", "local")
    patterns = cfg.get("glob") or []
    if isinstance(patterns, str):
        patterns = [patterns]

    seen: set[Path] = set()
    items: list[FetchedItem] = []
    for pattern in patterns:
        abs_pattern = os.path.join(str(vault_root), pattern)
        for match in glob.glob(abs_pattern, recursive=True):
            p = Path(match)
            if not p.is_file() or p.name == ".gitkeep":
                continue
            if p in seen:
                continue
            seen.add(p)
            rel = p.relative_to(vault_root).as_posix()
            items.append(
                FetchedItem(
                    source_id=f"{prefix}:{rel}",
                    clipping=p.name,
                    content=p.read_bytes(),
                    upstream_modified=_iso_mtime(p),
                    write=False,
                )
            )
    return items
