# Booking — Server Module. The rules engine shared by Portal (managers) and Public (guests):
#   opening hours  → which times a restaurant is open on a date
#   table layout   → which tables are joined into one bookable unit at a given hour
#   availability   → which unit a party gets, and how full the restaurant is
#   decision       → confirmed straight away, or pending until a manager approves
#
# Times are local to the restaurant: a reservation stores its date plus start_min (minutes after midnight)
# and duration (minutes). Nothing here deals in UTC except "now", which is converted with the restaurant's timezone.
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone

import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

ACTIVE = ("pending", "confirmed")          # statuses that hold a table
STATUSES = ("pending", "confirmed", "declined", "cancelled")
SOURCES = ("online", "phone", "walk_in", "staff")
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SHAPES = ("square", "round", "long")

# Restaurant settings with their defaults and allowed ranges.
SETTINGS = {
    "duration_min": (120, 15, 600),      # how long a reservation blocks its table
    "slot_min": (15, 5, 120),            # spacing of the times offered on the form
    "last_booking_min": (60, 0, 600),    # last start time is this long before closing
    "lead_min": (60, 0, 10080),          # minimum notice for online bookings
    "window_days": (60, 1, 730),         # how far ahead guests can book
    "max_party": (8, 1, 100),            # largest party the online form offers
    "auto_threshold": (80, 0, 100),      # auto-confirm while the restaurant is less full than this (%)
    "max_auto_party": (8, 1, 100),       # bigger parties always need approval
}
OVER_CAPACITY = ("review", "walk_in")    # past the threshold: ask the manager, or stop online booking
LANGS = ("en", "fr", "lv")              # languages of the guest pages and emails

DEFAULT_PRIVACY = (
    "We use your name, email address and phone number only to manage this reservation: to confirm it, "
    "to contact you about it, and to hold your table. We do not sell your details or use them for marketing. "
    "We keep them for up to 12 months after your visit and then delete them. You can ask us to see, change "
    "or delete your details at any time."
)
DEFAULT_PRIVACY_BY_LANG = {
    "en": DEFAULT_PRIVACY,
    "fr": ("Nous utilisons votre nom, votre adresse e-mail et votre numéro de téléphone uniquement pour gérer cette réservation : "
           "la confirmer, vous contacter à son sujet et vous garder votre table. Nous ne vendons pas vos données et ne les utilisons pas "
           "à des fins commerciales. Nous les conservons au maximum 12 mois après votre visite, puis nous les supprimons. Vous pouvez à "
           "tout moment nous demander de consulter, modifier ou supprimer vos données."),
    "lv": ("Jūsu vārdu, e-pasta adresi un tālruņa numuru mēs izmantojam tikai šīs rezervācijas pārvaldībai: lai to apstiprinātu, "
           "sazinātos ar jums par to un paturētu jums galdiņu. Mēs nepārdodam jūsu datus un neizmantojam tos mārketingam. Mēs tos "
           "glabājam ne ilgāk kā 12 mēnešus pēc jūsu apmeklējuma un pēc tam dzēšam. Jūs jebkurā laikā varat lūgt mums parādīt, "
           "labot vai dzēst jūsu datus."),
}


# ---------------------------------------------------------------- small helpers
def iso(value):
    return value.isoformat() if value else None


def now_utc():
    return datetime.now(timezone.utc)


def hm(minutes):
    """640 → "10:40". 1440 → "24:00"."""
    minutes = int(minutes)
    return "%02d:%02d" % (minutes // 60, minutes % 60)


def parse_hm(text, closing=False):
    """ "18:30" → 1110. As a closing time, "00:00" means midnight at the end of the day (1440)."""
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(text or ""))
    if not m:
        raise ValueError("Not a time: %r" % (text,))
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59 or (h == 24 and mi):
        raise ValueError("Not a time: %r" % (text,))
    value = h * 60 + mi
    return 1440 if closing and value == 0 else value


def parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise ValueError("Not a date: %r" % (value,))


def clean_intervals(raw):
    """[["12:00","15:00"], ["18:00","22:00"]] → sorted, validated, non-overlapping minute pairs."""
    out = []
    for pair in raw or []:
        try:
            o, c = parse_hm(pair[0]), parse_hm(pair[1], closing=True)
        except (ValueError, IndexError, TypeError):
            continue
        if c > o:
            out.append([o, c])
    out.sort()
    merged = []
    for o, c in out:
        if merged and o <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], c)
        else:
            merged.append([o, c])
    return merged


def intervals_text(intervals):
    """[[720, 900], [1080, 1320]] → [["12:00","15:00"], ["18:00","22:00"]] (JSON-friendly, for storage and the UI)."""
    return [[hm(o), hm(c)] for o, c in intervals]


