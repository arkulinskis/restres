# Portal — Server Module. Everything a signed-in restaurant manager can do.
# Every table is "No access" for client code; these callables check that the signed-in user
# owns the restaurant before reading or writing anything (see _rest).
import re
from datetime import date, datetime, time, timedelta

import anvil.server
import anvil.users
import anvil.tables as tables
from anvil.tables import app_tables

from . import Booking as B

MAX_RESTAURANTS = 50
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------- access
def _user():
    u = anvil.users.get_user()
    if u is None:
        raise anvil.users.AuthenticationFailed("Please sign in.")
    return u


ROLES = {"staff": 1, "manager": 2, "owner": 3}
ROLE_NAMES = {"owner": "Owner", "manager": "Manager", "staff": "Staff"}


def _role(r, u):
    """The user's role at restaurant r: owner, manager, staff, or None. An invite by email is
    claimed the first time that user turns up."""
    if r is None or u is None:
        return None
    if r["owner"] == u:
        return "owner"
    email = (u["email"] or "").strip().lower()
    for m in app_tables.members.search(restaurant=r):
        if m["user"] == u or (m["user"] is None and email and (m["email"] or "") == email):
            if m["user"] is None:
                m["user"] = u
            return m["role"] if m["role"] in ROLES else "staff"
    return None


def _rest(rid, need="staff"):
    """The restaurant with this id, if the signed-in user's role there is at least `need`."""
    u = _user()
    r = app_tables.restaurants.get_by_id(rid) if rid else None
    role = _role(r, u)
    if role is None or ROLES[role] < ROLES[need]:
        raise anvil.server.PermissionDenied("You don't have access to this." if role else "You don't have access to this restaurant.")
    return r


def _mine():
    """Every restaurant the user owns or is a member of (own ones first)."""
    u = _user()
    seen, out = set(), []
    email = (u["email"] or "").strip().lower()
    members = list(app_tables.members.search(user=u)) + (list(app_tables.members.search(email=email)) if email else [])
    for r in list(app_tables.restaurants.search(owner=u)) + [m["restaurant"] for m in members]:
        if r is not None and r.get_id() not in seen and _role(r, u):
            seen.add(r.get_id())
            out.append(r)
    return sorted(out, key=lambda r: (r["owner"] != u, r["position"] or 0, B._created_key(r)))


def _child(table, rid_row, item_id):
    row = table.get_by_id(item_id) if item_id else None
    if row is None or row["restaurant"] != rid_row:
        raise anvil.server.PermissionDenied("That item doesn't belong to this restaurant.")
    return row


def _pending(r):
    today = B.local_now(r).date()
    return [x for x in app_tables.reservations.search(restaurant=r, status="pending") if x["date"] >= today]


def _nav(r):
    return {"restaurant": {"id": r.get_id(), "name": r["name"], "slug": r["slug"], "pending": len(_pending(r)),
                           "role": _role(r, _user())},
            "restaurants": [{"id": x.get_id(), "name": x["name"]} for x in _mine()]}


def _int(v, lo, hi, default=None):
    try:
        v = int(v)
    except (TypeError, ValueError):
        if default is None:
            raise ValueError("Expected a number.")
        return default
    return max(lo, min(hi, v))


def _today_line(ctx, d):
    iv, src = B.day_hours(ctx, d)
    if not iv:
        return "Closed today" + (" · " + src["label"] if src["kind"] == "special" else "")
    return "Open today " + ", ".join("%s–%s" % (a, b) for a, b in B.intervals_text(iv))


# ---------------------------------------------------------------- the manager
@anvil.server.callable(require_user=True)
def get_me():
    u = _user()
    return {"email": u["email"], "display_name": u["display_name"] or (u["email"] or "").split("@")[0].title(),
            "alerts": get_alerts()}


@anvil.server.callable(require_user=True)
def update_me(display_name):
    u = _user()
    u["display_name"] = str(display_name or "").strip()[:80] or None
    return get_me()


@anvil.server.callable(require_user=True)
def get_alerts():
    """Pending requests across all of the manager's restaurants (the bell in the header)."""
    items = []
    for r in _mine():
        for x in _pending(r):
            items.append({"restaurant_id": r.get_id(), "restaurant": r["name"], "id": x.get_id(), "name": x["name"],
                          "date": B.iso(x["date"]), "time": B.hm(x["start_min"]), "party": int(x["party"] or 0),
                          "created": B.iso(x["created"])})
    items.sort(key=lambda i: (i["date"], i["time"]))
    return {"pending": len(items), "items": items[:20]}


