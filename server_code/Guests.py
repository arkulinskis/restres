# Guests — Server Module. A restaurant's guest book: everyone who has booked, matched across visits by email (or phone,
# or name when neither is given), with visits, no-shows, cancellations, the last and next visit, and the team's own
# notes and tags (the guests table). Built from reservations on the fly, so it is right from day one.
# Staff can read it (they greet regulars by name); managers and owners can also edit notes and tags.
import re

import anvil.server
from anvil.tables import app_tables

from . import Booking as B
from . import Portal as P

TAGS = ("Regular", "VIP", "Allergy", "Birthday", "Press", "Family", "Business", "Difficult")


def key_of(email, phone, name):
    """The same person across bookings: their email, else their phone digits, else their name."""
    e = str(email or "").strip().lower()
    if e:
        return "e:" + e
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) >= 6:
        return "p:" + digits[-9:]
    n = re.sub(r"\s+", " ", str(name or "").strip().lower())
    return "n:" + n if n else ""


def _row_key(x):
    return key_of(x["email"], x["phone"], x["name"])


def index(r, today=None):
    """{key: stats} for every guest of restaurant r."""
    today = today or B.local_now(r).date()
    out: dict = {}
    for x in app_tables.reservations.search(restaurant=r):
        k = _row_key(x)
        if not k:
            continue
        g: dict = out.get(k) or {}
        if not g:
            g = out[k] = {"key": k, "name": x["name"] or "", "email": x["email"] or "", "phone": x["phone"] or "", "visits": 0,
                          "no_shows": 0, "cancelled": 0, "bookings": 0, "covers": 0, "last": None, "next": None, "first": None}
        st, d = x["status"], x["date"]
        g["bookings"] += 1
        if x["name"]:
            g["name"] = x["name"]  # the newest spelling wins (rows aren't ordered, close enough)
        g["email"] = g["email"] or (x["email"] or "")
        g["phone"] = g["phone"] or (x["phone"] or "")
        came = st in B.VISITED or (st == "confirmed" and d is not None and d < today)
        if came:
            g["visits"] += 1
            g["covers"] += int(x["party"] or 0)
            if g["last"] is None or d > g["last"]:
                g["last"] = d
            if g["first"] is None or d < g["first"]:
                g["first"] = d
        elif st == "no_show":
            g["no_shows"] += 1
        elif st in ("cancelled", "declined"):
            g["cancelled"] += 1
        if st in ("pending", "confirmed") and d is not None and d >= today and (g["next"] is None or d < g["next"]):
            g["next"] = d
    for row in app_tables.guests.search(restaurant=r):
        found = out.get(row["key"])
        if found is not None:
            g = found
            g.update(note=row["note"] or "", tags=list(row["tags"] or []), vip=bool(row["vip"]))
    for g in out.values():
        g.setdefault("note", "")
        g.setdefault("tags", [])
        g.setdefault("vip", False)
        g["regular"] = g["visits"] >= 3
        for f in ("last", "next", "first"):
            g[f] = B.iso(g[f]) if g[f] else None
    return out


def badge(g):
    """The small view the day timeline and the booking editor show next to a name."""
    if not g:
        return None
    return {"key": g["key"], "visits": g["visits"], "no_shows": g["no_shows"], "vip": g["vip"], "regular": g["regular"],
            "tags": g["tags"], "note": g["note"]}


@anvil.server.callable(require_user=True)
def get_guests(rid, query=None, sort="recent"):
    r = P._rest(rid)
    q = str(query or "").strip().lower()
    rows = list(index(r).values())
    if q:
        rows = [g for g in rows if q in (g["name"] + " " + g["email"] + " " + g["phone"] + " " + " ".join(g["tags"]) + " " + g["note"]).lower()]
    if sort == "visits":
        rows.sort(key=lambda g: (-g["visits"], g["name"].lower()))
    elif sort == "name":
        rows.sort(key=lambda g: g["name"].lower())
    else:
        rows.sort(key=lambda g: (g["next"] or g["last"] or ""), reverse=True)
    total = len(rows)
    return {"nav": P._nav(r), "guests": rows[:300], "total": total, "tags": list(TAGS),
            "can_edit": P._role(r, P._user()) != "staff",
            "stats": {"regulars": len([g for g in rows if g["regular"]]), "no_show_guests": len([g for g in rows if g["no_shows"]])}}


@anvil.server.callable(require_user=True)
def get_guest(rid, key):
    r = P._rest(rid)
    g = index(r).get(str(key or ""))
    if g is None:
        return {"ok": False, "error": "That guest isn't in the guest book."}
    ctx = B.Ctx(r)
    visits = [x for x in app_tables.reservations.search(restaurant=r) if _row_key(x) == g["key"]]
    visits.sort(key=lambda x: (x["date"], int(x["start_min"] or 0)), reverse=True)
    return {"ok": True, "guest": g, "tags": list(TAGS), "can_edit": P._role(r, P._user()) != "staff",
            "history": [B.reservation_view(x, ctx, staff=True) for x in visits[:60]]}


@anvil.server.callable(require_user=True)
def save_guest(rid, key, data):
    r = P._rest(rid, "manager")
    key = str(key or "")
    if not key or key not in index(r):
        return {"ok": False, "error": "That guest isn't in the guest book."}
    data = dict(data or {})
    note = str(data.get("note") or "").strip()[:2000]
    tags = [t for t in (data.get("tags") or []) if t in TAGS]
    vip = bool(data.get("vip")) or "VIP" in tags
    row = app_tables.guests.get(restaurant=r, key=key)
    if row is None:
        app_tables.guests.add_row(restaurant=r, key=key, note=note, tags=tags, vip=vip, updated=B.now_utc())
    else:
        row.update(note=note, tags=tags, vip=vip, updated=B.now_utc())
    return get_guest(rid, key)
