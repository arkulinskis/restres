# Public — Server Module. Everything a guest can do without an account:
#   the booking form (#book/<slug>) and the reservation page (#r/<token>), plus the website embed script.
# None of these callables need a signed-in user. The token is the only key to a reservation.
import json
import re
from datetime import datetime, time, timedelta

import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

from . import Booking as B

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _find(slug):
    """The restaurant with this booking-link slug, or None."""
    slug = str(slug or "").strip().lower()
    return app_tables.restaurants.get(slug=slug) if slug else None


def _days(ctx):
    """Every date guests can pick, each marked open or closed."""
    earliest, last = B.booking_window(ctx)
    d, out = earliest.date(), []
    while d <= last:
        iv, src = B.day_hours(ctx, d)
        out.append({"date": d.isoformat(), "open": bool(iv)})
        d += timedelta(days=1)
    return out


def _clean_guest(data, r, need_consent=True):
    """Validate the guest's details. Returns (fields, error)."""
    name = str(data.get("name") or "").strip()[:100]
    email = str(data.get("email") or "").strip()[:200]
    phone = str(data.get("phone") or "").strip()[:40]
    notes = str(data.get("notes") or "").strip()[:1000]
    if not name:
        return None, "Please enter your name."
    if not EMAIL_RE.match(email):
        return None, "Please enter a valid email address."
    if len(re.sub(r"\D", "", phone)) < 6:
        return None, "Please enter a phone number we can reach you on."
    if need_consent and not data.get("consent"):
        return None, "Please confirm that you have read how we use your details."
    return {"name": name, "email": email, "phone": phone, "notes": notes}, None


def _party(data, r):
    try:
        p = int(data.get("party"))
    except (TypeError, ValueError):
        return None
    return p if 1 <= p <= B.setting(r, "max_party") else None


def _slot_state(ctx, d, t, party, exclude=None):
    for s in B.guest_slots(ctx, d, party, exclude):
        if s["time"] == B.hm(t):
            return s["state"]
    return None


# ---------------------------------------------------------------- the booking form
@anvil.server.callable
def get_booking_form(slug, lang=None):
    r = _find(slug)
    if r is None:
        return {"ok": False, "error": "We couldn't find this restaurant. Check the link and try again."}
    ctx = B.Ctx(r)
    lang = B.pick_language(r, lang)
    return {"ok": True, "restaurant": B.public_restaurant(r, lang), "days": _days(ctx), "today": B.local_now(r).date().isoformat(),
            "lang": lang, "privacy": {x: B.public_restaurant(r, x)["privacy_text"] for x in B.languages(r)}}


@anvil.server.callable
def get_slots(slug, day, party, token=None):
    r = _find(slug)
    if r is None:
        return {"ok": False, "error": "Restaurant not found."}
    try:
        d = B.parse_date(day)
    except ValueError:
        return {"ok": False, "error": "Pick a date."}
    party = _party({"party": party}, r)
    if party is None:
        return {"ok": False, "error": "Pick the number of guests."}
    ctx = B.Ctx(r)
    exclude = None
    if token:
        exclude = app_tables.reservations.get(token=str(token))
        if exclude is not None and exclude["restaurant"] != r:
            exclude = None
    iv, src = B.day_hours(ctx, d)
    return {"ok": True, "date": d.isoformat(), "party": party, "slots": B.guest_slots(ctx, d, party, exclude),
            "hours": B.intervals_text(iv), "closed": not iv, "label": src.get("label") if src.get("kind") == "special" else ""}


@tables.in_transaction
def _book(r, d, t, party, guest, consent_text, lang="en"):
    ctx = B.Ctx(r)
    state = _slot_state(ctx, d, t, party)
    if state != "open":
        return None, ("We're nearly full at that time, but walk-ins are welcome." if state == "walk_in"
                      else "Sorry, that time was just taken. Please pick another time.")
    dur = B.setting(r, "duration_min")
    unit = B.find_unit(ctx, d, t, party, dur)
    if unit is None:
        return None, "Sorry, that time was just taken. Please pick another time."
    status, reason, pct = B.check_rules(ctx, d, t, party, dur)
    now = B.now_utc()
    res = app_tables.reservations.add_row(
        restaurant=r, token=B.new_token(), date=d, start_min=t, duration=dur, party=party,
        name=guest["name"], email=guest["email"], phone=guest["phone"], notes=guest["notes"],
        status=status, source="online", tables=unit["ids"], review_reason=reason, capacity_pct=pct,
        consent=True, consent_text=consent_text, consent_at=now, created=now, updated=now, history=[], language=lang)
    B.add_history(res, "guest", "Booked online for %d on %s at %s%s." % (
        party, d.isoformat(), B.hm(t), "" if status == "confirmed" else " (awaiting approval)"))
    return res, None


