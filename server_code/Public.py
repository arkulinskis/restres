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
from . import GuestNews

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _find(slug):
    """The restaurant with this booking-link slug, or None."""
    slug = str(slug or "").strip().lower()
    return app_tables.restaurants.get(slug=slug) if slug else None


def _days(ctx):
    """Every date guests can pick, each marked open or closed."""
    earliest, last = B.booking_window(ctx)
    d, out = earliest.date(), []
    soon = earliest.hour * 60 + earliest.minute
    while d <= last:
        iv, src = B.day_hours(ctx, d)
        is_open = bool(iv)
        if is_open and d == earliest.date():  # the first day counts only while a start time is still bookable
            is_open = any(t >= soon for t in B.start_times(ctx, d))
        out.append({"date": d.isoformat(), "open": is_open})
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
def _demo(slug):
    """The demo restaurant (DemoData) appears the first time someone opens its booking form or menu."""
    if slug == "maison-lumiere":
        from . import DemoData
        DemoData.ensure_loaded()


@anvil.server.callable
def get_booking_form(slug, lang=None):
    _demo(slug)
    r = _find(slug)
    if r is None:
        return {"ok": False, "error": "We couldn't find this restaurant. Check the link and try again."}
    ctx = B.Ctx(r)
    lang = B.pick_language(r, lang)
    from . import Waitlist
    return {"ok": True, "restaurant": B.public_restaurant(r, lang), "days": _days(ctx), "today": B.local_now(r).date().isoformat(),
            "lang": lang, "privacy": {x: B.public_restaurant(r, x)["privacy_text"] for x in B.languages(r)},
            "pp": GuestNews.texts(), "waitlist": Waitlist.available()}


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
    slots = B.guest_slots(ctx, d, party, exclude)
    out = {"ok": True, "date": d.isoformat(), "party": party, "slots": slots,
           "hours": B.intervals_text(iv), "closed": not iv, "label": src.get("label") if src.get("kind") == "special" else ""}
    if iv and not token and not any(s["state"] == "open" for s in slots):
        out["alt_days"] = _alt_days(ctx, d, party)  # a full day is no dead end: the nearest days with room
    return out


def _alt_days(ctx, d, party, want=3, reach=7):
    """Up to `want` days within `reach` days of d (nearest first, either side) where a table for the party is free."""
    earliest, last = B.booking_window(ctx)
    found = []
    for k in range(1, reach + 1):
        for dd in (d + timedelta(days=k), d - timedelta(days=k)):
            if len(found) >= want or dd < earliest.date() or dd > last:
                continue
            free = [s for s in B.guest_slots(ctx, dd, party) if s["state"] == "open"]
            if free:
                found.append({"date": dd.isoformat(), "times": len(free), "first": free[0]["time"]})
        if len(found) >= want:
            break
    return sorted(found, key=lambda x: x["date"])


@tables.in_transaction
def _book(r, d, t, party, guest, consent_text, lang="en", pp=None):
    ctx = B.Ctx(r)
    state = _slot_state(ctx, d, t, party)
    if state != "open":
        return None, ("We're nearly full at that time, but walk-ins are welcome." if state == "walk_in"
                      else "Sorry, that time was just taken. Please pick another time.")
    dur = B.setting(r, "duration_min")
    unit, plan = B.seat_party(ctx, d, t, party, dur)
    if unit is None and plan is None:
        return None, "Sorry, that time was just taken. Please pick another time."
    status, reason, pct = B.check_rules(ctx, d, t, party, dur, notes=guest["notes"])
    if B.flag(r, "review_no_shows"):  # Settings -> Approvals: "Guests who missed a booking before wait for me"
        from . import Guests
        missed, last = Guests.no_shows_of(r, guest["email"], guest["phone"], guest["name"])
        if missed:
            status, reason = "pending", (Guests.no_show_reason(missed, last) + " " + reason).strip()
    if plan is not None:  # tables have to be pushed together (maybe after moving another booking): a manager decides
        status, reason = "pending", ("No single table fits. " + plan["text"] + " " + reason).strip()
    now = B.now_utc()
    res = app_tables.reservations.add_row(
        restaurant=r, token=B.new_token(), date=d, start_min=t, duration=dur, party=party,
        name=guest["name"], email=guest["email"], phone=guest["phone"], notes=guest["notes"],
        status=status, source="online", tables=unit["ids"] if unit else plan["ids"], review_reason=reason, capacity_pct=pct,
        consent=True, consent_text=consent_text, consent_at=now, created=now, updated=now, history=[], language=lang,
        **(pp or {}))
    if plan is not None:
        B.save_plan(res, plan)
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
    if not data.get("pp_consent"):  # the guest booked under the "By booking you accept..." line (GuestNews)
        return {"ok": False, "error": GuestNews.t(lang)["need"]}
    consent_text = B.public_restaurant(r, lang)["privacy_text"]
    news = bool(data.get("pp_news"))
    pp = {"pp_consent": True, "pp_consent_text": GuestNews.consent_text(lang, r["name"]), "pp_consent_at": B.now_utc(), "pp_news": news}
    res, err = _book(r, d, t, party, guest, consent_text, lang, pp)
    if err:
        return {"ok": False, "error": err}
    try:
        GuestNews.on_booking(res, news)
    except Exception as e:  # the news list must never break a booking
        print("news list failed:", e)
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


