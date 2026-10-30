# Board — Server Module. The restaurant's day, for the owner checking in from a phone:
#   get_today          the Today page: open now?, today's bookings, the week ahead, specials, photo of the day,
#                      upcoming events, website visits, and a set-up checklist
#   quick_hours        close today / change today's hours / back to regular hours (writes a special day)
#   specials           dishes of the day or week (save_dish_special, toggle_dish_special, delete_dish_special)
#   posts              photo of the day (post_photo, delete_post), shown on the restaurant's website
#   events             planned events with their own room set-up (get_events, save_event, save_event_setup, delete_event)
# Every callable checks the user's role with Portal._rest. Staff can see Today and post the photo of the day.
from datetime import date, timedelta

import anvil.server
import anvil.users
from anvil.tables import app_tables

from . import Booking as B
from . import Media as MD
from .Portal import _rest, _child, _nav, _user, _role, _pending, _int, ROLES

KINDS = ("public", "private")


# ---------------------------------------------------------------- views
def showing_on(s, d):
    """Is this special on the menu on date d?"""
    if s["active"] is False:
        return False
    if s["start"] is not None and d < s["start"]:
        return False
    if s["end"] is not None and d > s["end"]:
        return False
    days = s["days"] or []
    return not days or d.weekday() in days


def special_view(s, today, origin=None):
    days = sorted(s["days"] or [])
    return {"id": s.get_id(), "title": s["title"] or "", "description": s["description"] or "", "price": s["price"] or "",
            "photo": MD.view(s["photo"], origin), "start": B.iso(s["start"]), "end": B.iso(s["end"]), "days": days,
            "active": s["active"] is not False, "today": showing_on(s, today),
            "expired": s["end"] is not None and s["end"] < today}


def specials(r):
    return sorted(app_tables.specials.search(restaurant=r), key=lambda s: (s["position"] or 0, B._created_key(s)))


def specials_on(r, d):
    return [s for s in specials(r) if showing_on(s, d)]


def post_view(p, origin=None):
    by = p["by"]
    return {"id": p.get_id(), "date": B.iso(p["date"]), "text": p["text"] or "", "photo": MD.view(p["photo"], origin),
            "by": (by["display_name"] or (by["email"] or "").split("@")[0].title()) if by else ""}


def posts(r, limit=12):
    rows = list(app_tables.posts.search(restaurant=r))
    rows.reverse()  # newest added first, so two posts in the same instant keep that order
    rows.sort(key=lambda p: (p["date"], B._created_key(p)), reverse=True)
    return rows[:limit]


def latest_post(r, today, max_age=3):
    """The newest photo of the day from the last few days (the website shows it), or None."""
    for p in posts(r, 5):
        if p["date"] <= today and (today - p["date"]).days <= max_age and (p["photo"] is not None or p["text"]):
            return p
    return None


def event_view(e, origin=None):
    return {"id": e.get_id(), "title": e["title"] or "", "date": B.iso(e["date"]), "start": B.hm(int(e["start_min"] or 0)),
            "end": B.hm(int(e["end_min"] or 0)), "kind": e["kind"] or "public", "description": e["description"] or "",
            "photo": MD.view(e["photo"], origin), "guests": int(e["guests"] or 0), "host": e["host"] or "", "notes": e["notes"] or "",
            "blocks": bool(e["blocks"]), "on_site": bool(e["on_site"]), "has_setup": e["layout"] is not None,
            "layout": e["layout"] or {}, "groups": e["groups"] or [], "removed": e["removed"] or []}


def events_between(r, a, b):
    return sorted([e for e in app_tables.events.search(restaurant=r) if a <= e["date"] <= b],
                  key=lambda e: (e["date"], int(e["start_min"] or 0)))


def public_events(r, today, days=90):
    return [e for e in events_between(r, today, today + timedelta(days=days)) if e["on_site"]]


# ---------------------------------------------------------------- Today
def _status(iv, t):
    """("open"|"later"|"closed", text) for the restaurant right now."""
    for o, c in iv:
        if o <= t < c:
            return "open", "Open now, until %s" % B.hm(c)
    later = [o for o, c in iv if o > t]
    if later:
        return "later", "Closed now, opens at %s" % B.hm(min(later))
    return "closed", "Closed for the rest of the day" if iv else "Closed today"


