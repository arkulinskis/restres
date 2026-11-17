"""Builds the how-to guide page from docs/howto (called by `howto.py build`).

The text is a small Markdown subset, so no library is needed:
  ### heading · #### smaller heading · paragraphs · "- " lists · "1. " steps · "> " a tip box · | tables |
  **bold** (button and field names) · *italic* · `code` · [link](https://...)
  ![caption](shot:<name>) on a line of its own = a screenshot; several on one line = side by side (phone shots).
The page follows the artifact page contract (no <html>/<head>/<body>; the publisher wraps it), so it can be published
as a claude.ai artifact as-is and still opens in a browser from disk.
"""
import base64
import datetime as dt
import html
import json
import re

PHONE_MAX = 900  # shots narrower than this many pixels are shown at phone size


def _inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    return t


def _figure(caption, name, shots_dir, sizes):
    f = shots_dir / (name + ".webp")
    if not f.exists():
        return '<p class="missing">Missing screenshot: %s</p>' % html.escape(name)
    w, h = sizes.setdefault(name, _size(f))
    data = base64.b64encode(f.read_bytes()).decode()
    cls = "shot phone" if w < PHONE_MAX else "shot"
    return ('<figure class="%s"><img src="data:image/webp;base64,%s" width="%d" height="%d" alt="%s" loading="lazy">'
            '<figcaption>%s</figcaption></figure>') % (cls, data, w, h, html.escape(caption), _inline(caption))


def _size(path):
    b = path.read_bytes()  # WebP header: VP8 / VP8L / VP8X
    kind = b[12:16]
    if kind == b"VP8X":
        return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
    if kind == b"VP8L":
        bits = int.from_bytes(b[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return int.from_bytes(b[26:28], "little") & 0x3FFF, int.from_bytes(b[28:30], "little") & 0x3FFF


def markdown(text, shots_dir, sizes):
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        first = lines[0]
        if first.startswith("#### "):
            out.append("<h4>%s</h4>" % _inline(first[5:]))
        elif first.startswith("### "):
            out.append("<h3>%s</h3>" % _inline(first[4:]))
        elif all(l.startswith("> ") or l == ">" for l in lines):
            out.append('<aside class="tip">%s</aside>' % "<br>".join(_inline(l[2:]) for l in lines))
        elif all(re.match(r"\s*!\[[^\]]*\]\(shot:[\w-]+\)\s*$", l) or not l.strip() for l in lines) or re.fullmatch(r"(\s*!\[[^\]]*\]\(shot:[\w-]+\)\s*)+", block):
            figs = re.findall(r"!\[([^\]]*)\]\(shot:([\w-]+)\)", block)
            inner = "".join(_figure(c, n, shots_dir, sizes) for c, n in figs)
            out.append('<div class="figs">%s</div>' % inner if len(figs) > 1 else inner)
        elif first.startswith("|"):
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines if not re.match(r"^\|[\s:|-]+\|$", l.strip())]
            head, body = rows[0], rows[1:]
            out.append('<div class="table"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
                "".join("<th>%s</th>" % _inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % _inline(c) for c in r) for r in body)))
        elif re.match(r"\d+\. ", first):
            items, cur = [], None
            for l in lines:
                m = re.match(r"\d+\. (.*)", l)
                if m:
                    cur = [m.group(1)]; items.append(cur)
                elif cur is not None:
                    cur.append(l.strip())
            out.append('<ol class="steps">%s</ol>' % "".join("<li>%s</li>" % _inline(" ".join(i)) for i in items))
        elif first.startswith("- "):
            items, cur = [], None
            for l in lines:
                if l.startswith("- "):
                    cur = [l[2:]]; items.append(cur)
                elif cur is not None:
                    cur.append(l.strip())
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % _inline(" ".join(i)) for i in items))
        else:
            out.append("<p>%s</p>" % _inline(" ".join(l.strip() for l in lines)))
    return "\n".join(out)