# ---------------------------------------------------------------- restaurants
@anvil.server.callable(require_user=True)
def get_dashboard():
    out = []
    for r in _mine():
        ctx = B.Ctx(r)
        today = B.local_now(r).date()
        res = ctx.reservations(today)
        out.append({"id": r.get_id(), "name": r["name"], "slug": r["slug"], "address": r["address"] or "",
                    "today": _today_line(ctx, today), "bookings": len(res), "covers": sum(int(x["party"] or 0) for x in res),
                    "pending": len(_pending(r)), "tables": len(ctx.tables), "seats": ctx.total_seats,
                    "accepting": r["accepting"] is not False, "role": _role(r, _user())})
    return {"restaurants": out, "me": get_me()}


SAMPLE_WEEK = {"0": [], "1": [["12:00", "15:00"], ["18:00", "22:00"]], "2": [["12:00", "15:00"], ["18:00", "22:00"]],
               "3": [["12:00", "15:00"], ["18:00", "22:00"]], "4": [["12:00", "15:00"], ["18:00", "23:00"]],
               "5": [["12:00", "15:00"], ["18:00", "23:00"]], "6": [["12:00", "16:00"]]}
SAMPLE_TABLES = [("T1", 2, "round", 12, 18), ("T2", 2, "round", 27, 18), ("T3", 2, "round", 42, 18),
                 ("T4", 4, "square", 12, 50), ("T5", 4, "square", 27, 50), ("T6", 4, "square", 42, 50),
                 ("T7", 4, "square", 64, 30), ("T8", 4, "square", 79, 30), ("T9", 6, "long", 70, 72)]


def _sample_setup(r):
    now = B.now_utc()
    app_tables.periods.add_row(restaurant=r, name="Regular hours", start=None, end=None, week=SAMPLE_WEEK, created=now)
    ids = {}
    for i, (name, seats, shape, x, y) in enumerate(SAMPLE_TABLES):
        t = app_tables.dining_tables.add_row(restaurant=r, name=name, seats=seats, min_party=1, shape=shape, area="Main room",
                                             x=x, y=y, position=i, active=True)
        ids[name] = t.get_id()
    # T7 and T8 are pushed together into one table of 8 for dinner on Fridays and Saturdays.
    app_tables.table_joins.add_row(restaurant=r, tables=[ids["T7"], ids["T8"]], seats=8, label="",
                                   hours=list(range(18, 24)), days=[4, 5], created=now)


@anvil.server.callable(require_user=True)
def create_restaurant(name, timezone_name="UTC", sample=True):
    u = _user()
    name = str(name or "").strip()[:80]
    if not name:
        return {"ok": False, "error": "Give the restaurant a name."}
    if len(_mine()) >= MAX_RESTAURANTS:
        return {"ok": False, "error": "You've reached the limit of %d restaurants." % MAX_RESTAURANTS}
    tz = timezone_name if B.valid_timezone(timezone_name) else "UTC"
    r = app_tables.restaurants.add_row(owner=u, name=name, slug=B.unique_slug(name), timezone=tz, created=B.now_utc(),
                                       position=len(_mine()), accepting=True, over_capacity="review",
                                       **{k: v[0] for k, v in B.SETTINGS.items()})
    if sample:
        _sample_setup(r)
    return {"ok": True, "id": r.get_id()}


@anvil.server.callable(require_user=True)
def duplicate_restaurant(rid, name=None):
    """Copy a restaurant's settings, hours, special days, tables and joins (not its reservations)."""
    src = _rest(rid, "manager")
    if len(_mine()) >= MAX_RESTAURANTS:
        return {"ok": False, "error": "You've reached the limit of %d restaurants." % MAX_RESTAURANTS}
    name = str(name or "").strip()[:80] or (src["name"] + " (copy)")
    copy_cols = ["description", "address", "phone", "email", "website", "timezone", "form_note", "privacy_text",
                 "accepting", "over_capacity"] + list(B.SETTINGS)
    now = B.now_utc()
    r = app_tables.restaurants.add_row(owner=_user(), name=name, slug=B.unique_slug(name), created=now,
                                       position=len(_mine()), **{c: src[c] for c in copy_cols})
    for p in app_tables.periods.search(restaurant=src):
        app_tables.periods.add_row(restaurant=r, name=p["name"], start=p["start"], end=p["end"], week=p["week"], created=p["created"] or now)
    for s in app_tables.special_days.search(restaurant=src):
        app_tables.special_days.add_row(restaurant=r, date=s["date"], label=s["label"], closed=s["closed"], hours=s["hours"])
    ids = {}
    for t in app_tables.dining_tables.search(restaurant=src):
        n = app_tables.dining_tables.add_row(restaurant=r, **{c: t[c] for c in ("name", "seats", "min_party", "shape", "area", "x", "y", "position", "active")})
        ids[t.get_id()] = n.get_id()
    for j in app_tables.table_joins.search(restaurant=src):
        app_tables.table_joins.add_row(restaurant=r, tables=[ids[i] for i in (j["tables"] or []) if i in ids], seats=j["seats"],
                                       label=j["label"], hours=j["hours"], days=j["days"], created=j["created"] or now)
    for sec in app_tables.menu_sections.search(restaurant=src):
        ns = app_tables.menu_sections.add_row(restaurant=r, title=sec["title"], description=sec["description"], position=sec["position"])
        for it in app_tables.menu_items.search(section=sec):
            app_tables.menu_items.add_row(restaurant=r, section=ns, **{c: it[c] for c in ("name", "description", "price", "tags", "position", "available")})
    return {"ok": True, "id": r.get_id()}