def _checklist(r, s):
    gallery = len(MD.gallery_photos(r))
    has_menu = bool(list(app_tables.menu_items.search(restaurant=r)))
    return [
        {"key": "hours", "label": "Opening hours", "done": bool(list(app_tables.periods.search(restaurant=r))), "page": "hours"},
        {"key": "tables", "label": "Tables and floor plan", "done": bool(list(app_tables.dining_tables.search(restaurant=r))), "page": "tables"},
        {"key": "menu", "label": "Menu", "done": has_menu, "page": "menu"},
        {"key": "gallery", "label": "At least 4 gallery photos", "done": gallery >= 4, "page": "gallery"},
        {"key": "website", "label": "Website published", "done": bool(s and s["published"]), "page": "website"},
    ]


def week_visits(s, today):
    v = (s["visits"] or {}) if s else {}
    return sum(int(v.get((today - timedelta(days=i)).isoformat(), 0)) for i in range(7))


def _today(r):
    ctx = B.Ctx(r)
    now = B.local_now(r)
    today, t = now.date(), now.hour * 60 + now.minute
    iv, src = B.day_hours(ctx, today)
    state, status = _status(iv, t)
    res = sorted(ctx.reservations(today), key=lambda x: int(x["start_min"] or 0))
    arrivals = []
    for x in res:
        start, end = int(x["start_min"] or 0), int(x["start_min"] or 0) + int(x["duration"] or 0)
        if end <= t:
            continue
        arrivals.append({"id": x.get_id(), "time": B.hm(start), "name": x["name"] or "", "party": int(x["party"] or 0),
                         "status": x["status"], "seated": start <= t,
                         "tables": [ctx.by_id[i]["name"] for i in (x["tables"] or []) if i in ctx.by_id]})
    busy = B.busy_ids(ctx, today, t, 1)
    week = []
    for n in range(7):
        d = today + timedelta(days=n)
        div, dsrc = B.day_hours(ctx, d)
        rs = ctx.reservations(d)
        week.append({"date": d.isoformat(), "hours": B.intervals_text(div), "label": dsrc["label"] if dsrc["kind"] == "special" else "",
                     "bookings": len(rs), "covers": sum(int(x["party"] or 0) for x in rs),
                     "events": [e["title"] for e in B.events_on(ctx, d)]})
    s = MD.site_row(r, create=False)
    origin = anvil.server.get_app_origin()
    role = _role(r, _user())
    return {
        "ok": True, "nav": _nav(r), "role": role, "can_manage": ROLES[role] >= ROLES["manager"],
        "today": today.isoformat(), "now": B.hm(t), "weekday": B.DAY_NAMES[today.weekday()],
        "status": {"state": state, "text": status, "hours": B.intervals_text(iv), "kind": src["kind"], "label": src["label"]},
        "stats": {"bookings": len(res), "covers": sum(int(x["party"] or 0) for x in res), "pending": len(_pending(r)),
                  "in_now": sum(int(x["party"] or 0) for x in res if int(x["start_min"]) <= t < int(x["start_min"]) + int(x["duration"] or 0)),
                  "free_tables": len([x for x in ctx.tables if x.get_id() not in busy]), "tables": len(ctx.tables)},
        "arrivals": arrivals[:8], "more_arrivals": max(0, len(arrivals) - 8), "week": week,
        "specials": [special_view(x, today, origin) for x in specials(r) if not (x["end"] is not None and x["end"] < today)],
        "posts": [post_view(p, origin) for p in posts(r, 6)],
        "events": [event_view(e, origin) for e in events_between(r, today, today + timedelta(days=30))][:6],
        "site": {"exists": s is not None, "published": bool(s and s["published"]), "path": s["path"] if s else "",
                 "url": origin + "/_/api/site/" + s["path"] if s else "", "visits_week": week_visits(s, today),
                 "views": int((s["views"] or 0) if s else 0)},
        "checklist": _checklist(r, s),
        "default_hours": _regular_hours(ctx, today),
    }


def _regular_hours(ctx, d):
    """The regular (period) hours for date d, ignoring special days: what "back to regular hours" restores."""
    p = B.period_for(ctx.periods, d)
    return B.intervals_text(B.clean_intervals((p["week"] or {}).get(str(d.weekday()), []))) if p else []


@anvil.server.callable(require_user=True)
def get_today(rid):
    return _today(_rest(rid))


