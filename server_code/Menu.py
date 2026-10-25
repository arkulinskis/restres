# Menu — Server Module. The restaurant's menu, and the live feeds for its website:
#   managers: get_menu_admin, save_section, delete_section, save_item, delete_item, move_menu_row  (Portal access rules)
#   guests:   get_menu(slug) for the public menu page (#menu/<slug>, the menu QR code points here)
#   website:  /_/api/menu?r=<slug>  (JSON)   /_/api/menu.js?r=<slug>  (draws the menu into [data-planplate-menu])
#             /_/api/hours?r=<slug> (JSON)   /_/api/hours.js?r=<slug> (draws opening hours into [data-planplate-hours])
# The feeds read the live data on every request, so a change in the portal shows on the website at once.
import json
from datetime import timedelta

import anvil.server
from anvil.tables import app_tables

from . import Booking as B
from .Portal import _rest, _child, _nav

TAGS = {"V": "Vegetarian", "VG": "Vegan", "GF": "Gluten-free", "DF": "Dairy-free", "N": "Contains nuts", "S": "Spicy"}


def _sections(r):
    return sorted(app_tables.menu_sections.search(restaurant=r), key=lambda s: (s["position"] or 0))


def _menu(r, include_hidden=False):
    items = list(app_tables.menu_items.search(restaurant=r))
    out = []
    for s in _sections(r):
        its = sorted([i for i in items if i["section"] == s and (include_hidden or i["available"] is not False)], key=lambda i: (i["position"] or 0))
        out.append({"id": s.get_id(), "title": s["title"] or "", "description": s["description"] or "",
                    "items": [{"id": i.get_id(), "name": i["name"] or "", "description": i["description"] or "", "price": i["price"] or "",
                               "tags": [t for t in (i["tags"] or []) if t in TAGS], "available": i["available"] is not False} for i in its]})
    if not include_hidden:
        out = [s for s in out if s["items"]]
    return out


# ---------------------------------------------------------------- manager
def _admin(r):
    return {"ok": True, "nav": _nav(r), "sections": _menu(r, include_hidden=True), "tags": TAGS, "slug": r["slug"]}


@anvil.server.callable(require_user=True)
def get_menu_admin(rid):
    return _admin(_rest(rid, "manager"))


@anvil.server.callable(require_user=True)
def save_section(rid, data):
    r = _rest(rid, "manager")
    data = dict(data or {})
    title = str(data.get("title") or "").strip()[:80]
    if not title:
        return {"ok": False, "error": "Give the section a title, e.g. Starters."}
    fields = {"title": title, "description": str(data.get("description") or "").strip()[:300]}
    if data.get("id"):
        _child(app_tables.menu_sections, r, data["id"]).update(**fields)
    else:
        app_tables.menu_sections.add_row(restaurant=r, position=len(_sections(r)), **fields)
    return _admin(r)


@anvil.server.callable(require_user=True)
def delete_section(rid, sid):
    r = _rest(rid, "manager")
    s = _child(app_tables.menu_sections, r, sid)
    for i in list(app_tables.menu_items.search(section=s)):
        i.delete()
    s.delete()
    return _admin(r)


@anvil.server.callable(require_user=True)
def save_item(rid, data):
    r = _rest(rid, "manager")
    data = dict(data or {})
    name = str(data.get("name") or "").strip()[:120]
    if not name:
        return {"ok": False, "error": "Give the dish a name."}
    fields = {"name": name, "description": str(data.get("description") or "").strip()[:500],
              "price": str(data.get("price") or "").strip()[:30],
              "tags": [t for t in (data.get("tags") or []) if t in TAGS]}
    if "available" in data:
        fields["available"] = bool(data["available"])
    if data.get("id"):
        item = _child(app_tables.menu_items, r, data["id"])
        if data.get("section_id") and data["section_id"] != item["section"].get_id():
            fields["section"] = _child(app_tables.menu_sections, r, data["section_id"])
        item.update(**fields)
    else:
        s = _child(app_tables.menu_sections, r, data.get("section_id"))
        n = len(list(app_tables.menu_items.search(section=s)))
        app_tables.menu_items.add_row(restaurant=r, section=s, position=n, available=fields.pop("available", True), **fields)
    return _admin(r)


@anvil.server.callable(require_user=True)
def delete_item(rid, iid):
    r = _rest(rid, "manager")
    _child(app_tables.menu_items, r, iid).delete()
    return _admin(r)


@anvil.server.callable(require_user=True)
def move_menu_row(rid, kind, row_id, step):
    """Move a section or an item one place up (step -1) or down (+1)."""
    r = _rest(rid, "manager")
    if kind == "section":
        rows = _sections(r)
    else:
        item = _child(app_tables.menu_items, r, row_id)
        rows = sorted(app_tables.menu_items.search(section=item["section"]), key=lambda i: (i["position"] or 0))
    ids = [x.get_id() for x in rows]
    if row_id in ids:
        i = ids.index(row_id)
        j = max(0, min(len(rows) - 1, i + (1 if step > 0 else -1)))
        rows[i], rows[j] = rows[j], rows[i]
        for n, x in enumerate(rows):
            x["position"] = n
    return _admin(r)


# ---------------------------------------------------------------- public
def _find(slug):
    slug = str(slug or "").strip().lower()
    return app_tables.restaurants.get(slug=slug) if slug else None


