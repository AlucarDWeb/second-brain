"""Fetch adapters.

Each adapter is a module exposing:

    fetch(cfg: dict, vault_root: Path) -> list[FetchedItem]

where `cfg` is one entry from sources.yaml and `FetchedItem` (defined in run.py) carries
the fetched bytes plus the stable `source_id`, target `clipping` basename, upstream
last-modified date, and a `write` flag (True → run.py writes it into Clippings/).

The manifest-core build ships only `local`. Remote adapters (github_docs, confluence,
gdrive_gemini, amplitude) are Phase 1+ and register here by adding to run.py's ADAPTERS
map — no other file needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FetchedItem:
    """One fetched source, ready for hashing against the manifest.

    source_id          Stable key in manifest.json (e.g. "clippings:Clippings/foo.md").
    clipping           Basename of the target file in Clippings/.
    content            Raw bytes to hash (and, if write=True, to write).
    upstream_modified  Upstream last-modified date (ISO). Feeds Source `published:`.
    write              True → run.py writes `content` into Clippings/ (remote adapters);
                       False → the file already lives in Clippings/ (local adapter).
    """

    source_id: str
    clipping: str
    content: bytes
    upstream_modified: str
    write: bool = False
