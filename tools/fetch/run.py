#!/usr/bin/env python3
"""Content-hash manifest — the change-detection core of the auto-ingest loop.

    fetch → hash → diff (vs manifest) → (over)write changed → emit CHANGED

For every source in sources.yaml an adapter yields the current bytes. Each is sha256'd
against a stable `source_id` in manifest.json:

  * new / changed sha  → (over)write the clipping (remote adapters only), record the new
                         hash + upstream last-modified + fetched-at, add it to CHANGED.
  * unchanged          → skip. This is what makes a scheduled run cheap — untouched
                         sources are never re-compiled.
  * upstream deletion  → reported, never auto-deleted. Knowledge is not silently dropped.

CHANGED (new + changed clipping basenames) is printed and written to $GITHUB_OUTPUT as
`changed=...`, so a workflow can pass it straight to `/compile <CHANGED>`.

This build ships only the dependency-free `local` adapter (hashes files already in
Clippings/). Remote adapters are Phase 1+; they register in ADAPTERS below.

Usage:
    python tools/fetch/run.py [--dry-run] [--vault-root PATH]

No third-party dependencies required. PyYAML is used automatically if installed;
otherwise a minimal parser handles the flat sources.yaml subset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make `adapters` importable whether run as a script or a module.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters import FetchedItem  # noqa: E402
from adapters import local as local_adapter  # noqa: E402

# type string in sources.yaml -> adapter.fetch(cfg, vault_root) -> list[FetchedItem]
ADAPTERS = {
    "local": local_adapter.fetch,
    # Phase 1+ (require token secrets; not in the manifest-core build):
    # "github_docs":  github_docs.fetch,
    # "confluence":   confluence.fetch,
    # "gdrive_gemini": gdrive_gemini.fetch,
    # "amplitude":    amplitude.fetch,
}

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "manifest.json"
SOURCES_PATH = HERE / "sources.yaml"


# --------------------------------------------------------------------------- config

def _load_yaml(path: Path) -> dict:
    """Load sources.yaml. Uses PyYAML if present, else a minimal built-in parser.

    The built-in parser supports exactly the shape this project uses:
      - a top-level `sources:` key
      - a list of `- key: value` items (one dict per item)
      - scalar values (bare or quoted), booleans, and inline `[a, b]` lists
    """
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ModuleNotFoundError:
        return _minimal_parse(text)


def _coerce(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_coerce(part) for part in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value


def _minimal_parse(text: str) -> dict:
    sources: list[dict] = []
    current: dict | None = None
    in_sources = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "sources:":
            in_sources = True
            continue
        if not in_sources:
            continue
        if stripped.startswith("- "):
            current = {}
            sources.append(current)
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            # drop an inline trailing comment when the value isn't quoted/bracketed
            v = value.strip()
            if v and v[0] not in "\"'[" and "#" in v:
                v = v.split("#", 1)[0].strip()
            current[key.strip()] = _coerce(v)
    return {"sources": sources}


# ------------------------------------------------------------------------- manifest

def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return {}


def _save_manifest(manifest: dict) -> None:
    ordered = {k: manifest[k] for k in sorted(manifest)}
    MANIFEST_PATH.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------ run

def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch upstream sources and diff by content hash.")
    ap.add_argument("--dry-run", action="store_true", help="Report CHANGED without writing.")
    ap.add_argument("--vault-root", default=str(HERE.parent.parent), help="Vault root path.")
    args = ap.parse_args()

    vault_root = Path(args.vault_root).resolve()
    clippings_dir = vault_root / "Clippings"

    config = _load_yaml(SOURCES_PATH)
    manifest = _load_manifest()

    changed: list[str] = []          # clipping basenames that are new or content-changed
    seen_ids: set[str] = set()
    skipped_types: set[str] = set()

    for cfg in config.get("sources", []):
        stype = cfg.get("type")
        fetcher = ADAPTERS.get(stype)
        if fetcher is None:
            skipped_types.add(str(stype))
            continue

        items: list[FetchedItem] = fetcher(cfg, vault_root)
        for item in items:
            seen_ids.add(item.source_id)
            sha = hashlib.sha256(item.content).hexdigest()
            prev = manifest.get(item.source_id)

            if prev and prev.get("sha256") == sha:
                continue  # unchanged — skip

            status = "changed" if prev else "new"
            if item.write and not args.dry_run:
                target = clippings_dir / item.clipping
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(item.content)

            if not args.dry_run:
                manifest[item.source_id] = {
                    "sha256": sha,
                    "upstream_modified": item.upstream_modified,
                    "clipping": item.clipping,
                    "fetched_at": _now_iso(),
                }
            changed.append(item.clipping)
            print(f"  [{status:>7}] {item.clipping}  ({item.source_id})", file=sys.stderr)

    # Upstream deletions: recorded ids not seen this run. Reported, never removed.
    deletions = [
        m.get("clipping", sid)
        for sid, m in manifest.items()
        if sid not in seen_ids
    ]

    if not args.dry_run:
        _save_manifest(manifest)

    # De-dupe preserving order, then emit.
    changed = list(dict.fromkeys(changed))
    _report(changed, deletions, skipped_types, dry_run=args.dry_run)
    _emit_changed(changed)
    return 0


def _report(changed, deletions, skipped_types, *, dry_run):
    print("", file=sys.stderr)
    tag = "DRY RUN — " if dry_run else ""
    print(f"{tag}{len(changed)} changed, {len(deletions)} upstream deletion(s)", file=sys.stderr)
    if deletions:
        print("  upstream deletions (NOT removed — review manually):", file=sys.stderr)
        for d in deletions:
            print(f"    - {d}", file=sys.stderr)
    if skipped_types:
        known = {t for t in skipped_types if t not in ("None", "")}
        if known:
            print(
                "  skipped source types (adapter not in this build): "
                + ", ".join(sorted(known)),
                file=sys.stderr,
            )


def _emit_changed(changed: list[str]) -> None:
    # Human/pipe-readable line on stdout, space-joined and quoted for /compile args.
    joined = " ".join(_shell_quote(c) for c in changed)
    print(joined)

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"changed={joined}\n")
            fh.write(f"changed_count={len(changed)}\n")


def _shell_quote(s: str) -> str:
    return f'"{s}"' if (" " in s or '"' in s) else s


if __name__ == "__main__":
    raise SystemExit(main())
