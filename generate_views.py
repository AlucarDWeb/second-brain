#!/usr/bin/env python3
"""
generate_views.py — HTML visualization layer for the searchxp_brain vault.

The vault (Concepts/, Sources/, Maps/) is the source of truth. This script reads
the notes + their frontmatter and derives a standalone, fully-offline HTML site
under views/:

    views/index.html          force-directed graph of the whole vault
    views/notes/<slug>.html    one curated page per note (+ backlinks)
    views/assets/app.css       shared styles
    views/assets/graph.js      vanilla-canvas force graph (no D3, no CDN)

No third-party dependencies — Python 3 standard library only. Run from the vault
root:  python3 generate_views.py

Everything under views/ is regenerated on each run; never hand-edit it.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parent
NOTE_DIRS = ["Concepts", "Sources", "Maps"]
OUT = VAULT / "views"
NOTES_OUT = OUT / "notes"
ASSETS_OUT = OUT / "assets"

# Files that live in the note dirs but are NOT notes.
SKIP = {"_INDEX.md"}

TYPE_LABEL = {"concept": "Concept", "source": "Source", "map": "Map"}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def parse_frontmatter(text: str):
    """Return (frontmatter_dict, body). Minimal YAML — enough for this vault."""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    fm = {}
    key = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        m2 = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if m2:
            key, val = m2.group(1), m2.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                fm[key] = [v.strip().strip('"\'') for v in inner.split(",") if v.strip()]
            elif val:
                fm[key] = val.strip('"\'')
            else:
                fm[key] = ""
        elif line.lstrip().startswith("-") and key:
            # block-style list continuation
            if not isinstance(fm.get(key), list):
                fm[key] = [] if fm.get(key) in ("", None) else [fm[key]]
            fm[key].append(line.lstrip()[1:].strip().strip('"\''))
    return fm, body


def wikilink_target(raw: str) -> str:
    """Normalize a wikilink payload to its target title (drop |alias and #anchor)."""
    target = raw.split("|", 1)[0]
    target = target.split("#", 1)[0]
    return target.strip()


def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s or "note"


# --------------------------------------------------------------------------- #
# Load the vault
# --------------------------------------------------------------------------- #

def load_notes():
    notes = {}          # title -> note dict
    alias_index = {}    # lowercased alias/title -> title
    for d in NOTE_DIRS:
        folder = VAULT / d
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            if path.name in SKIP:
                continue
            text = path.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            title = path.stem
            note = {
                "title": title,
                "folder": d,
                "slug": slugify(title),
                "type": (fm.get("type") or d.rstrip("s").lower()),
                "fm": fm,
                "body": body,
                "path": path,
                "links_out": [],   # resolved titles
                "backlinks": [],   # resolved titles
            }
            notes[title] = note
            alias_index[title.lower()] = title
            aliases = fm.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            for a in aliases:
                if a and a != "—":
                    alias_index.setdefault(a.lower(), title)
    return notes, alias_index


def resolve_links(notes, alias_index):
    for note in notes.values():
        seen = set()
        for raw in WIKILINK_RE.findall(note["body"]):
            target = wikilink_target(raw)
            resolved = alias_index.get(target.lower())
            if resolved and resolved != note["title"] and resolved not in seen:
                seen.add(resolved)
                note["links_out"].append(resolved)
    # backlinks
    for note in notes.values():
        for tgt in note["links_out"]:
            notes[tgt]["backlinks"].append(note["title"])
    for note in notes.values():
        note["backlinks"] = sorted(set(note["backlinks"]))


# --------------------------------------------------------------------------- #
# Minimal Markdown -> HTML (stdlib only)
# --------------------------------------------------------------------------- #

def render_inline(text: str, alias_index, notes, rel_prefix="") -> str:
    """Inline markdown. Wikilinks/code/links are resolved on RAW text (so targets
    with '&' resolve), stashed as final HTML, then the rest is escaped and styled."""
    stash = []  # each entry is finished HTML

    def put(final_html):
        stash.append(final_html)
        return f"\x00S{len(stash) - 1}\x00"

    # 1. code spans (raw content, escaped once)
    text = re.sub(
        r"`([^`]+)`",
        lambda m: put(f"<code>{html.escape(m.group(1), quote=False)}</code>"),
        text,
    )

    # 2. wikilinks -> anchors (resolve against RAW target)
    def repl_wiki(m):
        raw = m.group(1)
        target = wikilink_target(raw)
        label = raw.split("|", 1)[1].strip() if "|" in raw else target
        resolved = alias_index.get(target.lower())
        label_html = html.escape(label, quote=False)
        if resolved and resolved in notes:
            href = f"{rel_prefix}{notes[resolved]['slug']}.html"
            return put(f'<a class="wl" href="{href}">{label_html}</a>')
        return put(f'<a class="wl broken" title="unresolved link">{label_html}</a>')

    text = WIKILINK_RE.sub(repl_wiki, text)

    # 3. markdown links [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: put(
            f'<a class="ext" href="{html.escape(m.group(2), quote=True)}" '
            f'target="_blank" rel="noopener">{html.escape(m.group(1), quote=False)}</a>'
        ),
        text,
    )

    # 4. escape whatever prose remains
    text = html.escape(text, quote=False)

    # 5. bold then italic (operate on escaped text; markers are unescaped)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)

    # 6. restore stashed HTML
    text = re.sub(r"\x00S(\d+)\x00", lambda m: stash[int(m.group(1))], text)
    return text