@anvil.server.callable(require_user=True)
def delete_restaurant(rid, confirm_name):
    r = _rest(rid, "owner")
    if str(confirm_name or "").strip() != r["name"]:
        return {"ok": False, "error": "Type the restaurant's name exactly to confirm."}
    for table in (app_tables.reservations, app_tables.periods, app_tables.special_days, app_tables.dining_tables, app_tables.table_joins,
                  app_tables.members, app_tables.menu_items, app_tables.menu_sections, app_tables.specials, app_tables.posts,
                  app_tables.events, app_tables.sites, app_tables.photos):
        for row in list(table.search(restaurant=r)):
            row.delete()
    r.delete()
    return {"ok": True}


@anvil.server.callable(require_user=True)
def reorder_restaurants(ids):
    mine = {r.get_id(): r for r in _mine() if r["owner"] == _user()}
    for i, rid in enumerate(ids or []):
        if rid in mine:
            mine[rid]["position"] = i
    return {"ok": True}


# ---------------------------------------------------------------- settings
TEXT_FIELDS = {"name": 80, "description": 400, "address": 200, "phone": 40, "email": 200, "website": 200,
               "form_note": 600, "privacy_text": 4000, "notify_email": 200, "msg_confirmed": 1000, "msg_pending": 1000,
               "msg_declined": 1000}


def _settings_view(r):
    v = {k: r[k] or "" for k in TEXT_FIELDS}
    v.update({k: B.setting(r, k) for k in B.SETTINGS})
    v.update({"id": r.get_id(), "slug": r["slug"], "timezone": r["timezone"] or "UTC", "accepting": r["accepting"] is not False,
              "over_capacity": r["over_capacity"] or "review", "default_privacy": B.DEFAULT_PRIVACY,
              "emails_on": r["emails_on"] is not False, "language": B.language(r), "languages": B.languages(r),
              "owner_email": r["owner"]["email"] if r["owner"] else ""})
    return v


@anvil.server.callable(require_user=True)
def get_settings(rid):
    r = _rest(rid, "manager")
    return {"nav": _nav(r), "settings": _settings_view(r), "origin": anvil.server.get_app_origin(), "team": _team(r),
            "role": _role(r, _user())}


@anvil.server.callable(require_user=True)
def save_settings(rid, data):
    r = _rest(rid, "manager")
    data = dict(data or {})
    upd = {}
    for k, n in TEXT_FIELDS.items():
        if k in data:
            upd[k] = str(data[k] or "").strip()[:n]
    if "name" in upd and not upd["name"]:
        return {"ok": False, "error": "The restaurant needs a name."}
    for k, (default, lo, hi) in B.SETTINGS.items():
        if k in data:
            upd[k] = _int(data[k], lo, hi, default)
    if "slug" in data:
        slug = B.slugify(data["slug"])
        other = app_tables.restaurants.get(slug=slug)
        if other is not None and other != r:
            return {"ok": False, "error": "The booking link “%s” is taken. Try another." % slug}
        upd["slug"] = slug
    if "timezone" in data:
        if not B.valid_timezone(data["timezone"]):
            return {"ok": False, "error": "Unknown time zone: %s" % data["timezone"]}
        upd["timezone"] = data["timezone"]
    if "accepting" in data:
        upd["accepting"] = bool(data["accepting"])
    if "emails_on" in data:
        upd["emails_on"] = bool(data["emails_on"])
    if "language" in data:
        upd["language"] = data["language"] if data["language"] in B.LANGS else "en"
    if "languages" in data:
        upd["languages"] = [x for x in B.LANGS if x in (data["languages"] or [])]
    if upd.get("notify_email") and not EMAIL_RE.match(upd["notify_email"]):
        return {"ok": False, "error": "The alert email address doesn't look right."}
    if "over_capacity" in data:
        upd["over_capacity"] = data["over_capacity"] if data["over_capacity"] in B.OVER_CAPACITY else "review"
    r.update(**upd)
    return {"ok": True, "settings": _settings_view(r), "nav": _nav(r)}


# ---------------------------------------------------------------- opening hours
def _period_view(p):
    return {"id": p.get_id(), "name": p["name"] or "", "start": B.iso(p["start"]), "end": B.iso(p["end"]),
            "week": {str(i): B.intervals_text(B.clean_intervals((p["week"] or {}).get(str(i), []))) for i in range(7)}}


