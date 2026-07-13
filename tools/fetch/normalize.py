"""Frontmatter normalization for fetched sources.

Clippings are the immutable raw record, and the compiler reads their frontmatter to
populate Source notes: `url` / `source` / `published` (the recency signal that drives
conflict ranking) / `created` (the clip date). Remote adapters produce raw markdown
that usually has *no* frontmatter, so they call `ensure_frontmatter` to inject it
before the bytes are written to Clippings/.

The `local` adapter does NOT normalize: files already in Clippings/ are the human's
own drops (often from the Obsidian Web Clipper, already carrying frontmatter), and
CLAUDE.md forbids modifying Clippings/. Normalization is strictly an ingest-time step
for adapters that *create* new clipping bytes.

No third-party dependencies — a minimal shallow frontmatter reader/writer is enough
for the flat key: value blocks the compiler expects.
"""

from __future__ import annotations


FRONTMATTER_KEYS = ("url", "source", "author", "published", "created", "clipping")


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (existing keys, body). Shallow parse of a leading --- ... --- block."""
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text
    lines = text.splitlines()
    # lines[0] is the opening '---'
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    keys: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            keys[k.strip()] = v.strip()
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return keys, body


def ensure_frontmatter(text: str, defaults: dict[str, str]) -> str:
    """Guarantee a frontmatter block, filling any missing keys from `defaults`.

    Existing values always win over defaults — we never clobber what a source already
    declares. Keys are emitted in the canonical order the compiler expects, with any
    extra existing keys appended after.
    """
    existing, body = _split_frontmatter(text)
    merged = {k: v for k, v in defaults.items() if v not in (None, "")}
    merged.update({k: v for k, v in existing.items() if v not in (None, "")})

    ordered: list[tuple[str, str]] = []
    for k in FRONTMATTER_KEYS:
        if k in merged:
            ordered.append((k, merged.pop(k)))
    for k, v in merged.items():  # any non-canonical keys the source carried
        ordered.append((k, v))

    fm = "\n".join(f"{k}: {v}" for k, v in ordered)
    return f"---\n{fm}\n---\n\n{body}".rstrip() + "\n"