def render_markdown(body: str, alias_index, notes, rel_prefix="") -> str:
    """Block-level markdown. Headings, lists (nested), blockquotes, hr, paragraphs."""
    lines = body.splitlines()
    out = []
    i = 0
    # list stack of indent levels
    list_stack = []

    def close_lists(to_level=0):
        while len(list_stack) > to_level:
            out.append("</li></ul>")
            list_stack.pop()

    para = []

    def flush_para():
        if para:
            out.append(f"<p>{render_inline(' '.join(para), alias_index, notes, rel_prefix)}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            close_lists()
            i += 1
            continue

        # headings
        hm = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if hm:
            flush_para()
            close_lists()
            level = len(hm.group(1))
            inner = render_inline(hm.group(2), alias_index, notes, rel_prefix)
            out.append(f"<h{level}>{inner}</h{level}>")
            i += 1
            continue

        # horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush_para()
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        # blockquote
        if stripped.startswith(">"):
            flush_para()
            close_lists()
            quote = [stripped.lstrip(">").strip()]
            i += 1
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            inner = render_inline(" ".join(quote), alias_index, notes, rel_prefix)
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # list item (- or *)
        lm = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if lm:
            flush_para()
            indent = len(lm.group(1))
            level = indent // 2 + 1
            content = render_inline(lm.group(2), alias_index, notes, rel_prefix)
            if level > len(list_stack):
                while len(list_stack) < level:
                    out.append("<ul>")
                    list_stack.append(level)
                out.append(f"<li>{content}")
            else:
                if len(list_stack) > level:
                    close_lists(level)
                else:
                    out.append("</li>")
                out.append(f"<li>{content}")
            i += 1
            continue

        # default: paragraph text
        close_lists()
        para.append(stripped)
        i += 1

    flush_para()
    close_lists()
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# HTML emission
# --------------------------------------------------------------------------- #

def page_shell(title, body_html, css_href, extra_head="", body_class=""):
    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{css_href}">
{extra_head}
</head>
<body class="{body_class}">
{body_html}
</body>
</html>
"""


def meta_row(label, value):
    if value in (None, "", []):
        return ""
    if isinstance(value, list):
        value = ", ".join(value)
    return f'<div class="meta-row"><span class="meta-k">{html.escape(label)}</span>' \
           f'<span class="meta-v">{html.escape(str(value))}</span></div>'


def render_note_page(note, notes, alias_index):
    fm = note["fm"]
    body_html = render_markdown(note["body"], alias_index, notes, rel_prefix="")

    # strip the leading H1 from body (we render our own header) — optional: keep it.
    type_key = note["type"]
    type_label = TYPE_LABEL.get(type_key, type_key.title())

    meta_html = "".join([
        meta_row("Type", type_label),
        meta_row("Folder", note["folder"]),
        meta_row("Tags", fm.get("tags")),
        meta_row("Aliases", [a for a in (fm.get("aliases") or []) if a and a != "—"]),
        meta_row("URL", fm.get("url")),
        meta_row("Author", fm.get("author")),
        meta_row("Published", fm.get("published")),
        meta_row("Created", fm.get("created")),
        meta_row("Updated", fm.get("updated")),
    ])

    def link_list(titles):
        if not titles:
            return '<p class="empty">None</p>'
        items = "".join(
            f'<li><a class="wl" href="{notes[t]["slug"]}.html">'
            f'<span class="dot {notes[t]["type"]}"></span>{html.escape(t)}</a></li>'
            for t in titles if t in notes
        )
        return f"<ul class='link-list'>{items}</ul>"

    outgoing = link_list(note["links_out"])
    backlinks = link_list(note["backlinks"])

    body = f"""
<div class="layout note-view">
  <header class="topbar">
    <a class="home" href="../index.html">◆ searchxp_brain</a>
    <span class="crumb">{html.escape(type_label)}</span>
  </header>
  <main class="content">
    <article class="prose type-{type_key}">
      <div class="badge {type_key}">{html.escape(type_label)}</div>
      {body_html}
    </article>
  </main>
  <aside class="sidebar">
    <section>
      <h3>Metadata</h3>
      <div class="meta-box">{meta_html}</div>
    </section>
    <section>
      <h3>Links out <span class="count">{len(note['links_out'])}</span></h3>
      {outgoing}
    </section>
    <section>
      <h3>Backlinks <span class="count">{len(note['backlinks'])}</span></h3>
      {backlinks}
    </section>
  </aside>
</div>
"""
    return page_shell(note["title"], body, "../assets/app.css",
                      body_class="note-page")


def build_graph_data(notes):
    idx = {t: i for i, t in enumerate(notes)}
    nodes = []
    for t, note in notes.items():
        deg = len(set(note["links_out"]) | set(note["backlinks"]))
        nodes.append({
            "id": idx[t],
            "label": t,
            "type": note["type"],
            "url": f"notes/{note['slug']}.html",
            "deg": deg,
        })
    seen = set()
    links = []
    for t, note in notes.items():
        for tgt in note["links_out"]:
            if tgt in idx:
                key = tuple(sorted((idx[t], idx[tgt])))
                if key not in seen:
                    seen.add(key)
                    links.append({"s": key[0], "t": key[1]})
    return {"nodes": nodes, "links": links}


def render_index(notes):
    graph = build_graph_data(notes)
    counts = {}
    for n in notes.values():
        counts[n["type"]] = counts.get(n["type"], 0) + 1

    # sidebar list grouped by type
    groups = {"concept": [], "source": [], "map": []}
    for t in sorted(notes):
        groups.setdefault(notes[t]["type"], []).append(t)

    def group_html(key, label):
        items = "".join(
            f'<li data-type="{key}"><a href="notes/{notes[t]["slug"]}.html">'
            f'{html.escape(t)}</a></li>'
            for t in groups.get(key, [])
        )
        if not items:
            return ""
        return f'<div class="nav-group"><h4><span class="dot {key}"></span>' \
               f'{label} <span class="count">{len(groups.get(key, []))}</span></h4>' \
               f'<ul>{items}</ul></div>'

    legend = "".join(
        f'<span class="lg"><span class="dot {k}"></span>{TYPE_LABEL[k]} '
        f'({counts.get(k, 0)})</span>'
        for k in ("concept", "source", "map")
    )

    body = f"""
<div class="index-layout">
  <header class="topbar">
    <span class="home">◆ searchxp_brain — visualization layer</span>
    <div class="legend">{legend}</div>
  </header>
  <div class="index-body">
    <aside class="nav">
      <input id="filter" type="search" placeholder="Filter notes…" autocomplete="off">
      <div id="nav-list">
        {group_html('map', 'Maps')}
        {group_html('concept', 'Concepts')}
        {group_html('source', 'Sources')}
      </div>
    </aside>
    <main class="graph-wrap">
      <canvas id="graph"></canvas>
      <div id="tooltip" class="tooltip"></div>
      <div class="graph-hint">drag to pan · scroll to zoom · click a node to open</div>
    </main>
  </div>
</div>
<script>window.GRAPH_DATA = {json.dumps(graph)};</script>
<script src="assets/graph.js"></script>
"""
    return page_shell("searchxp_brain — graph", body, "assets/app.css",
                      body_class="index-page")


# --------------------------------------------------------------------------- #
# Static assets
# --------------------------------------------------------------------------- #

APP_CSS = """
:root {
  --bg: #0f1115; --bg-2: #161922; --panel: #1a1e28; --border: #2a2f3d;
  --fg: #e6e9ef; --muted: #9aa4b2; --accent: #6ea8fe;
  --concept: #6ea8fe; --source: #7ee0a8; --map: #f0b866; --broken: #e06c75;
  --radius: 10px; --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
:root[data-theme="light"] {
  --bg:#f7f8fa; --bg-2:#eef0f4; --panel:#fff; --border:#dde1e8;
  --fg:#1c2230; --muted:#5a6472; --accent:#2563eb;
  --concept:#2563eb; --source:#16a34a; --map:#d97706; --broken:#dc2626;
}
* { box-sizing: border-box; }
html, body { margin:0; height:100%; }
body { background:var(--bg); color:var(--fg); font-family:var(--sans);
  font-size:15px; line-height:1.6; -webkit-font-smoothing:antialiased; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.dot { display:inline-block; width:9px; height:9px; border-radius:50%;
  margin-right:7px; vertical-align:middle; background:var(--muted); }
.dot.concept { background:var(--concept); } .dot.source { background:var(--source); }
.dot.map { background:var(--map); }
.count { color:var(--muted); font-weight:400; font-size:.82em; }

/* top bar */
.topbar { display:flex; align-items:center; justify-content:space-between;
  gap:16px; padding:12px 20px; background:var(--bg-2);
  border-bottom:1px solid var(--border); position:sticky; top:0; z-index:10; }
.topbar .home { font-weight:600; color:var(--fg); }
.crumb { color:var(--muted); font-size:.85em; }
.legend { display:flex; gap:16px; flex-wrap:wrap; font-size:.82em; color:var(--muted); }
.legend .lg { display:flex; align-items:center; }

/* ---- index / graph ---- */
.index-layout { height:100vh; display:flex; flex-direction:column; }
.index-body { flex:1; display:flex; min-height:0; }
.nav { width:290px; flex-shrink:0; background:var(--bg-2);
  border-right:1px solid var(--border); overflow-y:auto; padding:14px; }
.nav input { width:100%; padding:9px 11px; margin-bottom:12px; border-radius:8px;
  border:1px solid var(--border); background:var(--panel); color:var(--fg); font-size:14px; }
.nav-group { margin-bottom:16px; }
.nav-group h4 { margin:0 0 6px; font-size:.78em; text-transform:uppercase;
  letter-spacing:.05em; color:var(--muted); font-weight:600; }
.nav-group ul { list-style:none; margin:0; padding:0; }
.nav-group li a { display:block; padding:4px 8px; border-radius:6px;
  color:var(--fg); font-size:.9em; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.nav-group li a:hover { background:var(--panel); text-decoration:none; }
.graph-wrap { flex:1; position:relative; min-width:0; background:
  radial-gradient(circle at 50% 40%, var(--bg-2), var(--bg)); }
#graph { display:block; width:100%; height:100%; cursor:grab; }
#graph:active { cursor:grabbing; }
.tooltip { position:absolute; pointer-events:none; background:var(--panel);
  border:1px solid var(--border); padding:5px 9px; border-radius:6px;
  font-size:12px; opacity:0; transition:opacity .1s; white-space:nowrap; z-index:5; }
.graph-hint { position:absolute; bottom:10px; left:50%; transform:translateX(-50%);
  color:var(--muted); font-size:11px; opacity:.7; }

/* ---- note page ---- */
.note-page .layout { min-height:100vh; display:flex; flex-direction:column; }
.note-view .content, .note-view { }
.layout.note-view { display:grid; grid-template-columns:1fr 320px;
  grid-template-rows:auto 1fr; }
.layout.note-view .topbar { grid-column:1 / -1; }
.content { padding:34px 46px; max-width:820px; width:100%; }
.sidebar { border-left:1px solid var(--border); background:var(--bg-2);
  padding:24px 20px; overflow-y:auto; }
.sidebar section { margin-bottom:26px; }
.sidebar h3 { font-size:.78em; text-transform:uppercase; letter-spacing:.05em;
  color:var(--muted); margin:0 0 10px; }
.meta-box { background:var(--panel); border:1px solid var(--border);
  border-radius:var(--radius); padding:4px 12px; }
.meta-row { display:flex; justify-content:space-between; gap:12px;
  padding:6px 0; border-bottom:1px solid var(--border); font-size:.85em; }
.meta-row:last-child { border-bottom:none; }
.meta-k { color:var(--muted); } .meta-v { text-align:right; word-break:break-word; }
.link-list { list-style:none; margin:0; padding:0; }
.link-list li a { display:block; padding:5px 8px; border-radius:6px;
  color:var(--fg); font-size:.9em; }
.link-list li a:hover { background:var(--panel); text-decoration:none; }
.empty { color:var(--muted); font-size:.85em; font-style:italic; }

/* prose */
.prose { }
.badge { display:inline-block; font-size:.72em; text-transform:uppercase;
  letter-spacing:.06em; font-weight:700; padding:3px 10px; border-radius:99px;
  margin-bottom:8px; }
.badge.concept { background:color-mix(in srgb, var(--concept) 18%, transparent); color:var(--concept); }
.badge.source { background:color-mix(in srgb, var(--source) 18%, transparent); color:var(--source); }
.badge.map { background:color-mix(in srgb, var(--map) 18%, transparent); color:var(--map); }
.prose h1 { font-size:1.9em; line-height:1.2; margin:.2em 0 .5em; }
.prose h2 { font-size:1.3em; margin:1.6em 0 .5em; padding-bottom:.3em;
  border-bottom:1px solid var(--border); }
.prose h3 { font-size:1.08em; margin:1.4em 0 .4em; }
.prose p { margin:.7em 0; }
.prose ul { padding-left:1.3em; margin:.6em 0; }
.prose li { margin:.28em 0; }
.prose code { font-family:var(--mono); font-size:.86em; background:var(--bg-2);
  border:1px solid var(--border); padding:1px 5px; border-radius:5px; }
.prose blockquote { margin:1em 0; padding:.4em 1em; border-left:3px solid var(--accent);
  background:var(--bg-2); border-radius:0 8px 8px 0; color:var(--muted); }
.prose hr { border:none; border-top:1px solid var(--border); margin:1.6em 0; }
.prose a.wl { color:var(--accent); border-bottom:1px dotted color-mix(in srgb,var(--accent) 50%,transparent); }
.prose a.wl.broken { color:var(--broken); border-bottom-color:var(--broken); cursor:help; }
.prose a.ext::after { content:" ↗"; font-size:.8em; color:var(--muted); }

@media (max-width:820px) {
  .layout.note-view { grid-template-columns:1fr; }
  .sidebar { border-left:none; border-top:1px solid var(--border); }
  .content { padding:22px; }
  .nav { display:none; }
}
"""

GRAPH_JS = r"""
(function () {
  var data = window.GRAPH_DATA || {nodes: [], links: []};
  var canvas = document.getElementById('graph');
  var ctx = canvas.getContext('2d');
  var tooltip = document.getElementById('tooltip');
  var css = getComputedStyle(document.documentElement);
  var COLORS = {
    concept: css.getPropertyValue('--concept').trim() || '#6ea8fe',
    source:  css.getPropertyValue('--source').trim()  || '#7ee0a8',
    map:     css.getPropertyValue('--map').trim()      || '#f0b866'
  };
  var lineColor = css.getPropertyValue('--border').trim() || '#2a2f3d';
  var fgColor = css.getPropertyValue('--fg').trim() || '#e6e9ef';

  var nodes = data.nodes.map(function (n) {
    return {
      id: n.id, label: n.label, type: n.type, url: n.url, deg: n.deg,
      x: (Math.random() - 0.5) * 600, y: (Math.random() - 0.5) * 600,
      vx: 0, vy: 0
    };
  });
  var byId = {};
  nodes.forEach(function (n) { byId[n.id] = n; });
  var links = data.links.map(function (l) {
    return {source: byId[l.s], target: byId[l.t]};
  });
  var adjacency = {};
  links.forEach(function (l) {
    (adjacency[l.source.id] = adjacency[l.source.id] || {})[l.target.id] = 1;
    (adjacency[l.target.id] = adjacency[l.target.id] || {})[l.source.id] = 1;
  });

  function radius(n) { return 5 + Math.sqrt(n.deg) * 2.4; }

  // view transform
  var scale = 1, offsetX = 0, offsetY = 0;
  var W = 0, H = 0, dpr = window.devicePixelRatio || 1;

  function resize() {
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resize);
  resize();
  offsetX = W / 2; offsetY = H / 2;

  // force simulation
  var alpha = 1;
  function tick() {
    if (alpha > 0.005) alpha *= 0.985;
    var k = alpha;
    // repulsion (O(n^2) — fine for a few hundred nodes)
    for (var i = 0; i < nodes.length; i++) {
      var a = nodes[i];
      for (var j = i + 1; j < nodes.length; j++) {
        var b = nodes[j];
        var dx = a.x - b.x, dy = a.y - b.y;
        var d2 = dx * dx + dy * dy + 0.01;
        var force = 2600 / d2;
        var d = Math.sqrt(d2);
        var fx = (dx / d) * force, fy = (dy / d) * force;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      }
    }
    // springs
    links.forEach(function (l) {
      var dx = l.target.x - l.source.x, dy = l.target.y - l.source.y;
      var d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      var target = 90;
      var f = (d - target) * 0.015;
      var fx = (dx / d) * f, fy = (dy / d) * f;
      l.source.vx += fx; l.source.vy += fy;
      l.target.vx -= fx; l.target.vy -= fy;
    });
    // centering + integrate
    nodes.forEach(function (n) {
      if (n === dragging) return;
      n.vx += -n.x * 0.0016;
      n.vy += -n.y * 0.0016;
      n.vx *= 0.86; n.vy *= 0.86;
      n.x += n.vx * k * 4; n.y += n.vy * k * 4;
    });
  }

  function toScreen(n) {
    return {x: n.x * scale + offsetX, y: n.y * scale + offsetY};
  }
  function toWorld(px, py) {
    return {x: (px - offsetX) / scale, y: (py - offsetY) / scale};
  }

  var hovered = null;
  function draw() {
    ctx.clearRect(0, 0, W, H);
    // links
    ctx.lineWidth = 1;
    links.forEach(function (l) {
      var s = toScreen(l.source), t = toScreen(l.target);
      var hot = hovered && (l.source === hovered || l.target === hovered);
      ctx.strokeStyle = hot ? COLORS[hovered.type] : lineColor;
      ctx.globalAlpha = hot ? 0.9 : (hovered ? 0.15 : 0.5);
      ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y); ctx.stroke();
    });
    ctx.globalAlpha = 1;
    // nodes
    nodes.forEach(function (n) {
      var p = toScreen(n);
      var r = radius(n) * Math.max(0.7, Math.min(scale, 1.6));
      var dim = hovered && n !== hovered && !(adjacency[hovered.id] && adjacency[hovered.id][n.id]);
      ctx.globalAlpha = dim ? 0.25 : 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = COLORS[n.type] || '#888';
      ctx.fill();
      if (n === hovered) { ctx.lineWidth = 2; ctx.strokeStyle = fgColor; ctx.stroke(); }
      // labels for big / hovered / when zoomed in
      if (n === hovered || n.deg >= 5 || scale > 1.4) {
        ctx.globalAlpha = dim ? 0.3 : 1;
        ctx.fillStyle = fgColor;
        ctx.font = '11px -apple-system, Segoe UI, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(n.label, p.x, p.y - r - 4);
      }
    });
    ctx.globalAlpha = 1;
  }

  function frame() { tick(); draw(); requestAnimationFrame(frame); }
  frame();

  // interaction
  var dragging = null, panning = false, lastX = 0, lastY = 0, moved = false;

  function pick(px, py) {
    for (var i = nodes.length - 1; i >= 0; i--) {
      var p = toScreen(nodes[i]);
      var r = radius(nodes[i]) * Math.max(0.7, Math.min(scale, 1.6)) + 3;
      if ((px - p.x) * (px - p.x) + (py - p.y) * (py - p.y) <= r * r) return nodes[i];
    }
    return null;
  }

  canvas.addEventListener('mousedown', function (e) {
    var rect = canvas.getBoundingClientRect();
    var px = e.clientX - rect.left, py = e.clientY - rect.top;
    moved = false; lastX = e.clientX; lastY = e.clientY;
    var n = pick(px, py);
    if (n) { dragging = n; alpha = Math.max(alpha, 0.3); }
    else { panning = true; }
  });
  window.addEventListener('mousemove', function (e) {
    var rect = canvas.getBoundingClientRect();
    var px = e.clientX - rect.left, py = e.clientY - rect.top;
    if (Math.abs(e.clientX - lastX) + Math.abs(e.clientY - lastY) > 3) moved = true;
    if (dragging) {
      var w = toWorld(px, py); dragging.x = w.x; dragging.y = w.y;
      dragging.vx = 0; dragging.vy = 0;
    } else if (panning) {
      offsetX += e.clientX - lastX; offsetY += e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
    } else {
      var n = pick(px, py);
      hovered = n;
      canvas.style.cursor = n ? 'pointer' : 'grab';
      if (n) {
        tooltip.style.opacity = 1;
        tooltip.style.left = (px + 12) + 'px';
        tooltip.style.top = (py + 12) + 'px';
        tooltip.textContent = n.label + ' · ' + n.deg + ' links';
      } else { tooltip.style.opacity = 0; }
    }
  });
  window.addEventListener('mouseup', function (e) {
    if (dragging && !moved && dragging.url) window.location.href = dragging.url;
    dragging = null; panning = false;
  });
  canvas.addEventListener('wheel', function (e) {
    e.preventDefault();
    var rect = canvas.getBoundingClientRect();
    var px = e.clientX - rect.left, py = e.clientY - rect.top;
    var w = toWorld(px, py);
    var factor = e.deltaY < 0 ? 1.1 : 0.9;
    scale = Math.max(0.2, Math.min(4, scale * factor));
    offsetX = px - w.x * scale; offsetY = py - w.y * scale;
  }, {passive: false});

  // nav filter + hover-from-list
  var filter = document.getElementById('filter');
  if (filter) {
    filter.addEventListener('input', function () {
      var q = filter.value.toLowerCase();
      document.querySelectorAll('#nav-list li').forEach(function (li) {
        var t = li.textContent.toLowerCase();
        li.style.display = t.indexOf(q) >= 0 ? '' : 'none';
      });
    });
  }
})();
"""


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    notes, alias_index = load_notes()
    resolve_links(notes, alias_index)

    if OUT.exists():
        shutil.rmtree(OUT)
    NOTES_OUT.mkdir(parents=True)
    ASSETS_OUT.mkdir(parents=True)

    (ASSETS_OUT / "app.css").write_text(APP_CSS, encoding="utf-8")
    (ASSETS_OUT / "graph.js").write_text(GRAPH_JS, encoding="utf-8")

    for note in notes.values():
        html_page = render_note_page(note, notes, alias_index)
        (NOTES_OUT / f"{note['slug']}.html").write_text(html_page, encoding="utf-8")

    (OUT / "index.html").write_text(render_index(notes), encoding="utf-8")

    n_links = sum(len(n["links_out"]) for n in notes.values())
    print(f"Generated views/ from {len(notes)} notes ({n_links} resolved links).")
    print(f"  open: {OUT / 'index.html'}")


if __name__ == "__main__":
    main()