def _special_view(s):
    return {"id": s.get_id(), "date": B.iso(s["date"]), "label": s["label"] or "", "closed": bool(s["closed"]),
            "hours": B.intervals_text(B.clean_intervals(s["hours"]))}


def _calendar(ctx, first):
    """Every day of the month that starts at `first`, with its hours and where they come from."""
    out, d = [], first
    while d.month == first.month:
        iv, src = B.day_hours(ctx, d)
        out.append({"date": d.isoformat(), "hours": B.intervals_text(iv), "kind": src["kind"], "label": src["label"],
                    "period_id": src.get("id")})
        d += timedelta(days=1)
    return out


@anvil.server.callable(require_user=True)
def get_hours(rid, month=None):
    r = _rest(rid, "manager")
    ctx = B.Ctx(r)
    today = B.local_now(r).date()
    try:
        first = B.parse_date((month or "")[:7] + "-01")
    except ValueError:
        first = today.replace(day=1)
    periods = sorted(ctx.periods, key=lambda p: (p["start"] is not None or p["end"] is not None, p["start"] or date.min, B._created_key(p)))
    specials = sorted(ctx.specials.values(), key=lambda s: s["date"])
    return {"nav": _nav(r), "today": today.isoformat(), "month": first.isoformat()[:7],
            "periods": [_period_view(p) for p in periods],
            "specials": [_special_view(s) for s in specials if s["date"] >= today - timedelta(days=30)],
            "past_specials": len([s for s in specials if s["date"] < today - timedelta(days=30)]),
            "calendar": _calendar(ctx, first)}


def _clean_week(week):
    out = {}
    for i in range(7):
        iv = B.clean_intervals((week or {}).get(str(i)) or [])
        out[str(i)] = B.intervals_text(iv)
    return out


@anvil.server.callable(require_user=True)
def save_period(rid, data, month=None):
    r = _rest(rid, "manager")
    data = dict(data or {})
    name = str(data.get("name") or "").strip()[:60] or "Opening hours"
    try:
        start = B.parse_date(data["start"]) if data.get("start") else None
        end = B.parse_date(data["end"]) if data.get("end") else None
    except ValueError:
        return {"ok": False, "error": "Check the dates."}
    if start and end and end < start:
        return {"ok": False, "error": "The end date is before the start date."}
    fields = {"name": name, "start": start, "end": end, "week": _clean_week(data.get("week"))}
    if data.get("id"):
        _child(app_tables.periods, r, data["id"]).update(**fields)
    else:
        app_tables.periods.add_row(restaurant=r, created=B.now_utc(), **fields)
    return dict(get_hours(rid, month), ok=True)


@anvil.server.callable(require_user=True)
def delete_period(rid, pid, month=None):
    r = _rest(rid, "manager")
    _child(app_tables.periods, r, pid).delete()
    return dict(get_hours(rid, month), ok=True)


@anvil.server.callable(require_user=True)
def save_special(rid, data, month=None):
    """One special day, or the same hours for every date from `date` to `to` (at most 62 days)."""
    r = _rest(rid, "manager")
    data = dict(data or {})
    try:
        d = B.parse_date(data.get("date"))
        to = B.parse_date(data["to"]) if data.get("to") else d
    except ValueError:
        return {"ok": False, "error": "Pick a date."}
    if to < d or (to - d).days > 61:
        return {"ok": False, "error": "A range of special days can be up to 62 days long."}
    closed = bool(data.get("closed"))
    hours = B.intervals_text(B.clean_intervals(data.get("hours")))
    if not closed and not hours:
        return {"ok": False, "error": "Add opening hours, or mark the day as closed."}
    fields = {"label": str(data.get("label") or "").strip()[:60], "closed": closed, "hours": [] if closed else hours}
    if data.get("id") and to == d:
        row = _child(app_tables.special_days, r, data["id"])
        clash = app_tables.special_days.get(restaurant=r, date=d)
        if clash is not None and clash != row:
            clash.delete()
        row.update(date=d, **fields)
    else:
        day = d
        while day <= to:
            row = app_tables.special_days.get(restaurant=r, date=day)
            if row is None:
                app_tables.special_days.add_row(restaurant=r, date=day, **fields)
            else:
                row.update(**fields)
            day += timedelta(days=1)
    return dict(get_hours(rid, month), ok=True)


@anvil.server.callable(require_user=True)
def delete_special(rid, sid, month=None):
    r = _rest(rid, "manager")
    _child(app_tables.special_days, r, sid).delete()
    return dict(get_hours(rid, month), ok=True)