@anvil.server.callable
def get_menu(slug):
    r = _find(slug)
    if r is None:
        return {"ok": False, "error": "We couldn't find this restaurant."}
    return {"ok": True, "restaurant": B.public_restaurant(r), "sections": _menu(r), "tags": TAGS}


def hours_feed(r, days=7):
    """Opening hours for the website: the regular week now in force, the next `days` days, and special days ahead."""
    ctx = B.Ctx(r)
    today = B.local_now(r).date()
    p = B.period_for(ctx.periods, today)
    week = []
    for i in range(7):
        iv = B.clean_intervals((p["week"] or {}).get(str(i), [])) if p else []
        week.append({"day": B.DAY_NAMES[i], "hours": B.intervals_text(iv), "closed": not iv})
    upcoming = []
    for n in range(days):
        d = today + timedelta(days=n)
        iv, src = B.day_hours(ctx, d)
        upcoming.append({"date": d.isoformat(), "day": B.DAY_NAMES[d.weekday()], "hours": B.intervals_text(iv), "closed": not iv,
                         "special": src["label"] if src["kind"] == "special" else None})
    specials = [{"date": s["date"].isoformat(), "label": s["label"] or "", "closed": bool(s["closed"]),
                 "hours": B.intervals_text(B.clean_intervals(s["hours"]))}
                for s in sorted(ctx.specials.values(), key=lambda s: s["date"]) if today <= s["date"] <= today + timedelta(days=90)]
    return {"restaurant": r["name"], "timezone": r["timezone"] or "UTC", "today": today.isoformat(),
            "period": p["name"] if p else None, "week": week, "next_days": upcoming, "special_days": specials}


def _json(data):
    return anvil.server.HttpResponse(200, json.dumps(data), headers={
        "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=60"})


def _js(body):
    return anvil.server.HttpResponse(200, body, headers={"Content-Type": "application/javascript; charset=utf-8", "Cache-Control": "max-age=60"})


def _missing():
    return anvil.server.HttpResponse(404, json.dumps({"error": "No restaurant with that link (use ?r=<booking-link name>)."}),
                                     headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})


@anvil.server.http_endpoint("/menu")
def menu_json(r=None, **kw):
    rest = _find(r)
    if rest is None:
        return _missing()
    return _json({"restaurant": rest["name"], "sections": _menu(rest), "tags": TAGS})


@anvil.server.http_endpoint("/hours")
def hours_json(r=None, **kw):
    rest = _find(r)
    if rest is None:
        return _missing()
    return _json(hours_feed(rest))


# The widgets draw plain, unstyled-but-tidy HTML that takes the website's own fonts and colours.
WIDGET_JS = r"""(function(){
  var DATA=%(data)s, KIND=%(kind)s;
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function menu(){
    return DATA.sections.map(function(s){
      return '<section class="pp-menu-section" style="margin:0 0 1.6em"><h3 style="margin:0 0 .2em">'+esc(s.title)+'</h3>'+
        (s.description?'<p style="margin:0 0 .8em;opacity:.7">'+esc(s.description)+'</p>':'')+
        s.items.map(function(i){
          return '<div class="pp-menu-item" style="margin:.7em 0"><div style="display:flex;gap:.6em;align-items:baseline"><strong>'+esc(i.name)+'</strong>'+
            (i.tags.length?'<small style="opacity:.6">'+esc(i.tags.join(' · '))+'</small>':'')+
            '<span style="flex:1;border-bottom:1px dotted currentColor;opacity:.3"></span><span>'+esc(i.price)+'</span></div>'+
            (i.description?'<div style="opacity:.7;font-size:.92em">'+esc(i.description)+'</div>':'')+'</div>';
        }).join('')+'</section>';
    }).join('');
  }
  function hours(){
    var rows=DATA.week.map(function(d){return '<tr><td style="padding:.2em 1.2em .2em 0">'+esc(d.day)+'</td><td>'+(d.closed?'Closed':esc(d.hours.map(function(h){return h[0]+'–'+h[1];}).join(', ')))+'</td></tr>';}).join('');
    var sp=DATA.special_days.slice(0,5).map(function(s){return '<li>'+esc(new Date(s.date+'T12:00').toLocaleDateString(undefined,{day:'numeric',month:'short'}))+' · '+esc(s.label||'')+': '+(s.closed?'Closed':esc(s.hours.map(function(h){return h[0]+'–'+h[1];}).join(', ')))+'</li>';}).join('');
    return '<table class="pp-hours" style="border-collapse:collapse">'+rows+'</table>'+(sp?'<ul class="pp-hours-special" style="padding-left:1.1em;margin:.8em 0 0">'+sp+'</ul>':'');
  }
  var html=KIND==='menu'?menu():hours();
  function draw(){document.querySelectorAll('[data-planplate-'+KIND+']').forEach(function(el){el.innerHTML=html;});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',draw);else draw();
})();
"""


@anvil.server.http_endpoint("/menu.js")
def menu_js(r=None, **kw):
    rest = _find(r)
    if rest is None:
        return _missing()
    return _js(WIDGET_JS % {"data": json.dumps({"sections": _menu(rest)}), "kind": json.dumps("menu")})


@anvil.server.http_endpoint("/hours.js")
def hours_js(r=None, **kw):
    rest = _find(r)
    if rest is None:
        return _missing()
    return _js(WIDGET_JS % {"data": json.dumps(hours_feed(rest)), "kind": json.dumps("hours")})
