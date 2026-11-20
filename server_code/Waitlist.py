# Waitlist — Server Module. A full day is no longer a dead end (2026-11-20).
#   Guests: when no time fits, the booking form offers the nearest days with room (Public._alt_days) and "Join the
#     waitlist" (join_waitlist): date, party, Lunch / Dinner / Any time, name, email, phone. Nothing is booked and no
#     email goes out: the restaurant calls or messages them when a table frees up.
#   Staff: Reservations shows "Waitlist · 3" for the day shown (Portal.get_day -> day_view), each entry with "Table free
#     at 19:30" once a cancellation or a no-show opens one (`fits`), and Book (the booking editor, pre-filled; saving
#     marks the entry booked: Portal.save_reservation -> mark_booked), Call, Message (a pre-written WhatsApp / SMS in
#     the guest's language, Remind.links) and Remove.
#   The table is new: until the owner accepts Anvil's schema change, _table() is None, the form never offers the
#   waitlist (get_booking_form sends waitlist False) and the live app behaves exactly as before.
from datetime import timedelta

import anvil.server
from anvil.tables import app_tables

from . import Booking as B
from . import GuestNews
from . import common as C

WINDOWS = {"lunch": (11 * 60, 16 * 60), "dinner": (16 * 60, 24 * 60), "any": (0, 24 * 60)}
WINDOW_NAMES = {"lunch": "Lunch", "dinner": "Dinner", "any": "Any time"}
MAX_PER_DAY = 200     # waiting entries per restaurant and day (a bot can't fill the list for ever)
KEEP_DAYS = 30        # entries for days longer ago than this are deleted (they're only useful until the day)
TEXT = {
    "en": {"msg": "Hello {n}, good news from {r}: a table for {p} is free {when} at {t}. Reply to this message{call} to take it.",
           "call": " or call {phone}"},
    "fr": {"msg": "Bonjour {n}, bonne nouvelle de {r} : une table pour {p} s'est libérée {when} à {t}. Répondez à ce message{call} "
                  "pour la réserver.",
           "call": " ou appelez le {phone}"},
    "lv": {"msg": "Labdien, {n}! Labas ziņas no {r}: {when} plkst. {t} ir atbrīvojies galdiņš ({p}). Atbildiet uz šo ziņu{call}, "
                  "lai to rezervētu.",
           "call": " vai zvaniet {phone}"},
}


def _table():
    """The waitlist table, or None while the live database doesn't have it yet (until the owner accepts Anvil's
    schema change). Everything here asks this first, so the app keeps working unchanged until then."""
    try:
        return getattr(app_tables, "waitlist", None)
    except Exception:
        return None


def available():
    return _table() is not None


def window_name(a, b):
    for k, (x, y) in WINDOWS.items():
        if (x, y) == (int(a or 0), int(b if b is not None else 1440)):
            return k
    return "any"


def _row(r, wid):
    T = _table()
    try:
        w = T.get_by_id(wid) if T is not None and wid else None
    except Exception:
        w = None
    if w is None or w["restaurant"] != r:
        raise anvil.server.PermissionDenied("That waitlist entry doesn't belong to this restaurant.")
    return w


def _fits(ctx, d, a, b, party, now):
    """(first time in the guest's window when a table fits, needs tables pushed together?) or (None, False)."""
    dur = B.setting(ctx.r, "duration_min")
    joined = None
    for t in B.start_times(ctx, d):
        if not (a <= t < b):
            continue
        if d == now.date() and t < now.hour * 60 + now.minute:
            continue
        unit, plan = B.seat_party(ctx, d, t, party, dur)
        if unit is not None:
            return B.hm(t), False
        if plan is not None and joined is None:
            joined = B.hm(t)
    return (joined, True) if joined else (None, False)


def view(r, ctx, w, now):
    from . import Remind
    d, a = w["date"], int(w["from_min"] or 0)
    b = int(w["to_min"] if w["to_min"] is not None else 1440)
    party, lang = int(w["party"] or 2), Remind.lang_of(w["language"])
    fits, join = _fits(ctx, d, a, b, party, now) if w["status"] == "waiting" else (None, False)
    v = {"id": w.get_id(), "date": B.iso(d), "party": party, "name": w["name"] or "", "email": w["email"] or "",
         "phone": w["phone"] or "", "notes": w["notes"] or "", "language": lang, "window": window_name(a, b),
         "window_label": WINDOW_NAMES[window_name(a, b)], "status": w["status"] or "waiting",
         "created": B.iso(w["created"]), "fits": fits, "join": join}
    text = ""
    if fits:
        t = TEXT[lang]
        call = Remind.fill(t["call"], phone=r["phone"]) if r["phone"] else ""
        text = Remind.fill(t["msg"], n=(w["name"] or "").split(" ")[0], r=r["name"] or "", p=Remind.party_text(party, lang),
                           when=Remind.when_text(d, now.date(), lang), t=Remind.time_text(B.parse_hm(fits), lang), call=call)
    v["message"] = text
    v.update(Remind.links(r, w["phone"], "", text, ""))
    if not fits:
        v["wa"] = v["sms"] = ""  # nothing to offer yet: Call still works
    return v