def setting(r, name):
    v = r[name]
    return SETTINGS[name][0] if v is None else int(v)


def local_now(r):
    """The restaurant's wall-clock time, as a naive datetime."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(r["timezone"] or "UTC")).replace(tzinfo=None)
    except Exception:
        return now_utc().replace(tzinfo=None)


def valid_timezone(name):
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(name)
        return True
    except Exception:
        return bool(re.match(r"^[A-Za-z_]+(/[A-Za-z0-9_+\-]+)*$", name or ""))


def new_token():
    return uuid.uuid4().hex


def slugify(text):
    """ "Maison Lumière" → "maison-lumiere" (accents folded, so Latvian and French names read well)."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40].strip("-") or "restaurant"


def unique_slug(base, exclude=None):
    base = slugify(base)
    slug, n = base, 2
    while True:
        hit = app_tables.restaurants.get(slug=slug)
        if hit is None or hit == exclude:
            return slug
        slug = "%s-%d" % (base, n)
        n += 1


def add_history(res, by, what):
    h = list(res["history"] or [])
    h.append({"at": iso(now_utc()), "by": by, "what": what})
    res["history"] = h[-50:]


def _created_key(row):
    c = row["created"]
    return c.timestamp() if c else 0


# ---------------------------------------------------------------- the per-restaurant context
class Ctx(object):
    """Everything the rules need for one restaurant, loaded once per request."""

    def __init__(self, r):
        self.r = r
        self.periods = list(app_tables.periods.search(restaurant=r))
        self.specials = {s["date"]: s for s in app_tables.special_days.search(restaurant=r)}
        self.all_tables = list(app_tables.dining_tables.search(tables.order_by("position"), restaurant=r))
        self.tables = [t for t in self.all_tables if t["active"] is not False]
        self.by_id = {t.get_id(): t for t in self.tables}
        self.joins = sorted(app_tables.table_joins.search(restaurant=r), key=_created_key)
        self.total_seats = sum(int(t["seats"] or 0) for t in self.tables)
        self.events = sorted(app_tables.events.search(restaurant=r), key=lambda e: (e["date"], int(e["start_min"] or 0)))
        self._res = {}

    def reservations(self, d):
        """Reservations on date d that hold a table (pending or confirmed)."""
        if d not in self._res:
            self._res[d] = [x for x in app_tables.reservations.search(restaurant=self.r, date=d) if x["status"] in ACTIVE]
        return self._res[d]

    def forget(self, d):
        self._res.pop(d, None)


# ---------------------------------------------------------------- opening hours
def period_for(periods, d):
    """The period that sets the regular hours on date d. When periods overlap, the shorter one wins
    (so "Summer 2026" beats "Regular hours"); on a tie, the newer one wins."""
    hits = [p for p in periods if (p["start"] is None or p["start"] <= d) and (p["end"] is None or d <= p["end"])]
    if not hits:
        return None

    def key(p):
        span = ((p["end"] or date.max) - (p["start"] or date.min)).days
        return (span, -_created_key(p))
    return sorted(hits, key=key)[0]


def day_hours(ctx, d):
    """(intervals in minutes, source) for date d. Special days override the regular hours."""
    sp = ctx.specials.get(d)
    if sp is not None:
        label = sp["label"] or "Special day"
        if sp["closed"]:
            return [], {"kind": "special", "label": label, "closed": True}
        return clean_intervals(sp["hours"]), {"kind": "special", "label": label, "closed": False}
    p = period_for(ctx.periods, d)
    if p is None:
        return [], {"kind": "none", "label": "No opening hours set", "closed": True}
    iv = clean_intervals((p["week"] or {}).get(str(d.weekday()), []))
    return iv, {"kind": "period", "label": p["name"] or "Opening hours", "id": p.get_id(), "closed": not iv}


def is_open_at(ctx, d, t):
    return any(o <= t < c for o, c in day_hours(ctx, d)[0])


# ---------------------------------------------------------------- events
def events_on(ctx, d):
    return [e for e in ctx.events if e["date"] == d]


def setup_at(ctx, d, t):
    """The event whose own room set-up applies at minute t of date d, or None (the everyday layout applies)."""
    for e in events_on(ctx, d):
        if e["layout"] is not None and int(e["start_min"] or 0) <= t < int(e["end_min"] or 0):
            return e
    return None


def blocked(ctx, d, t, dur):
    """True if a private event closes online booking for any part of [t, t+dur) on date d."""
    return any(e["blocks"] and int(e["start_min"] or 0) < t + dur and t < int(e["end_min"] or 0) for e in events_on(ctx, d))