def _can_confirm(res):
    """May the guest tap "Yes, we're coming"? A confirmed booking that hasn't started, from 48 hours before (or as soon
    as the restaurant sent a reminder: a closed Sunday and Monday can mean reminding on Saturday for Tuesday)."""
    if res["status"] != "confirmed" or res["date"] is None:
        return False
    start = datetime.combine(res["date"], time()) + timedelta(minutes=int(res["start_min"] or 0))
    now = B.local_now(res["restaurant"])
    return start > now and (start - now <= timedelta(hours=48) or bool(B.history_flags(res)["reminded"]))


def _guest_reply(res):
    r = res["restaurant"]
    can_change, can_cancel = _can(res)
    out = {"ok": True, "reservation": B.reservation_view(res), "restaurant": B.public_restaurant(r, res["language"]),
           "can_change": can_change, "can_cancel": can_cancel, "can_confirm": _can_confirm(res),
           "guest": {"email": res["email"] or "", "phone": res["phone"] or ""},
           "news": GuestNews.subscribed(res["email"]), "pp": GuestNews.texts()}
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
    new_time = res["date"] != d or int(res["start_min"]) != t  # a reminder or a "we're coming" was for the old time
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
        status, reason, pct = B.check_rules(ctx, d, t, party, dur, exclude=res, notes=guest["notes"])
        if res["status"] == "pending":
            status = "pending"  # a change never skips an approval that is still waiting
            reason = reason or res["review_reason"]
        res.update(date=d, start_min=t, party=party, tables=unit["ids"], status=status,
                   review_reason=reason if status == "pending" else "", capacity_pct=pct, **guest)
        changes.insert(0, "moved to %s %s for %d" % (d.isoformat(), B.hm(t), party))
    res["updated"] = B.now_utc()
    B.add_history(res, "guest", "Changed: " + ", ".join(changes) + ".", kind="moved" if new_time else None)
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


@anvil.server.callable
def confirm_coming(token):
    """The guest taps "Yes, we're coming" on their reservation page (usually from the restaurant's reminder). The host
    stand then shows "Coming" next to the booking (it reads the history: Booking.history_flags)."""
    from . import common as C
    if C.rate_limited("confirm_coming", 20, 3600):
        return {"ok": False, "error": "Too many tries. Please try again in a while."}
    res = _by_token(token)
    if res is None:
        return {"ok": False, "error": "Reservation not found."}
    if not _can_confirm(res):
        return {"ok": False, "error": "This reservation can't be confirmed online any more."}
    if not B.history_flags(res)["coming"]:
        res["updated"] = B.now_utc()
        B.add_history(res, "guest", "The guest confirmed they are coming.", kind="confirm")
    return _guest_reply(res)


