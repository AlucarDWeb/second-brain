#!/usr/bin/env python3
"""Deterministic name/alias dedup gate — language-neutral, no model, no cache.

Concept identity in this vault is *textual*: the filename is the wikilink target
and `aliases:` are the load-bearing synonyms. Two notes that mean the same thing
almost always share a name or an alias, so a lexical comparison catches the
duplicates the compiler must not create — in milliseconds, with zero context.

Deliberate design choices:

- **No stopword list.** A hardcoded Italian (or English) list makes the tool
  silently useless on any other language, and this vault mixes Italian notes over
  English sources. Instead, token weights are derived from the corpus itself
  (IDF over Concept names): function words appear in many names and get weighted
  toward zero, domain terms stay sharp. Nothing about the language is assumed.
- **Name-to-name, never union across aliases.** Unioning a 10-alias concept into
  one bag of tokens makes every score collapse; each alias competes on its own.
- **Numeric guard.** "Disegno di Legge C-2" and "Disegno di Legge C-8" are
  different things; templated names must not merge.
- **Containment is a strong signal**, not a weak one: "Too Big to Fail" nested
  inside "Too Big to Fail come Basis Etica" is exactly the near-duplicate case.

The semantic layer (`semantic.py`) is *retrieval for `/ask`*, not a dedup gate:
measured on this vault, unrelated concepts sit at ~0.88 cosine (the model
saturates), so `pairs` nominates noise and finds nothing above 0.85.

Usage:
    python3 dedup_check.py "Crisi del 2008 come Operazione di Clearing"
    python3 dedup_check.py "Too Big to Fail" --aliases "TBTF; basis etica" --top 5
    python3 dedup_check.py --audit                  # suspect unlinked pairs, worst first
    python3 dedup_check.py --alias-gaps             # concepts with <2 aliases (the real risk)
    python3 dedup_check.py --audit --quiet          # counts only

Exit codes: 0 = no candidate at/above threshold, 1 = candidates found (lookup mode).
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import unicodedata
from pathlib import Path

CONCEPTS_DIR = Path(__file__).resolve().parent / "Concepts"
# Above this share of the corpus a token is structural, not descriptive.
HIGH_DF_SHARE = 0.35


def normalize(text: str) -> str:
    """Lowercase, strip accents, drop punctuation — the canonical comparison key."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if t}


def trigrams(text: str) -> set[str]:
    s = " " + normalize(text).replace(" ", "_") + " "
    return {s[i : i + 3] for i in range(len(s) - 2)}