def _event_units(ctx, ev):
    removed = set(ev["removed"] or [])
    used, units = set(), []
    for g in ev["groups"] or []:
        ids = [i for i in (g.get("tables") or []) if i in ctx.by_id and i not in removed and i not in used]
        if len(ids) < 2:
            continue
        used |= set(ids)
        rows = [ctx.by_id[i] for i in ids]
        units.append({"ids": ids, "join_id": None, "seats": int(g.get("seats") or sum(int(x["seats"] or 0) for x in rows)),
                      "min": max(1, min(int(x["min_party"] or 1) for x in rows)),
                      "label": g.get("label") or " + ".join(x["name"] for x in rows)})
    for tb in ctx.tables:
        if tb.get_id() not in used and tb.get_id() not in removed:
            units.append({"ids": [tb.get_id()], "join_id": None, "seats": int(tb["seats"] or 0),
                          "min": int(tb["min_party"] or 1), "label": tb["name"]})
    return units


# ---------------------------------------------------------------- table layout
def units_at(ctx, d, t):
    """The bookable units at minute t of date d: each active join, then every table not in one.
    A join is active when its hours include the hour of t and its days include d's weekday
    (no days = every day). A table can only be in one active join; the older join wins.
    During an event with its own room set-up, that set-up's groups and removed tables apply instead."""
    ev = setup_at(ctx, d, int(t))
    if ev is not None:
        return _event_units(ctx, ev)
    hour, wd = min(int(t) // 60, 23), d.weekday()
    used, units = set(), []
    for j in ctx.joins:
        ids = [i for i in (j["tables"] or []) if i in ctx.by_id]
        if len(ids) < 2 or hour not in (j["hours"] or []):
            continue
        days = j["days"] or []
        if days and wd not in days:
            continue
        if used & set(ids):
            continue
        used |= set(ids)
        rows = [ctx.by_id[i] for i in ids]
        units.append({
            "ids": ids, "join_id": j.get_id(),
            "seats": int(j["seats"] or sum(int(x["seats"] or 0) for x in rows)),
            "min": max(1, min(int(x["min_party"] or 1) for x in rows)),
            "label": j["label"] or " + ".join(x["name"] for x in rows),
        })
    for tb in ctx.tables:
        if tb.get_id() not in used:
            units.append({"ids": [tb.get_id()], "join_id": None, "seats": int(tb["seats"] or 0),
                          "min": int(tb["min_party"] or 1), "label": tb["name"]})
    return units


def busy_ids(ctx, d, t, dur, exclude=None):
    """Table ids held by reservations that overlap [t, t+dur) on date d."""
    out = set()
    for x in ctx.reservations(d):
        if exclude is not None and x == exclude:
            continue
        s = int(x["start_min"] or 0)
        e = s + int(x["duration"] or 0)
        if s < t + dur and t < e:
            out |= set(x["tables"] or [])
    return out


def occupancy(ctx, d, t, dur, exclude=None):
    """How full the restaurant is at its busiest moment in [t, t+dur), in % of seats at occupied tables."""
    if not ctx.total_seats:
        return 100
    step = max(5, setting(ctx.r, "slot_min"))
    peak = 0
    for m in range(int(t), int(t + dur), step):
        ids = busy_ids(ctx, d, m, 1, exclude)
        seats = sum(int(ctx.by_id[i]["seats"] or 0) for i in ids if i in ctx.by_id)
        peak = max(peak, seats)
    return int(round(100.0 * peak / ctx.total_seats))


def free_units(ctx, d, t, party, dur, exclude=None):
    """Units that fit the party and are free for the whole stay, best fit first."""
    busy = busy_ids(ctx, d, t, dur, exclude)
    fits = [u for u in units_at(ctx, d, t)
            if u["seats"] >= party and u["min"] <= party and not (set(u["ids"]) & busy)]
    fits.sort(key=lambda u: (u["seats"], len(u["ids"])))
    return fits


def find_unit(ctx, d, t, party, dur, exclude=None):
    fits = free_units(ctx, d, t, party, dur, exclude)
    return fits[0] if fits else None


# ---------------------------------------------------------------- what guests can book
def booking_window(ctx):
    """(earliest datetime a guest can book, last bookable date)."""
    now = local_now(ctx.r)
    return now + timedelta(minutes=setting(ctx.r, "lead_min")), now.date() + timedelta(days=setting(ctx.r, "window_days"))


def start_times(ctx, d):
    """Every start time (minutes) the form offers on date d, ignoring tables. Times that would overlap a
    private event (one that closes online booking) are left out."""
    r = ctx.r
    step, last, dur = setting(r, "slot_min"), setting(r, "last_booking_min"), setting(r, "duration_min")
    out = []
    for o, c in day_hours(ctx, d)[0]:
        t = o
        while t <= c - last:
            if not blocked(ctx, d, t, dur):
                out.append(t)
            t += step
    return out


def check_rules(ctx, d, t, party, dur, exclude=None):
    """(status, reason, occupancy%) for a booking that has a free table: confirmed, or pending with the reason."""
    r = ctx.r
    pct = occupancy(ctx, d, t, dur, exclude)
    thr, max_auto = setting(r, "auto_threshold"), setting(r, "max_auto_party")
    reasons = []
    if pct >= thr:
        reasons.append("The restaurant is %d%% booked at this time (auto-approval stops at %d%%)." % (pct, thr))
    if party > max_auto:
        reasons.append("A party of %d is above the auto-approval limit of %d." % (party, max_auto))
    return ("pending" if reasons else "confirmed"), " ".join(reasons), pct


def guest_slots(ctx, d, party, exclude=None):
    """The times shown on the booking form for date d, each with a state:
       open      → a table is free; `review` says the booking will wait for approval
       walk_in   → past the threshold and the restaurant takes walk-ins instead of online bookings
       full      → no table fits"""
    r = ctx.r
    earliest, last_day = booking_window(ctx)
    if d < earliest.date() or d > last_day:
        return []
    dur = setting(r, "duration_min")
    walk_in_mode = (r["over_capacity"] or "review") == "walk_in"
    out = []
    for t in start_times(ctx, d):
        if datetime.combine(d, time()) + timedelta(minutes=t) < earliest:
            continue
        unit = find_unit(ctx, d, t, party, dur, exclude)
        if unit is None:
            out.append({"time": hm(t), "state": "full"})
            continue
        status, reason, pct = check_rules(ctx, d, t, party, dur, exclude)
        if walk_in_mode and pct >= setting(r, "auto_threshold"):
            out.append({"time": hm(t), "state": "walk_in"})
        else:
            out.append({"time": hm(t), "state": "open", "review": status == "pending"})
    return out


# ---------------------------------------------------------------- views (JSON-friendly)
def reservation_view(res, ctx=None, staff=False):
    t = int(res["start_min"] or 0)
    v = {
        "id": res.get_id(), "token": res["token"], "date": iso(res["date"]), "time": hm(t),
        "end": hm(t + int(res["duration"] or 0)), "start_min": t, "duration": int(res["duration"] or 0),
        "party": int(res["party"] or 0), "name": res["name"] or "", "status": res["status"],
        "source": res["source"] or "online", "notes": res["notes"] or "", "language": res["language"] or "en",
    }
    if staff:
        names = []
        if ctx is not None:
            names = [ctx.by_id[i]["name"] for i in (res["tables"] or []) if i in ctx.by_id]
        v.update({
            "email": res["email"] or "", "phone": res["phone"] or "", "staff_note": res["staff_note"] or "",
            "tables": list(res["tables"] or []), "table_names": names,
            "review_reason": res["review_reason"] or "", "capacity_pct": res["capacity_pct"],
            "created": iso(res["created"]), "updated": iso(res["updated"]), "history": list(res["history"] or []),
            "consent": bool(res["consent"]), "consent_at": iso(res["consent_at"]),
        })
    return v


def table_view(t):
    return {"id": t.get_id(), "name": t["name"], "seats": int(t["seats"] or 0), "min_party": int(t["min_party"] or 1),
            "area": t["area"] or "", "shape": t["shape"] or "square", "x": t["x"] if t["x"] is not None else 10,
            "y": t["y"] if t["y"] is not None else 10, "active": t["active"] is not False}


def join_view(j):
    return {"id": j.get_id(), "tables": list(j["tables"] or []), "seats": int(j["seats"] or 0), "label": j["label"] or "",
            "hours": sorted(j["hours"] or []), "days": sorted(j["days"] or [])}


def public_restaurant(r, lang=None):
    lang = pick_language(r, lang)
    return {"name": r["name"], "slug": r["slug"], "description": r["description"] or "", "address": r["address"] or "",
            "phone": r["phone"] or "", "email": r["email"] or "", "website": r["website"] or "",
            "form_note": r["form_note"] or "", "privacy_text": r["privacy_text"] or DEFAULT_PRIVACY_BY_LANG.get(lang, DEFAULT_PRIVACY),
            "max_party": setting(r, "max_party"), "accepting": r["accepting"] is not False,
            "duration_min": setting(r, "duration_min"), "language": language(r), "languages": languages(r)}


def language(r):
    return r["language"] if r["language"] in LANGS else "en"


def languages(r):
    """The languages guests can choose on the form, the restaurant's own first."""
    offered = [x for x in (r["languages"] or []) if x in LANGS]
    main = language(r)
    return [main] + [x for x in offered if x != main]


def pick_language(r, wanted):
    return wanted if wanted in languages(r) else language(r)