@anvil.server.callable(require_user=True)
def quick_hours(rid, action, hours=None, label=None):
    """Change today only: "close" (closed today), "hours" (these hours today), "regular" (remove today's exception)."""
    r = _rest(rid, "manager")
    today = B.local_now(r).date()
    row = app_tables.special_days.get(restaurant=r, date=today)
    if action == "regular":
        if row is not None:
            row.delete()
        return dict(_today(r), ok=True, message="Back to the regular hours today.")
    if action == "close":
        fields = {"label": str(label or "").strip()[:60] or "Closed today", "closed": True, "hours": []}
    elif action == "hours":
        iv = B.intervals_text(B.clean_intervals(hours))
        if not iv:
            return {"ok": False, "error": "Add at least one opening time, like 12:00 to 22:00."}
        fields = {"label": str(label or "").strip()[:60] or "Changed hours today", "closed": False, "hours": iv}
    else:
        return {"ok": False, "error": "Unknown action."}
    if row is None:
        app_tables.special_days.add_row(restaurant=r, date=today, **fields)
    else:
        row.update(**fields)
    return dict(_today(r), ok=True, message="Today's hours are updated everywhere: booking form, website and widgets.")


# ---------------------------------------------------------------- specials
def _date_or_none(v):
    return B.parse_date(v) if v else None


@anvil.server.callable(require_user=True)
def save_dish_special(rid, data):
    """A dish of the day/week. when: "today" | "dates" (start/end) | "always"; days: weekdays (empty = every day)."""
    r = _rest(rid, "manager")
    data = dict(data or {})
    title = str(data.get("title") or "").strip()[:80]
    if not title:
        return {"ok": False, "error": "Give the special a name."}
    today = B.local_now(r).date()
    when = data.get("when") or "dates"
    try:
        if when == "today":
            start = end = today
        elif when == "always":
            start = end = None
        else:
            start, end = _date_or_none(data.get("start")), _date_or_none(data.get("end"))
    except ValueError:
        return {"ok": False, "error": "Check the dates."}
    if start and end and end < start:
        return {"ok": False, "error": "The last day is before the first day."}
    days = sorted({_int(x, 0, 6) for x in (data.get("days") or [])})
    photo = MD.by_key(r, data.get("photo")) if data.get("photo") else None
    fields = {"title": title, "description": str(data.get("description") or "").strip()[:300],
              "price": str(data.get("price") or "").strip()[:30], "start": start, "end": end,
              "days": [] if len(days) == 7 else days, "photo": photo, "active": data.get("active", True) is not False}
    if data.get("id"):
        _child(app_tables.specials, r, data["id"]).update(**fields)
    else:
        app_tables.specials.add_row(restaurant=r, position=len(specials(r)), created=B.now_utc(), **fields)
    return dict(_today(r), ok=True)


@anvil.server.callable(require_user=True)
def toggle_dish_special(rid, sid, active):
    r = _rest(rid, "manager")
    _child(app_tables.specials, r, sid)["active"] = bool(active)
    return dict(_today(r), ok=True)


@anvil.server.callable(require_user=True)
def delete_dish_special(rid, sid):
    r = _rest(rid, "manager")
    _child(app_tables.specials, r, sid).delete()
    return dict(_today(r), ok=True)


# ---------------------------------------------------------------- photo of the day
@anvil.server.callable(require_user=True)
def post_photo(rid, data):
    """Post today's photo (already uploaded: its key) with a line of text. Staff can post."""
    r = _rest(rid)
    data = dict(data or {})
    photo = MD.by_key(r, data.get("photo"))
    text = str(data.get("text") or "").strip()[:280]
    if photo is None and not text:
        return {"ok": False, "error": "Add a photo, or write a line about today."}
    if photo is not None and data.get("add_to_gallery") and (photo["kind"] or "image") == "image":
        photo["in_gallery"] = True
        if text and not photo["caption"]:
            photo["caption"] = text[:200]
    app_tables.posts.add_row(restaurant=r, date=B.local_now(r).date(), photo=photo, text=text, created=B.now_utc(), by=_user())
    return dict(_today(r), ok=True)


@anvil.server.callable(require_user=True)
def delete_post(rid, pid):
    """Managers can delete any post; staff only their own."""
    r = _rest(rid)
    p = _child(app_tables.posts, r, pid)
    if ROLES[_role(r, _user())] < ROLES["manager"] and p["by"] != _user():
        raise anvil.server.PermissionDenied("Only a manager can delete someone else's post.")
    p.delete()
    return dict(_today(r), ok=True)