CSS = r"""
/* Layout: PlanPlate's ivory paper, a sticky contents column on wide screens, one reading column of ~68ch. */
:root {
  --bg: #f6f3ee; --surface: #fffdf9; --surface-2: #f1ede6; --ink: #1d1b18; --muted: #6f6a62; --line: #e4ded4;
  --accent: #826638; --accent-soft: #f3ebdc; --tip: #e5efe7; --tip-ink: #2f5a3d;
  --font-body: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Cormorant Garamond", "Iowan Old Style", Georgia, serif;
  --shadow: 0 1px 2px rgba(29, 27, 24, .05), 0 12px 32px rgba(29, 27, 24, .08);
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121110; --surface: #1b1a18; --surface-2: #23211e; --ink: #ece7de; --muted: #a39d92; --line: #2e2b27;
  --accent: #c9a56a; --accent-soft: #2c2519; --tip: #1d2a21; --tip-ink: #a7d1b2; --shadow: 0 0 0 1px #2e2b27; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #121110; --surface: #1b1a18; --surface-2: #23211e; --ink: #ece7de; --muted: #a39d92; --line: #2e2b27;
  --accent: #c9a56a; --accent-soft: #2c2519; --tip: #1d2a21; --tip-ink: #a7d1b2; --shadow: 0 0 0 1px #2e2b27; color-scheme: dark; }
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font: 16px/1.65 var(--font-body); }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 40px 80px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 56px; }
header.top { grid-column: 1 / -1; display: grid; gap: 10px; padding-bottom: 28px; border-bottom: 1px solid var(--line); }
.brand { display: flex; align-items: center; gap: 10px; color: var(--accent); font-weight: 600; font-size: .85rem; letter-spacing: .08em; text-transform: uppercase; }
.brand svg { width: 26px; height: 26px; }
h1 { font: 500 clamp(2.4rem, 5vw, 3.6rem)/1.05 var(--font-display); margin: 0; text-wrap: balance; }
.lead { color: var(--muted); font-size: 1.1rem; margin: 0; max-width: 60ch; }
.meta { color: var(--muted); font-size: .85rem; margin: 0; }
nav.toc { position: sticky; top: calc(env(safe-area-inset-top, 0px) + 24px); align-self: start; max-height: calc(100vh - 48px); overflow: auto; font-size: .92rem; }
nav.toc h2 { font: 600 .75rem/1 var(--font-body); letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin: 0 0 12px; }
nav.toc ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
nav.toc a { display: block; padding: 6px 10px; border-radius: 8px; color: var(--ink); text-decoration: none; }
nav.toc a:hover, nav.toc a:focus-visible { background: var(--surface-2); }
nav.toc a.on { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
main { min-width: 0; display: grid; gap: 72px; }
section { display: grid; gap: 14px; scroll-margin-top: 24px; }
section > * { margin: 0; }
section > p, section > ul, section > ol, section > aside, section > h3, section > h4 { max-width: 68ch; }
.sec-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; }
h2 { font: 500 2.1rem/1.15 var(--font-display); margin: 0; text-wrap: balance; }
.who { font-size: .75rem; font-weight: 600; letter-spacing: .04em; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 3px 11px; white-space: nowrap; }
h3 { font: 600 1.05rem/1.3 var(--font-body); margin-top: 12px; }
h4 { font: 600 .95rem/1.3 var(--font-body); color: var(--muted); }
ul, ol { padding-left: 1.3em; display: grid; gap: 6px; }
ol.steps { list-style: none; padding: 0; counter-reset: s; gap: 10px; }
ol.steps li { counter-increment: s; display: grid; grid-template-columns: 28px 1fr; gap: 10px; align-items: baseline; }
ol.steps li::before { content: counter(s); width: 24px; height: 24px; border-radius: 50%; background: var(--ink); color: var(--bg);
  font-size: .78rem; font-weight: 600; display: inline-grid; place-items: center; font-variant-numeric: tabular-nums; transform: translateY(-1px); }
strong { font-weight: 600; }
code { font: .88em ui-monospace, "Cascadia Mono", Consolas, monospace; background: var(--surface-2); padding: 1px 5px; border-radius: 5px; }
a { color: var(--accent); }
aside.tip { background: var(--tip); color: var(--tip-ink); border-radius: 12px; padding: 12px 16px; font-size: .95rem; }
figure.shot { margin: 8px 0 4px; display: grid; gap: 8px; }
figure.shot img { width: 100%; height: auto; border-radius: 12px; border: 1px solid var(--line); box-shadow: var(--shadow); background: var(--surface); }
figure.shot.phone { max-width: 300px; }
figcaption { color: var(--muted); font-size: .85rem; }
.figs { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }
.figs > figure { flex: 1 1 260px; }
.figs > figure.phone { flex: 0 1 280px; }
.table { overflow-x: auto; max-width: 100%; }
table { border-collapse: collapse; font-size: .92rem; min-width: 480px; background: var(--surface); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
th, td { text-align: left; padding: 9px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600; background: var(--surface-2); }
tr:last-child td { border-bottom: 0; }
.missing { color: #a23b2c; font-weight: 600; }
footer.end { grid-column: 1 / -1; border-top: 1px solid var(--line); padding-top: 20px; color: var(--muted); font-size: .85rem; }
@media (max-width: 860px) {
  .wrap { grid-template-columns: minmax(0, 1fr); gap: 32px; padding-block: 24px 60px; }
  nav.toc { position: static; max-height: none; background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 16px; }
  nav.toc ol { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
  main { gap: 56px; }
  h2 { font-size: 1.8rem; }
}
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
"""