@anvil.server.callable
def book(slug, data):
    data = dict(data or {})
    r = _find(slug)
    if r is None:
        return {"ok": False, "error": "Restaurant not found."}
    if r["accepting"] is False:
        return {"ok": False, "error": "Online booking is closed right now. Please call us."}
    if data.get("website"):  # the hidden honeypot field: only bots fill it in
        return {"ok": False, "error": "Something went wrong. Please try again."}
    try:
        d, t = B.parse_date(data.get("date")), B.parse_hm(data.get("time"))
    except ValueError:
        return {"ok": False, "error": "Pick a date and a time."}
    party = _party(data, r)
    if party is None:
        return {"ok": False, "error": "Pick the number of guests."}
    guest, err = _clean_guest(data, r)
    if err:
        return {"ok": False, "error": err}
    lang = B.pick_language(r, data.get("language"))
    consent_text = B.public_restaurant(r, lang)["privacy_text"]
    res, err = _book(r, d, t, party, guest, consent_text, lang)
    if err:
        return {"ok": False, "error": err}
    _notify_new(res)
    return {"ok": True, "token": res["token"], "status": res["status"], "reservation": B.reservation_view(res),
            "restaurant": B.public_restaurant(r)}


def _notify_new(res):
    """Hook for emails (confirmation to the guest, approval alert to staff). See the planplate skill."""
    try:
        from . import Notify
        Notify.reservation_event(res, "created")
    except Exception as e:  # emails must never break a booking
        print("notify failed:", e)


# ---------------------------------------------------------------- the guest's reservation page
def _by_token(token):
    if not token or not re.match(r"^[0-9a-f]{32}$", str(token)):
        return None
    return app_tables.reservations.get(token=str(token))


def _can(res):
    """(can_change, can_cancel) for the guest: only before the visit, and only while it holds a table."""
    r = res["restaurant"]
    start = datetime.combine(res["date"], time()) + timedelta(minutes=int(res["start_min"] or 0))
    now = B.local_now(r)
    live = res["status"] in B.ACTIVE
    return (live and start - now >= timedelta(minutes=B.setting(r, "lead_min")) and r["accepting"] is not False,
            live and start > now)


def _guest_reply(res):
    r = res["restaurant"]
    can_change, can_cancel = _can(res)
    out = {"ok": True, "reservation": B.reservation_view(res), "restaurant": B.public_restaurant(r, res["language"]),
           "can_change": can_change, "can_cancel": can_cancel,
           "guest": {"email": res["email"] or "", "phone": res["phone"] or ""}}
    if can_change:
        ctx = B.Ctx(r)
        out["days"] = _days(ctx)
    return out


@anvil.server.callable
def get_reservation(token):
    res = _by_token(token)
    if res is None:
        return {"ok": False, "error": "We couldn't find this reservation. Check that you used the full link."}
    return _guest_reply(res)


@tables.in_transaction
def _change(res, d, t, party, guest):
    r = res["restaurant"]
    ctx = B.Ctx(r)
    same_slot = res["date"] == d and int(res["start_min"]) == t and int(res["party"]) == party
    changes = []
    for k in ("name", "phone", "notes", "email"):
        if guest[k] != (res[k] or ""):
            changes.append(k)
    if same_slot:
        if not changes:
            return None
        res.update(**guest)
    else:
        if _slot_state(ctx, d, t, party, exclude=res) != "open":
            return "Sorry, that time isn't available. Please pick another."
        dur = int(res["duration"] or B.setting(r, "duration_min"))
        unit = B.find_unit(ctx, d, t, party, dur, exclude=res)
        if unit is None:
            return "Sorry, that time isn't available. Please pick another."
        status, reason, pct = B.check_rules(ctx, d, t, party, dur, exclude=res)
        if res["status"] == "pending":
            status = "pending"  # a change never skips an approval that is still waiting
            reason = reason or res["review_reason"]
        res.update(date=d, start_min=t, party=party, tables=unit["ids"], status=status,
                   review_reason=reason if status == "pending" else "", capacity_pct=pct, **guest)
        changes.insert(0, "moved to %s %s for %d" % (d.isoformat(), B.hm(t), party))
    res["updated"] = B.now_utc()
    B.add_history(res, "guest", "Changed: " + ", ".join(changes) + ".")
    return None