# ---------------------------------------------------------------- events
def _events_reply(r):
    ctx = B.Ctx(r)
    today = B.local_now(r).date()
    rows = sorted(app_tables.events.search(restaurant=r), key=lambda e: (e["date"], int(e["start_min"] or 0)))
    origin = anvil.server.get_app_origin()
    upcoming = [event_view(e, origin) for e in rows if e["date"] >= today]
    past = [event_view(e, origin) for e in reversed(rows) if e["date"] < today][:12]
    for v in upcoming:  # how many bookings already overlap each upcoming event (to call guests of a private event)
        e = next(x for x in rows if x.get_id() == v["id"])
        a, b = int(e["start_min"] or 0), int(e["end_min"] or 0)
        clash = [x for x in ctx.reservations(e["date"]) if int(x["start_min"]) < b and a < int(x["start_min"]) + int(x["duration"] or 0)]
        v["bookings"] = len(clash)
        v["covers"] = sum(int(x["party"] or 0) for x in clash)
    return {"ok": True, "nav": _nav(r), "today": today.isoformat(), "upcoming": upcoming, "past": past,
            "tables": [B.table_view(t) for t in ctx.tables], "joins": [B.join_view(j) for j in ctx.joins],
            "seats": ctx.total_seats}


@anvil.server.callable(require_user=True)
def get_events(rid):
    return _events_reply(_rest(rid, "manager"))


@anvil.server.callable(require_user=True)
def save_event(rid, data):
    r = _rest(rid, "manager")
    data = dict(data or {})
    title = str(data.get("title") or "").strip()[:100]
    if not title:
        return {"ok": False, "error": "Give the event a name."}
    try:
        d = B.parse_date(data.get("date"))
        a, b = B.parse_hm(data.get("start")), B.parse_hm(data.get("end"), closing=True)
    except ValueError:
        return {"ok": False, "error": "Pick a date, a start time and an end time."}
    if b <= a:
        return {"ok": False, "error": "The event ends before it starts. (Events past midnight: end at 00:00.)"}
    kind = data.get("kind") if data.get("kind") in KINDS else "public"
    blocks = bool(data.get("blocks")) if "blocks" in data else kind == "private"
    on_site = bool(data.get("on_site")) if "on_site" in data else kind == "public"
    photo = MD.by_key(r, data.get("photo")) if data.get("photo") else None
    fields = {"title": title, "date": d, "start_min": a, "end_min": b, "kind": kind, "blocks": blocks, "on_site": on_site,
              "description": str(data.get("description") or "").strip()[:1000], "photo": photo,
              "guests": _int(data.get("guests"), 0, 2000, 0), "host": str(data.get("host") or "").strip()[:200],
              "notes": str(data.get("notes") or "").strip()[:1000]}
    if data.get("id"):
        e = _child(app_tables.events, r, data["id"])
        e.update(**fields)
    else:
        e = app_tables.events.add_row(restaurant=r, created=B.now_utc(), layout=None, groups=None, removed=None, **fields)
    return dict(_events_reply(r), ok=True, id=e.get_id())


@anvil.server.callable(require_user=True)
def save_event_setup(rid, eid, data):
    """The room for this event: table positions, tables pushed together, tables taken out. data.reset → everyday layout."""
    r = _rest(rid, "manager")
    e = _child(app_tables.events, r, eid)
    data = dict(data or {})
    if data.get("reset"):
        e.update(layout=None, groups=None, removed=None)
        return dict(_events_reply(r), ok=True)
    ids = {t.get_id() for t in app_tables.dining_tables.search(restaurant=r)}
    layout = {}
    for tid, pos in (data.get("layout") or {}).items():
        if tid in ids:
            try:
                layout[tid] = [round(max(0.0, min(100.0, float(pos[0]))), 1), round(max(0.0, min(100.0, float(pos[1]))), 1)]
            except (TypeError, ValueError, IndexError):
                continue
    removed = [i for i in dict.fromkeys(data.get("removed") or []) if i in ids]
    used, groups = set(removed), []
    for g in data.get("groups") or []:
        g = dict(g or {})
        tids = [i for i in dict.fromkeys(g.get("tables") or []) if i in ids]
        if len(tids) < 2:
            continue
        if used & set(tids):
            return {"ok": False, "error": "A table can be in only one group, and not in a group if it's taken out."}
        used |= set(tids)
        groups.append({"tables": tids, "seats": _int(g.get("seats"), 1, 500, 2), "label": str(g.get("label") or "").strip()[:30]})
    e.update(layout=layout, groups=groups, removed=removed)
    return dict(_events_reply(r), ok=True)


@anvil.server.callable(require_user=True)
def delete_event(rid, eid):
    r = _rest(rid, "manager")
    _child(app_tables.events, r, eid).delete()
    return dict(_events_reply(r), ok=True)