# ---------------------------------------------------------------- tables and layout
def _open_hours(ctx):
    """The hours of the day the restaurant is ever open (for the layout hour strip)."""
    hours = set()
    weeks = [p["week"] or {} for p in ctx.periods] + [{"x": s["hours"]} for s in ctx.specials.values() if not s["closed"]]
    for w in weeks:
        for iv in w.values():
            for o, c in B.clean_intervals(iv):
                hours |= set(range(o // 60, (c + 59) // 60))
    return sorted(h for h in hours if 0 <= h <= 23) or list(range(11, 23))


def _tables_reply(r):
    ctx = B.Ctx(r)
    return {"ok": True, "nav": _nav(r), "tables": [B.table_view(t) for t in ctx.all_tables],
            "joins": [B.join_view(j) for j in ctx.joins], "open_hours": _open_hours(ctx),
            "seats": ctx.total_seats, "today_weekday": B.local_now(r).date().weekday(),
            "now_hour": B.local_now(r).hour}


@anvil.server.callable(require_user=True)
def get_tables(rid):
    return _tables_reply(_rest(rid, "manager"))


def _free_spot(existing):
    """Where a new table goes on the floor plan (x, y in %, the table's centre): the first spot on a roomy grid
    that no table is near, so new tables don't land on top of each other (or on one the manager moved there)."""
    taken = [(float(t["x"] or 0), float(t["y"] or 0)) for t in existing]
    for y in (14, 38, 62, 86):
        for x in (12, 30, 48, 66, 84):
            if all(abs(x - tx) >= 14 or abs(y - ty) >= 18 for tx, ty in taken):
                return float(x), float(y)
    n = len(existing)  # the room is full: stagger near the middle so the new table is easy to spot and drag
    return float(40 + (n * 3) % 20), float(40 + (n * 5) % 20)


@anvil.server.callable(require_user=True)
def save_table(rid, data):
    r = _rest(rid, "manager")
    data = dict(data or {})
    existing = list(app_tables.dining_tables.search(restaurant=r))
    fields = {}
    if "name" in data or not data.get("id"):
        name = str(data.get("name") or "").strip()[:20]
        if not name:  # the first free T<n> (counting tables would repeat a name after a delete)
            names = set(t["name"].lower() for t in existing)
            name = next("T%d" % n for n in range(1, len(existing) + 2) if ("t%d" % n) not in names)
        if any(t["name"].lower() == name.lower() and t.get_id() != data.get("id") for t in existing):
            return {"ok": False, "error": "There is already a table called %s." % name}
        fields["name"] = name
    if "seats" in data or not data.get("id"):
        fields["seats"] = _int(data.get("seats"), 1, 60, 4)
    if "min_party" in data:
        fields["min_party"] = _int(data.get("min_party"), 1, 60, 1)
    if "shape" in data:
        fields["shape"] = data["shape"] if data["shape"] in B.SHAPES else "square"
    if "area" in data:
        fields["area"] = str(data.get("area") or "").strip()[:40]
    if "active" in data:
        fields["active"] = bool(data["active"])
    for k in ("x", "y"):
        if k in data:
            fields[k] = float(max(0, min(100, float(data[k] or 0))))
    if fields.get("min_party") and fields.get("seats") and fields["min_party"] > fields["seats"]:
        fields["min_party"] = fields["seats"]
    if data.get("id"):
        _child(app_tables.dining_tables, r, data["id"]).update(**fields)
    else:
        fields.setdefault("shape", "square")
        fields.setdefault("min_party", 1)
        if "x" not in fields or "y" not in fields:
            fields["x"], fields["y"] = _free_spot(existing)
        last = max([int(t["position"] or 0) for t in existing] or [-1])  # after a delete, len() would repeat a position
        row = app_tables.dining_tables.add_row(restaurant=r, position=last + 1, active=True, area=fields.pop("area", ""), **fields)
        return dict(_tables_reply(r), new_id=row.get_id())
    return _tables_reply(r)


@anvil.server.callable(require_user=True)
def delete_table(rid, tid):
    r = _rest(rid, "manager")
    t = _child(app_tables.dining_tables, r, tid)
    for j in list(app_tables.table_joins.search(restaurant=r)):
        if tid in (j["tables"] or []):
            rest = [i for i in j["tables"] if i != tid]
            if len(rest) < 2:
                j.delete()
            else:
                j["tables"] = rest
    t.delete()
    return _tables_reply(r)


@anvil.server.callable(require_user=True)
def save_positions(rid, positions):
    r = _rest(rid, "manager")
    mine = {t.get_id(): t for t in app_tables.dining_tables.search(restaurant=r)}
    for p in positions or []:
        t = mine.get(p.get("id"))
        if t is not None:
            t.update(x=float(max(0, min(100, float(p.get("x") or 0)))), y=float(max(0, min(100, float(p.get("y") or 0)))))
    return {"ok": True}


@anvil.server.callable(require_user=True)
def save_join(rid, data):
    """Join two or more tables into one bookable table for some hours of the day, on some weekdays."""
    return _save_join(_rest(rid, "manager"), dict(data or {}))


@tables.in_transaction
def _save_join(r, data):
    # in a transaction, so two quick saves can't both pass the overlap check below
    ctx = B.Ctx(r)
    ids = [i for i in dict.fromkeys(data.get("tables") or []) if i in {t.get_id() for t in ctx.all_tables}]
    if len(ids) < 2:
        return {"ok": False, "error": "Pick at least two tables to join."}
    hours = sorted({_int(h, 0, 23) for h in (data.get("hours") or [])})
    days = sorted({_int(d, 0, 6) for d in (data.get("days") or [])})
    if len(days) == 7:
        days = []
    if not hours:
        if data.get("id"):  # no hours left: the join is gone (the tables are split all day)
            _child(app_tables.table_joins, r, data["id"]).delete()
            return _tables_reply(r)
        return {"ok": False, "error": "Pick the hours when these tables are joined."}
    names = {t.get_id(): t["name"] for t in ctx.all_tables}
    for j in ctx.joins:
        if j.get_id() == data.get("id"):
            continue
        shared = set(ids) & set(j["tables"] or [])
        both_hours = set(hours) & set(j["hours"] or [])
        jd = set(j["days"] or range(7))
        both_days = (set(days) or set(range(7))) & jd
        if shared and both_hours and both_days:
            h, d = min(both_hours), min(both_days)
            return {"ok": False, "error": "%s is already joined with other tables at %02d:00 on %s. Change that join first." % (
                names[sorted(shared)[0]], h, B.DAY_NAMES[d])}
    default_seats = sum(int(ctx.by_id[i]["seats"] or 0) if i in ctx.by_id else 0 for i in ids)
    fields = {"tables": ids, "hours": hours, "days": days, "seats": _int(data.get("seats"), 1, 200, default_seats or 2),
              "label": str(data.get("label") or "").strip()[:30]}
    if data.get("id"):
        _child(app_tables.table_joins, r, data["id"]).update(**fields)
    else:
        app_tables.table_joins.add_row(restaurant=r, created=B.now_utc(), **fields)
    return _tables_reply(r)


@anvil.server.callable(require_user=True)
def delete_join(rid, jid):
    r = _rest(rid, "manager")
    _child(app_tables.table_joins, r, jid).delete()
    return _tables_reply(r)


# ---------------------------------------------------------------- reservations
def _analysis(ctx, x):
    """What a manager needs to decide on a pending request."""
    d, t, dur, party = x["date"], int(x["start_min"]), int(x["duration"] or 0), int(x["party"] or 0)
    pct_without = B.occupancy(ctx, d, t, dur, exclude=x)
    alts = B.free_units(ctx, d, t, party, dur, exclude=x)
    return {"pct_without": pct_without, "pct_with": B.occupancy(ctx, d, t, dur), "free_units": len(alts),
            "threshold": B.setting(ctx.r, "auto_threshold"), "max_auto_party": B.setting(ctx.r, "max_auto_party")}


@anvil.server.callable(require_user=True)
def get_day(rid, day=None):
    r = _rest(rid)
    ctx = B.Ctx(r)
    now = B.local_now(r)
    try:
        d = B.parse_date(day) if day else now.date()
    except ValueError:
        d = now.date()
    iv, src = B.day_hours(ctx, d)
    rows = sorted(app_tables.reservations.search(restaurant=r, date=d), key=lambda x: (int(x["start_min"] or 0), B._created_key(x)))
    live = [x for x in rows if x["status"] in B.ACTIVE]
    step = B.setting(r, "slot_min")
    curve, peak = [], {"pct": 0, "time": None}
    lo = min([o for o, c in iv] + [int(x["start_min"]) for x in live]) if (iv or live) else None
    hi = max([c for o, c in iv] + [int(x["start_min"]) + int(x["duration"] or 0) for x in live]) if (iv or live) else None
    if lo is not None:
        t = lo
        while t < hi:
            ids = B.busy_ids(ctx, d, t, 1)
            seats = sum(int(ctx.by_id[i]["seats"] or 0) for i in ids if i in ctx.by_id)
            pct = int(round(100.0 * seats / ctx.total_seats)) if ctx.total_seats else 0
            curve.append({"time": B.hm(t), "pct": pct, "guests": sum(int(x["party"] or 0) for x in live
                                                                     if int(x["start_min"]) <= t < int(x["start_min"]) + int(x["duration"] or 0))})
            if pct > peak["pct"]:
                peak = {"pct": pct, "time": B.hm(t)}
            t += step
    pending = []
    for x in sorted(_pending(r), key=lambda x: (x["date"], int(x["start_min"] or 0))):
        v = B.reservation_view(x, ctx, staff=True)
        v["analysis"] = _analysis(ctx, x)  # ctx loads each date's reservations on first use
        pending.append(v)
    return {
        "nav": _nav(r), "date": d.isoformat(), "today": now.date().isoformat(),
        "now_min": now.hour * 60 + now.minute if d == now.date() else None,
        "weekday": B.DAY_NAMES[d.weekday()], "hours": B.intervals_text(iv), "hours_label": src["label"], "hours_kind": src["kind"],
        "tables": [B.table_view(t) for t in ctx.tables], "seats": ctx.total_seats,
        "reservations": [B.reservation_view(x, ctx, staff=True) for x in rows],
        "summary": {"bookings": len(live), "covers": sum(int(x["party"] or 0) for x in live), "peak": peak,
                    "pending_today": len([x for x in live if x["status"] == "pending"])},
        "curve": curve, "pending": pending,
        "events": [{"id": e.get_id(), "title": e["title"] or "", "start": B.hm(int(e["start_min"] or 0)), "end": B.hm(int(e["end_min"] or 0)),
                    "kind": e["kind"] or "public", "blocks": bool(e["blocks"]), "guests": int(e["guests"] or 0),
                    "setup": e["layout"] is not None} for e in B.events_on(ctx, d)],
        "settings": {"duration_min": B.setting(r, "duration_min"), "slot_min": step, "auto_threshold": B.setting(r, "auto_threshold")},
    }


@anvil.server.callable(require_user=True)
def get_options(rid, day, time_text, party, duration, res_id=None):
    """Free tables for a time, for the booking editor's table picker."""
    r = _rest(rid)
    ctx = B.Ctx(r)
    try:
        d, t = B.parse_date(day), B.parse_hm(time_text)
    except ValueError:
        return {"ok": False, "error": "Pick a date and time."}
    party = _int(party, 1, 200, 2)
    dur = _int(duration, 15, 720, B.setting(r, "duration_min"))
    exclude = _child(app_tables.reservations, r, res_id) if res_id else None
    units = B.free_units(ctx, d, t, party, dur, exclude)
    return {"ok": True, "open": B.is_open_at(ctx, d, t), "pct": B.occupancy(ctx, d, t, dur, exclude),
            "units": [{"ids": u["ids"], "label": u["label"], "seats": u["seats"]} for u in units],
            "best": units[0]["ids"] if units else None}


@tables.in_transaction
def _save_reservation(r, data):
    ctx = B.Ctx(r)
    res = _child(app_tables.reservations, r, data["id"]) if data.get("id") else None
    try:
        d, t = B.parse_date(data.get("date")), B.parse_hm(data.get("time"))
    except ValueError:
        return {"ok": False, "error": "Pick a date and a time."}
    party = _int(data.get("party"), 1, 200, 2)
    dur = _int(data.get("duration"), 15, 720, B.setting(r, "duration_min"))
    name = str(data.get("name") or "").strip()[:100]
    if not name:
        return {"ok": False, "error": "Enter the guest's name."}
    force = bool(data.get("force"))
    warnings = []
    if not B.is_open_at(ctx, d, t):
        warnings.append("The restaurant is closed at %s on %s." % (B.hm(t), d.isoformat()))
    chosen = data.get("tables")
    if chosen in (None, "auto", []):
        unit = B.find_unit(ctx, d, t, party, dur, exclude=res)
        if unit is None:
            if not force:
                return {"ok": False, "conflict": True, "error": "No free table fits %d guests at %s." % (party, B.hm(t))}
            ids = []
        else:
            ids = unit["ids"]
    else:
        valid = {x.get_id() for x in ctx.tables}
        ids = [i for i in chosen if i in valid]
        clash = set(ids) & B.busy_ids(ctx, d, t, dur, exclude=res)
        if clash:
            warnings.append("%s is already booked at that time." % ", ".join(ctx.by_id[i]["name"] for i in clash))
        seats = sum(int(ctx.by_id[i]["seats"] or 0) for i in ids)
        if seats and seats < party:
            warnings.append("The table seats %d, fewer than the %d guests." % (seats, party))
    if warnings and not force:
        return {"ok": False, "conflict": True, "error": " ".join(warnings) + " Save anyway?"}
    status = data.get("status") if data.get("status") in B.STATUSES else ("confirmed" if res is None else res["status"])
    source = data.get("source") if data.get("source") in B.SOURCES else ("phone" if res is None else res["source"])
    fields = {"date": d, "start_min": t, "duration": dur, "party": party, "name": name, "tables": ids,
              "email": str(data.get("email") or "").strip()[:200], "phone": str(data.get("phone") or "").strip()[:40],
              "notes": str(data.get("notes") or "").strip()[:1000], "staff_note": str(data.get("staff_note") or "").strip()[:1000],
              "status": status, "source": source, "updated": B.now_utc()}
    if status != "pending":
        fields["review_reason"] = ""
    if res is None:
        res = app_tables.reservations.add_row(restaurant=r, token=B.new_token(), created=B.now_utc(), history=[],
                                              consent=False, capacity_pct=B.occupancy(ctx, d, t, dur), **fields)
        B.add_history(res, "staff", "Added by staff (%s)." % source.replace("_", "-"))
    else:
        before = res["status"]
        res.update(**fields)
        B.add_history(res, "staff", "Edited by staff." + (" Status: %s → %s." % (before, status) if before != status else ""))
    return {"ok": True, "id": res.get_id(), "warnings": warnings}


@anvil.server.callable(require_user=True)
def save_reservation(rid, data):
    r = _rest(rid)
    out = _save_reservation(r, dict(data or {}))
    if out.get("ok"):
        if data.get("notify"):  # "Email the guest" ticked in the booking editor
            try:
                from . import Notify
                out["emailed"] = Notify.reservation_event(app_tables.reservations.get_by_id(out["id"]),
                                                          "changed" if data.get("id") else "created")
            except Exception as e:
                print("notify failed:", e)
        out["day"] = get_day(rid, data.get("date"))
    return out


@anvil.server.callable(require_user=True)
def set_status(rid, res_id, status, day=None):
    """Approve (confirmed), decline, cancel or reopen a reservation."""
    r = _rest(rid)
    if status not in B.STATUSES:
        return {"ok": False, "error": "Unknown status."}
    res = _child(app_tables.reservations, r, res_id)
    before = res["status"]
    if status in B.ACTIVE and before not in B.ACTIVE:
        ctx = B.Ctx(r)
        clash = set(res["tables"] or []) & B.busy_ids(ctx, res["date"], int(res["start_min"]), int(res["duration"] or 0), exclude=res)
        if clash:
            unit = B.find_unit(ctx, res["date"], int(res["start_min"]), int(res["party"]), int(res["duration"] or 0), exclude=res)
            if unit is None:
                return {"ok": False, "error": "Its table has been given to someone else, and no other table fits. Edit the booking to pick a time or table."}
            res["tables"] = unit["ids"]
    res.update(status=status, updated=B.now_utc(), review_reason="" if status != "pending" else res["review_reason"])
    words = {"confirmed": "Approved" if before == "pending" else "Confirmed", "declined": "Declined", "cancelled": "Cancelled", "pending": "Marked as pending"}
    B.add_history(res, "staff", "%s by staff." % words[status])
    try:
        from . import Notify
        Notify.reservation_event(res, status, before=before)
    except Exception as e:
        print("notify failed:", e)
    return {"ok": True, "day": get_day(rid, day or B.iso(res["date"])), "alerts": get_alerts()}


# ---------------------------------------------------------------- team (owners, managers, staff)
def _team(r):
    owner = r["owner"]
    rows = [{"id": None, "email": owner["email"] if owner else "", "name": (owner["display_name"] or "") if owner else "",
             "role": "owner", "joined": True}]
    for m in sorted(app_tables.members.search(restaurant=r), key=B._created_key):
        rows.append({"id": m.get_id(), "email": m["email"] or "", "name": (m["user"]["display_name"] or "") if m["user"] else "",
                     "role": m["role"], "joined": m["user"] is not None})
    return rows


@anvil.server.callable(require_user=True)
def get_team(rid):
    return {"ok": True, "team": _team(_rest(rid, "manager"))}


@anvil.server.callable(require_user=True)
def invite_member(rid, email, role="staff"):
    """Give someone access by email. They see the restaurant when they sign in with that address."""
    r = _rest(rid, "owner")
    email = str(email or "").strip().lower()
    if not EMAIL_RE.match(email):
        return {"ok": False, "error": "Enter a valid email address."}
    if role not in ("manager", "staff"):
        return {"ok": False, "error": "Pick a role."}
    if r["owner"] and (r["owner"]["email"] or "").lower() == email:
        return {"ok": False, "error": "That's the owner's address."}
    team = list(app_tables.members.search(restaurant=r))
    if any((m["email"] or "") == email for m in team):
        return {"ok": False, "error": "%s already has access." % email}
    if len(team) >= 100:
        return {"ok": False, "error": "A restaurant can have up to 100 team members."}
    user = app_tables.users.get(email=email)
    app_tables.members.add_row(restaurant=r, email=email, user=user, role=role, invited_by=_user(), created=B.now_utc())
    try:
        from . import Notify
        Notify.invite(r, email, role, _user())
    except Exception as e:
        print("invite email failed:", e)
    return {"ok": True, "team": _team(r)}


@anvil.server.callable(require_user=True)
def set_member_role(rid, mid, role):
    r = _rest(rid, "owner")
    if role not in ("manager", "staff"):
        return {"ok": False, "error": "Pick a role."}
    _child(app_tables.members, r, mid)["role"] = role
    return {"ok": True, "team": _team(r)}


@anvil.server.callable(require_user=True)
def remove_member(rid, mid):
    r = _rest(rid, "owner")
    _child(app_tables.members, r, mid).delete()
    return {"ok": True, "team": _team(r)}