@anvil.server.callable
def change_reservation(token, data):
    data = dict(data or {})
    res = _by_token(token)
    if res is None:
        return {"ok": False, "error": "Reservation not found."}
    if not _can(res)[0]:
        return {"ok": False, "error": "This reservation can no longer be changed online. Please call the restaurant."}
    r = res["restaurant"]
    try:
        d, t = B.parse_date(data.get("date")), B.parse_hm(data.get("time"))
    except ValueError:
        return {"ok": False, "error": "Pick a date and a time."}
    party = _party(data, r)
    if party is None:
        return {"ok": False, "error": "Pick the number of guests."}
    guest, err = _clean_guest(data, r, need_consent=False)
    if err:
        return {"ok": False, "error": err}
    before = res["status"]
    err = _change(res, d, t, party, guest)
    if err:
        return {"ok": False, "error": err}
    try:
        from . import Notify
        Notify.reservation_event(res, "changed", before=before)
    except Exception as e:
        print("notify failed:", e)
    return _guest_reply(res)


@anvil.server.callable
def cancel_reservation(token):
    res = _by_token(token)
    if res is None:
        return {"ok": False, "error": "Reservation not found."}
    if not _can(res)[1]:
        return {"ok": False, "error": "This reservation can't be cancelled online any more."}
    res.update(status="cancelled", updated=B.now_utc())
    B.add_history(res, "guest", "Cancelled by the guest.")
    try:
        from . import Notify
        Notify.reservation_event(res, "cancelled")
    except Exception as e:
        print("notify failed:", e)
    return _guest_reply(res)


# ---------------------------------------------------------------- website embed
EMBED_JS = r"""(function(){
  var ORIGIN=%(origin)s, SLUG=%(slug)s, LABEL=%(label)s;
  var me=document.currentScript;
  function open(){
    var o=document.createElement('div');
    o.setAttribute('style','position:fixed;inset:0;z-index:2147483000;background:rgba(20,18,15,.55);display:flex;align-items:center;justify-content:center;padding:16px');
    var box=document.createElement('div');
    box.setAttribute('style','position:relative;width:min(560px,100%%);height:min(820px,100%%);background:#faf8f4;border-radius:14px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.35)');
    var x=document.createElement('button');
    x.setAttribute('aria-label','Close');x.innerHTML='&times;';
    x.setAttribute('style','position:absolute;top:8px;right:10px;z-index:2;border:0;background:transparent;font:28px/1 Georgia,serif;color:#555;cursor:pointer');
    var f=document.createElement('iframe');
    f.src=ORIGIN+'/#book/'+SLUG;f.title='Reserve a table';
    f.setAttribute('style','border:0;width:100%%;height:100%%');
    function close(){o.remove();document.removeEventListener('keydown',esc);}
    function esc(e){if(e.key==='Escape')close();}
    x.onclick=close;o.onclick=function(e){if(e.target===o)close();};
    document.addEventListener('keydown',esc);
    box.appendChild(x);box.appendChild(f);o.appendChild(box);document.body.appendChild(o);
  }
  var hooks=document.querySelectorAll('[data-planplate-open]');
  if(hooks.length){hooks.forEach(function(h){h.addEventListener('click',function(e){e.preventDefault();open();});});}
  else if(me){
    var b=document.createElement('button');b.type='button';b.textContent=LABEL;
    b.setAttribute('style','font:500 15px/1 system-ui,sans-serif;letter-spacing:.04em;padding:14px 26px;border-radius:999px;border:1px solid #1d1b18;background:#1d1b18;color:#faf8f4;cursor:pointer');
    b.onclick=open;me.parentNode.insertBefore(b,me);
  }
  window.PlanPlate={open:open};
})();
"""


@anvil.server.http_endpoint("/embed.js")
def embed_js(r=None, label=None, **kw):
    slug = str(r or "").strip().lower()
    body = EMBED_JS % {"origin": json.dumps(anvil.server.get_app_origin()), "slug": json.dumps(slug),
                       "label": json.dumps(str(label or "Reserve a table")[:40])}
    return anvil.server.HttpResponse(200, body, headers={"Content-Type": "application/javascript; charset=utf-8",
                                                         "Cache-Control": "max-age=300"})