def nums(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def dice(a: set[str], b: set[str]) -> float:
    return 0.0 if not a or not b else 2 * len(a & b) / (len(a) + len(b))


def read_aliases(path: Path) -> list[str]:
    """Minimal YAML reader: `aliases:` as block list or inline list."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.count("---") < 2:
        return []
    fm = text.split("---", 2)[1]
    m = re.search(r"^aliases:[ \t]*(.*)\n((?:[ \t]*-[ \t]*.+\n)*)", fm, re.M)
    if not m:
        return []
    out = [x.strip().strip("\"'") for x in m.group(1).strip().strip("[]").split(",") if x.strip()]
    out += [ln.strip().lstrip("-").strip().strip("\"'") for ln in m.group(2).splitlines()]
    return [x for x in out if x]


class Concept:
    __slots__ = ("name", "aliases", "names", "forms", "n_forms", "linked")

    def __init__(self, name: str, aliases: list[str], body: str = "") -> None:
        self.name, self.aliases = name, aliases
        self.names = [n for n in [name, *aliases] if n.strip()]
        self.forms = [(tokens(n), trigrams(n), nums(n)) for n in self.names]
        self.n_forms = 1 if self.forms else 0  # forms[0] is the name, the rest are aliases
        self.linked = set(re.findall(r"\[\[([^\]\|#]+)", body))


def load() -> list[Concept]:
    out = []
    for p in sorted(CONCEPTS_DIR.glob("*.md")):
        if p.stem.startswith("_"):  # _INDEX.md is generated, not a concept
            continue
        out.append(Concept(p.stem, read_aliases(p), p.read_text(encoding="utf-8", errors="replace")))
    return out


class Scorer:
    """IDF weights derived from the concept names, so no stopword list is needed."""

    def __init__(self, concepts: list[Concept]) -> None:
        df: dict[str, int] = {}
        for c in concepts:
            seen = set().union(*(f[0] for f in c.forms)) if c.forms else set()
            for t in seen:
                df[t] = df.get(t, 0) + 1
        n = max(len(concepts), 1)
        self.idf = {t: math.log((n + 1) / (d + 0.5)) for t, d in df.items()}
        self.structural = {t for t, d in df.items() if d / n > HIGH_DF_SHARE}

    def vec(self, toks: set[str]) -> dict[str, float]:
        v = {t: self.idf.get(t, 1.0) for t in toks if t not in self.structural}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {k: x / norm for k, x in v.items()}

    def score(self, a: Concept, b: Concept) -> tuple[float, str]:
        """Best match across name/alias pairs, with the guard-rails applied per pair."""
        best = (0.0, "")
        for ia, (ta, ga, na) in enumerate(a.forms):
            for ib, (tb, gb, nb) in enumerate(b.forms):
                if ta and ta == tb:
                    # Same token set: an alias that literally names the same thing.
                    return (1.0, "identical")
                ct, cd = self.cos(self.vec(ta), self.vec(tb)), dice(ga, gb) * 0.9
                s, how = (ct, "tokens") if ct >= cd else (cd, "trigram")
                # Containment is only trustworthy on the *primary names*: aliases are
                # short topic tags shared across concepts ("banca centrale"), and
                # nesting them there means "same theme", not "same concept".
                if ia == 0 and ib == 0 and ta and tb and (ta <= tb or tb <= ta) and len(ta & tb) >= 2:
                    s, how = max(s, 0.95), "containment"
                if ia > 0 and ib > 0:
                    s *= 0.85  # alias↔alias is the weakest evidence
                if na and nb and na != nb:
                    s *= 0.6  # C-2 vs C-8
                if s > best[0]:
                    best = (s, how)
        return best

    @staticmethod
    def cos(a: dict[str, float], b: dict[str, float]) -> float:
        return sum(x * b.get(k, 0.0) for k, x in a.items())

    def shared(self, a: Concept, b: Concept) -> list[str]:
        best, out = 0.0, set()
        for ta, _, _ in a.forms:
            for tb, _, _ in b.forms:
                c = self.cos(self.vec(ta), self.vec(tb))
                if c > best:
                    best, out = c, ta & tb
        return sorted(out)


def cmd_lookup(args: argparse.Namespace) -> int:
    concepts = load()
    sc = Scorer(concepts)
    cand = Concept(args.name, args.aliases or [])
    rows = sorted(((sc.score(cand, c)[0], sc.score(cand, c)[1], c) for c in concepts),
                  key=lambda r: -r[0])
    hits = [r for r in rows if r[0] >= args.threshold][: args.top]
    for s, how, c in hits:
        shared = sc.shared(cand, c)
        print(f"{s:.2f} [{how}] [[{c.name}]]" + (f"  · {', '.join(shared)}" if shared else ""))
    if hits:
        print(f"\n{len(hits)} candidate(s) ≥ {args.threshold} — open them before creating a new concept.",
              file=sys.stderr)
        return 1
    print(f"No concept ≥ {args.threshold} — name/alias are free.", file=sys.stderr)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    concepts = load()
    sc = Scorer(concepts)
    rows = []
    for i, a in enumerate(concepts):
        for b in concepts[i + 1 :]:
            if a.name in b.linked or b.name in a.linked:
                continue
            s, how = sc.score(a, b)
            if s >= args.threshold:
                rows.append((s, how, a, b))
    rows.sort(key=lambda r: -r[0])
    if not args.quiet:
        for s, how, a, b in rows[: args.top]:
            shared = sc.shared(a, b)
            print(f"{s:.2f} [{how}] [[{a.name}]] ↔ [[{b.name}]]"
                  + (f"  · {', '.join(shared)}" if shared else ""))
    print(f"\n{len(rows)} unlinked pair(s) ≥ {args.threshold} over {len(concepts)} concepts; "
          f"{args.top} shown.", file=sys.stderr)
    return 0


def cmd_alias_gaps(args: argparse.Namespace) -> int:
    """Aliases are the only cross-language bridge; <2 means the note is unfindable."""
    gaps = sorted((c.name, len(c.aliases)) for c in load() if len(c.aliases) < args.min_aliases)
    for name, n in gaps:
        print(f"{n} aliases  [[{name}]]")
    print(f"\n{len(gaps)} concept(s) with <{args.min_aliases} aliases — add the other-language "
          f"form(s) so name dedup can find them.", file=sys.stderr)
    return 0


def cmd_alias_collisions(args: argparse.Namespace) -> int:
    """One alias claimed by several concepts breaks search: the name resolves to a set."""
    table: dict[str, set[str]] = {}
    for c in load():
        for alias in c.aliases:
            key = " ".join(sorted(tokens(alias)))
            if key:
                table.setdefault(key, set()).add(c.name)
    bad = {k: v for k, v in table.items() if len(v) > 1}
    for key, names in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        print(f"[{key}] ← {len(names)}: " + ", ".join(f"[[{n}]]" for n in names))
    print(f"\n{len(bad)} alias key(s) claimed by more than one concept — the alias must be "
          f"disambiguated or moved to the concept it really names.", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", help="candidate concept name (lookup mode)")
    ap.add_argument("--aliases", help="semicolon-separated alternative names")
    ap.add_argument("--threshold", type=float, default=0.55, help="min score (audit default 0.7)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--min-aliases", type=int, default=2)
    ap.add_argument("--audit", action="store_true", help="compare every unlinked concept pair")
    ap.add_argument("--alias-gaps", action="store_true", help="concepts with too few aliases")
    ap.add_argument("--alias-collisions", action="store_true", help="aliases claimed by 2+ concepts")
    ap.add_argument("--quiet", action="store_true", help="audit: print the count only")
    args = ap.parse_args()
    if args.aliases:
        args.aliases = [x.strip() for x in args.aliases.split(";") if x.strip()]
    if args.alias_gaps:
        return cmd_alias_gaps(args)
    if args.alias_collisions:
        return cmd_alias_collisions(args)
    if args.audit:
        if args.threshold == 0.55:
            args.threshold = 0.7
        return cmd_audit(args)
    if not args.name:
        ap.error("provide a candidate name, or use --audit / --alias-gaps")
    return cmd_lookup(args)


if __name__ == "__main__":
    sys.exit(main())