def day_view(r, ctx, d, now=None):
    """The waiting entries for date d (first come, first served), or None while the table doesn't exist."""
    T = _table()
    if T is None:
        return None
    now = now or B.local_now(r)
    rows = sorted([w for w in T.search(restaurant=r, date=d) if w["status"] == "waiting"], key=B._created_key)
    return [view(r, ctx, w, now) for w in rows]


def count(r, d):
    T = _table()
    if T is None:
        return 0
    return len([w for w in T.search(restaurant=r, date=d) if w["status"] == "waiting"])


def _tidy(T, r, today):
    """Forget entries for days long gone (they hold guests' details and help nobody any more)."""
    for w in T.search(restaurant=r):
        if w["date"] is not None and w["date"] < today - timedelta(days=KEEP_DAYS):
            w.delete()


def mark_booked(r, wid, res_id):
    """The booking editor saved a booking for this entry: it leaves the list. Never breaks the booking."""
    try:
        w = _row(r, wid)
        res = app_tables.reservations.get_by_id(res_id)
        w.update(status="booked", reservation=res if res is not None and res["restaurant"] == r else None, updated=B.now_utc())
        return True
    except Exception as e:
        print("waitlist entry not marked booked:", e)
        return False


def delete_for(r):
    """When a restaurant (or the demo) is deleted."""
    T = _table()
    if T is not None:
        for w in list(T.search(restaurant=r)):
            w.delete()


# ---------------------------------------------------------------- callables
@anvil.server.callable
def join_waitlist(slug, data):
    """The guest's waitlist request from the booking form (no account, no email sent)."""
    from . import Public as P
    data = dict(data or {})
    r = P._find(slug)
    if r is None:
        return {"ok": False, "error": "Restaurant not found."}
    T = _table()
    if T is None:
        return {"ok": False, "error": "The waitlist isn't open yet. Please call the restaurant."}
    if r["accepting"] is False:
        return {"ok": False, "error": "Online booking is closed right now. Please call us."}
    if data.get("website"):  # the honeypot
        return {"ok": False, "error": "Something went wrong. Please try again."}
    if C.rate_limited("waitlist", 6, 3600):
        return {"ok": False, "error": "Too many requests. Please try again later, or call us."}
    try:
        d = B.parse_date(data.get("date"))
    except ValueError:
        return {"ok": False, "error": "Pick a date."}
    party = P._party(data, r)
    if party is None:
        return {"ok": False, "error": "Pick the number of guests."}
    ctx = B.Ctx(r)
    earliest, last = B.booking_window(ctx)
    if d < earliest.date() or d > last:
        return {"ok": False, "error": "Pick a day you can book online."}
    if not B.day_hours(ctx, d)[0]:
        return {"ok": False, "error": "The restaurant is closed on that day."}
    win = data.get("window") if data.get("window") in WINDOWS else "any"
    a, b = WINDOWS[win]
    if not [t for t in B.start_times(ctx, d) if a <= t < b]:
        return {"ok": False, "error": {"lunch": "There's no lunch service that day.",
                                       "dinner": "There's no dinner service that day."}.get(win, "The restaurant is closed on that day.")}
    guest, err = P._clean_guest(data, r, need_consent=False)
    if err or guest is None:
        return {"ok": False, "error": err or "Please check your details."}
    lang = B.pick_language(r, data.get("language"))
    if not data.get("pp_consent"):  # the same "By booking, you accept..." line as the booking form (GuestNews)
        return {"ok": False, "error": GuestNews.t(lang)["need"]}
    now = B.now_utc()
    fields = {"party": party, "from_min": a, "to_min": b, "name": guest["name"], "email": guest["email"], "phone": guest["phone"],
              "notes": guest["notes"], "language": lang, "consent_text": B.public_restaurant(r, lang)["privacy_text"],
              "pp_consent_text": GuestNews.consent_text(lang, r["name"]), "updated": now}
    rows = list(T.search(restaurant=r, date=d))
    waiting = [w for w in rows if w["status"] == "waiting"]
    same = [w for w in waiting if (w["email"] or "").lower() == guest["email"].lower()]
    if same:  # one entry per email and day: joining again updates it
        same[0].update(**fields)
    else:
        if len(waiting) >= MAX_PER_DAY:
            return {"ok": False, "error": "The waitlist for that day is full. Please call us."}
        T.add_row(restaurant=r, token=B.new_token(), date=d, status="waiting", reservation=None, created=now, **fields)
    try:
        _tidy(T, r, B.local_now(r).date())
    except Exception as e:
        print("waitlist tidy failed:", e)
    return {"ok": True, "again": bool(same), "date": d.isoformat(), "party": party, "window": win}


@anvil.server.callable(require_user=True)
def get_waitlist(rid, day=None):
    from .Portal import _rest
    r = _rest(rid)
    now = B.local_now(r)
    try:
        d = B.parse_date(day) if day else now.date()
    except ValueError:
        d = now.date()
    entries = day_view(r, B.Ctx(r), d, now)
    return {"ok": True, "date": d.isoformat(), "on": entries is not None, "entries": entries or []}


@anvil.server.callable(require_user=True)
def remove_waitlist(rid, wid):
    """Take someone off the list (they found another evening, or said no). Returns the day's new data."""
    from .Portal import _rest, get_day
    r = _rest(rid)
    w = _row(r, wid)
    w.update(status="removed", updated=B.now_utc())
    return {"ok": True, "day": get_day(rid, B.iso(w["date"]))}