JS = r"""
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('nav.toc a'));
  var byId = {}; links.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
  if (!('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { links.forEach(function (a) { a.classList.remove('on'); });
      var a = byId[e.target.id]; if (a) a.classList.add('on'); } });
  }, { rootMargin: '-20% 0px -70% 0px' });
  document.querySelectorAll('main section').forEach(function (s) { io.observe(s); });
})();
"""

LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" stroke-width="1.6"/>'
        '<circle cx="16" cy="16" r="9.5" fill="none" stroke="currentColor" stroke-width="1"/><path d="M16 9v14" stroke="currentColor" stroke-width="1.6"/></svg>')


def build_html(guide, docs, shots_dir):
    sizes = {}
    manifest = json.loads((shots_dir / "manifest.json").read_text(encoding="utf-8")) if (shots_dir / "manifest.json").exists() else {}
    taken = max((v["taken"] for v in manifest.values()), default=dt.datetime.now().isoformat())
    when = dt.datetime.fromisoformat(taken).strftime("%B %Y").replace(" 0", " ")
    toc, body = [], []
    for s in guide["sections"]:
        md = docs / "sections" / (s["id"] + ".md")
        text = md.read_text(encoding="utf-8") if md.exists() else "*This section has no text yet.*"
        toc.append('<li><a href="#%s">%s</a></li>' % (s["id"], html.escape(s["title"])))
        body.append('<section id="%s"><div class="sec-head"><h2>%s</h2><span class="who">%s</span></div>\n%s\n</section>' % (
            s["id"], html.escape(s["title"]), html.escape(s["who"]), markdown(text, shots_dir, sizes)))
    title = guide["title"]
    return """<meta charset="utf-8">
<title>%(title)s</title>
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="%(sub)s">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Inter:wght@400;500;600&display=swap">
<style>%(css)s</style>
<div class="wrap">
<header class="top"><div class="brand">%(logo)s PlanPlate</div><h1>How to use PlanPlate</h1><p class="lead">%(sub)s</p>
<p class="meta">Screenshots from the demo restaurant, Maison Lumière · updated %(when)s</p></header>
<nav class="toc" aria-label="Contents"><h2>Contents</h2><ol>%(toc)s</ol></nav>
<main>
%(body)s
</main>
<footer class="end">PlanPlate · questions or ideas: use <strong>Submit feedback</strong> at the bottom of any PlanPlate page.</footer>
</div>
<script>%(js)s</script>
""" % {"title": html.escape(title), "sub": html.escape(guide.get("subtitle", "")), "css": CSS, "logo": LOGO, "when": when,
       "toc": "".join(toc), "body": "\n".join(body), "js": JS}