# ---------------------------------------------------------------- website embed
# /_/api/embed.js?r=<slug> draws PlanPlate's "Reserve a table" button where the script tag stands (like a "Sign in with
# Google" button: the restaurant can't restyle it by accident, but can pick a style), and opens the booking form in a
# window over the page. Options in the address: style=ink|brass|light|outline, shape=pill|rounded, size=sm|md|lg,
# lang=en|fr|lv, label=<own words>, button=none (no button: only elements with data-planplate-open open the form).
# Elements with data-planplate-open always open it too. Loading the script twice never binds an element twice.
EMBED_LABELS = {"en": "Reserve a table", "fr": "Réserver une table", "lv": "Rezervēt galdiņu"}
EMBED_CLOSE = {"en": "Close", "fr": "Fermer", "lv": "Aizvērt"}
EMBED_JS = r"""(function(){
  var ORIGIN=__ORIGIN__, SLUG=__SLUG__, LABEL=__LABEL__, OPT=__OPT__, CLOSE=__CLOSE__;
  var me=document.currentScript;
  var MARK='<svg viewBox="0 0 32 32" width="20" height="20" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="16" cy="16" r="13" stroke-width="1.6"/><circle cx="16" cy="16" r="8.2" stroke-width="1.2"/><path d="M16 10.8v10.4" stroke-width="1.7" stroke-linecap="round"/></svg>';
  function css(){
    if(document.getElementById('pp-embed-css'))return;
    var s=document.createElement('style');s.id='pp-embed-css';
    s.textContent=[
      '.pp-reserve{box-sizing:border-box;display:inline-flex;align-items:center;gap:10px;height:48px;margin:0;padding:0 22px 0 8px;border:1px solid transparent;border-radius:999px;font:600 15px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;letter-spacing:.01em;text-decoration:none;cursor:pointer;-webkit-tap-highlight-color:transparent;box-shadow:0 1px 2px rgba(20,18,15,.14),0 6px 18px -6px rgba(20,18,15,.28);transition:transform .16s cubic-bezier(.2,.8,.2,1),box-shadow .16s cubic-bezier(.2,.8,.2,1),background-color .16s,filter .16s;white-space:nowrap}',
      '.pp-reserve .pp-reserve-mark{display:inline-grid;place-items:center;flex:none;width:32px;height:32px;border-radius:999px}',
      '.pp-reserve:hover{transform:translateY(-1px);box-shadow:0 2px 4px rgba(20,18,15,.14),0 12px 26px -8px rgba(20,18,15,.34)}',
      '.pp-reserve:active{transform:translateY(0) scale(.98);box-shadow:0 1px 2px rgba(20,18,15,.18)}',
      '.pp-reserve:focus-visible{outline:3px solid #c9a56a;outline-offset:3px}',
      '.pp-reserve.pp-ink{background:#1d1b18;color:#faf8f4}.pp-reserve.pp-ink .pp-reserve-mark{background:#faf8f4;color:#826638}',
      '.pp-reserve.pp-brass{background:#826638;color:#fff}.pp-reserve.pp-brass .pp-reserve-mark{background:rgba(255,255,255,.16);color:#fff}',
      '.pp-reserve.pp-light{background:#fff;color:#1d1b18;border-color:#dcd5c9}.pp-reserve.pp-light .pp-reserve-mark{background:#f3eee6;color:#826638}',
      '.pp-reserve.pp-outline{background:transparent;color:inherit;border:1.5px solid currentColor;box-shadow:none}.pp-reserve.pp-outline .pp-reserve-mark{border:1.2px solid currentColor}',
      '.pp-reserve.pp-outline:hover{box-shadow:none;filter:brightness(1.08)}',
      '.pp-reserve.pp-rounded{border-radius:12px}.pp-reserve.pp-rounded .pp-reserve-mark{border-radius:8px}',
      '.pp-reserve.pp-sm{height:40px;font-size:14px;padding-right:18px;padding-left:6px}.pp-reserve.pp-sm .pp-reserve-mark{width:28px;height:28px}',
      '.pp-reserve.pp-lg{height:56px;font-size:16.5px;padding-right:26px;padding-left:10px;gap:12px}.pp-reserve.pp-lg .pp-reserve-mark{width:38px;height:38px}',
      '.pp-modal{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(20,18,15,.55);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px);animation:pp-fade .2s cubic-bezier(.2,.8,.2,1)}',
      '.pp-modal-box{position:relative;width:min(560px,100%);height:min(860px,100%);background:#faf8f4;border-radius:18px;overflow:hidden;box-shadow:0 30px 80px -20px rgba(0,0,0,.5);animation:pp-rise .26s cubic-bezier(.2,.8,.2,1)}',
      '.pp-modal iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent}',
      '.pp-modal-x{position:absolute;top:12px;right:12px;z-index:2;display:grid;place-items:center;width:36px;height:36px;margin:0;padding:0;border:1px solid rgba(29,27,24,.12);border-radius:999px;background:rgba(250,248,244,.92);color:#1d1b18;cursor:pointer;transition:background-color .16s,transform .16s}',
      '.pp-modal-x:hover{background:#fff;transform:scale(1.05)}.pp-modal-x:focus-visible{outline:3px solid #c9a56a;outline-offset:2px}',
      '.pp-modal-wait{position:absolute;inset:0;display:grid;place-items:center;color:#826638}.pp-modal-wait svg{width:38px;height:38px;animation:pp-spin 1.1s linear infinite}',
      '@keyframes pp-fade{from{opacity:0}}@keyframes pp-rise{from{opacity:0;transform:translateY(14px) scale(.985)}}@keyframes pp-spin{to{transform:rotate(360deg)}}',
      '@media (max-width:560px){.pp-modal{padding:0}.pp-modal-box{width:100%;height:100%;border-radius:0}}',
      '@media (prefers-reduced-motion:reduce){.pp-reserve,.pp-modal,.pp-modal-box,.pp-modal-x{animation:none;transition:none}.pp-modal-wait svg{animation-duration:3s}}'
    ].join('');
    (document.head||document.documentElement).appendChild(s);
  }
  function open(ev){
    css();
    var opener=document.activeElement;
    var o=document.createElement('div');o.className='pp-modal';
    o.setAttribute('role','dialog');o.setAttribute('aria-modal','true');o.setAttribute('aria-label',LABEL);
    var box=document.createElement('div');box.className='pp-modal-box';
    var wait=document.createElement('div');wait.className='pp-modal-wait';wait.innerHTML=MARK;
    var x=document.createElement('button');x.type='button';x.className='pp-modal-x';x.setAttribute('aria-label',CLOSE);
    x.innerHTML='<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>';
    var f=document.createElement('iframe');
    f.src=ORIGIN+'/#book/'+encodeURIComponent(SLUG)+(OPT.lang?'/'+OPT.lang:'');f.title=LABEL;f.setAttribute('allow','clipboard-write');
    f.addEventListener('load',function(){wait.style.display='none';});
    var lock=document.documentElement.style.overflow;
    function close(){o.remove();document.removeEventListener('keydown',esc);window.removeEventListener('message',msg);document.documentElement.style.overflow=lock;if(opener&&opener.focus)opener.focus();}
    function esc(e){if(e.key==='Escape')close();}
    function msg(e){if(e.origin===ORIGIN&&e.source===f.contentWindow&&(e.data==='close_div'||(e.data&&e.data.planplate==='close')))close();}
    x.onclick=close;o.onclick=function(e){if(e.target===o)close();};
    document.addEventListener('keydown',esc);window.addEventListener('message',msg);
    box.appendChild(wait);box.appendChild(f);box.appendChild(x);o.appendChild(box);document.body.appendChild(o);
    document.documentElement.style.overflow='hidden';
    x.focus();
  }
  function bind(root){
    (root||document).querySelectorAll('[data-planplate-open]').forEach(function(h){
      if(h.__ppBound)return;h.__ppBound=true;
      h.addEventListener('click',function(e){e.preventDefault();open();});
    });
  }
  var hooks=document.querySelectorAll('[data-planplate-open]').length;
  var wantButton=OPT.button==='none'?false:(OPT.button==='show'||!hooks);
  if(wantButton&&me&&me.parentNode){
    css();
    var b=document.createElement('button');b.type='button';
    b.className='pp-reserve pp-'+(OPT.style||'ink')+(OPT.shape==='rounded'?' pp-rounded':'')+(OPT.size&&OPT.size!=='md'?' pp-'+OPT.size:'');
    b.innerHTML='<span class="pp-reserve-mark">'+MARK+'</span><span class="pp-reserve-text"></span>';
    b.lastChild.textContent=LABEL;
    b.onclick=open;me.parentNode.insertBefore(b,me);
  }
  bind();
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){bind();});
  window.PlanPlate=window.PlanPlate||{};window.PlanPlate.open=open;
})();
"""


@anvil.server.http_endpoint("/embed.js")
def embed_js(r=None, label=None, style=None, shape=None, size=None, lang=None, button=None, **kw):
    slug = str(r or "").strip().lower()
    lang = lang if lang in B.LANGS else ""
    rest = _find(slug)
    if not lang and rest is not None:
        lang = B.language(rest)
    opt = {"style": style if style in ("ink", "brass", "light", "outline") else "ink",
           "shape": "rounded" if shape == "rounded" else "pill", "size": size if size in ("sm", "md", "lg") else "md",
           "lang": lang if lang and (rest is None or lang in B.languages(rest)) else "",
           "button": button if button in ("none", "show") else ""}
    text = str(label or "").strip()[:40] or EMBED_LABELS.get(lang or "en", EMBED_LABELS["en"])
    body = (EMBED_JS.replace("__ORIGIN__", json.dumps(anvil.server.get_app_origin())).replace("__SLUG__", json.dumps(slug))
            .replace("__LABEL__", json.dumps(text)).replace("__OPT__", json.dumps(opt))
            .replace("__CLOSE__", json.dumps(EMBED_CLOSE.get(lang or "en", "Close"))))
    return anvil.server.HttpResponse(200, body, headers={"Content-Type": "application/javascript; charset=utf-8",
                                                         "Cache-Control": "max-age=300"})
