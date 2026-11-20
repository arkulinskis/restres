# Remind — Server Module. The no-show shield (2026-11-20).
#   Reminders go from the restaurant's OWN phone or email: the host taps WhatsApp, SMS or Email on a list and the
#   message opens pre-written in the guest's language, with their private link (#r/<token>). PlanPlate sends nothing
#   itself (no SMS fees; the guest sees a number they know). On that page the guest taps "Yes, we're coming"
#   (Public.confirm_coming) or cancels.
#   What went out and what the guest answered are lines in the booking's history (kind "remind" / "confirm", read
#   with Booking.history_flags), so this needs no new column.
#   The message helpers here (dates, party sizes, phone numbers for wa.me) are shared with Waitlist.py.
#   Staff can do all of it (they run the room); every callable checks the role with Portal._rest.
import re
from datetime import timedelta
from urllib.parse import quote

import anvil.server
from anvil.tables import app_tables

from . import Booking as B
from .Portal import _child, _rest

CHANNELS = {"whatsapp": "WhatsApp", "sms": "SMS", "email": "Email", "copy": "Copied"}
TEXT = {
    "en": {"msg": "Hello {n}, see you {when} at {t} at {r} ({p}). Tap to confirm, or cancel if plans changed: {link}",
           "subject": "Your table at {r} {when}",
           "today": "today", "tomorrow": "tomorrow", "on": "on {date}",
           "one": "{n} guest", "many": "{n} guests"},
    "fr": {"msg": "Bonjour {n}, nous vous attendons {when} à {t} chez {r} ({p}). Touchez le lien pour confirmer, "
                  "ou pour annuler si vos plans ont changé : {link}",
           "subject": "Votre table chez {r} {when}",
           "today": "aujourd'hui", "tomorrow": "demain", "on": "le {date}",
           "one": "{n} personne", "many": "{n} personnes"},
    "lv": {"msg": "Labdien, {n}! Gaidīsim jūs {when} plkst. {t} restorānā {r} ({p}). Lūdzu, apstipriniet ierašanos "
                  "vai atceliet rezervāciju, ja plāni mainījušies: {link}",
           "subject": "Jūsu galdiņš restorānā {r} {when}",
           "today": "šodien", "tomorrow": "rīt", "on": "{date}",
           "one": "{n} viesis", "many": "{n} viesi"},
}
# Latvian says "on Friday, 21 November" with its own forms: piektdien, 21. novembrī.
LV_ON_DAY = ["pirmdien", "otrdien", "trešdien", "ceturtdien", "piektdien", "sestdien", "svētdien"]
LV_IN_MONTH = ["janvārī", "februārī", "martā", "aprīlī", "maijā", "jūnijā", "jūlijā", "augustā", "septembrī", "oktobrī",
               "novembrī", "decembrī"]

# Country calling codes for numbers typed without one (wa.me needs the full international number). The restaurant's
# own phone (+371 ...) decides first, then its time zone.
CC_BY_TZ = {"Europe/Riga": "371", "Europe/Tallinn": "372", "Europe/Vilnius": "370", "Europe/Helsinki": "358",
            "Europe/Stockholm": "46", "Europe/Oslo": "47", "Europe/Copenhagen": "45", "Europe/Warsaw": "48",
            "Europe/Berlin": "49", "Europe/Paris": "33", "Europe/Monaco": "377", "Europe/Brussels": "32",
            "Europe/Luxembourg": "352", "Europe/Amsterdam": "31", "Europe/London": "44", "Europe/Dublin": "353",
            "Europe/Madrid": "34", "Europe/Lisbon": "351", "Europe/Rome": "39", "Europe/Zurich": "41",
            "Europe/Vienna": "43", "Europe/Prague": "420", "Europe/Bratislava": "421", "Europe/Budapest": "36",
            "Europe/Athens": "30", "Europe/Kyiv": "380", "Europe/Bucharest": "40", "Europe/Sofia": "359",
            "Europe/Istanbul": "90", "Asia/Dubai": "971", "Asia/Tokyo": "81", "Asia/Singapore": "65",
            "Australia/Sydney": "61", "Australia/Melbourne": "61", "Pacific/Auckland": "64", "America/Mexico_City": "52"}
NANP = ("America/Toronto", "America/Montreal", "America/New_York", "America/Chicago", "America/Denver", "America/Phoenix",
        "America/Los_Angeles", "America/Vancouver", "America/Edmonton", "America/Winnipeg", "America/Halifax",
        "America/St_Johns", "America/Regina", "America/Detroit", "America/Anchorage", "Pacific/Honolulu")
KNOWN_CC = set(CC_BY_TZ.values()) | {"1"}


# ---------------------------------------------------------------- message helpers (also used by Waitlist.py)
def lang_of(lang):
    return lang if lang in TEXT else "en"


def when_text(d, today, lang):
    """ "tomorrow" / "demain" / "rīt", or "on Friday 21 November" in the guest's language."""
    t = TEXT[lang_of(lang)]
    if d == today:
        return t["today"]
    if d == today + timedelta(days=1):
        return t["tomorrow"]
    if lang_of(lang) == "lv":
        date = "%s, %d. %s" % (LV_ON_DAY[d.weekday()], d.day, LV_IN_MONTH[d.month - 1])
    else:
        from . import Notify
        date = Notify.fmt_date(d, lang_of(lang))
    return t["on"].replace("{date}", date)


def party_text(n, lang):
    t = TEXT[lang_of(lang)]
    n = int(n or 0)
    one = n % 10 == 1 and n % 100 != 11 if lang_of(lang) == "lv" else n == 1
    return (t["one"] if one else t["many"]).replace("{n}", str(n))


def time_text(minutes, lang):
    """19:30, or 19h30 in French."""
    s = B.hm(minutes)
    return s.replace(":", "h") if lang_of(lang) == "fr" else s


def fill(template, **values):
    for k, v in values.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def _country_code(r):
    own = re.sub(r"\D", "", str(r["phone"] or "")) if str(r["phone"] or "").strip().startswith("+") else ""
    for n in (3, 2, 1):
        if own[:n] in KNOWN_CC:
            return own[:n]
    tz = r["timezone"] or ""
    return "1" if tz in NANP else CC_BY_TZ.get(tz, "")


def wa_number(phone, r):
    """The guest's number as wa.me wants it: country code + number, digits only ("" when there is no number)."""
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 6:
        return ""
    if raw.startswith("+"):
        return digits
    if digits.startswith("00"):
        return digits[2:]
    cc = _country_code(r)
    if not cc:
        return digits
    if cc == "1" and len(digits) == 11 and digits.startswith("1"):
        return digits
    if digits.startswith(cc) and len(digits) >= len(cc) + 8:  # typed with the code but without the +
        return digits
    return cc + (digits[1:] if digits.startswith("0") else digits)


def dial(phone):
    """For tel: and sms: links: the number as typed, digits only (+ kept)."""
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    return ("+" if raw.startswith("+") else "") + digits if len(digits) >= 6 else ""


def links(r, phone, email, text, subject):
    """WhatsApp, SMS, email and phone links that open the restaurant's own apps with the message written."""
    wa, tel = wa_number(phone, r), dial(phone)
    body = quote(text, safe="")
    return {"wa": "https://wa.me/%s?text=%s" % (wa, body) if wa else "",
            "sms": "sms:%s?&body=%s" % (tel, body) if tel else "",
            "mail": ("mailto:%s?subject=%s&body=%s" % (quote(email, safe="@"), quote(subject, safe=""), body)) if email else "",
            "tel": "tel:" + tel if tel else ""}


def guest_link(res):
    from . import Notify
    return "%s/#r/%s" % (Notify.origin(), res["token"])


# ---------------------------------------------------------------- which day, which bookings
def next_day(ctx, today):
    """The day reminders are for: tomorrow, or the next day the restaurant opens (within two weeks)."""
    for k in range(1, 15):
        d = today + timedelta(days=k)
        if B.day_hours(ctx, d)[0]:
            return d
    return today + timedelta(days=1)


def day_word(d, today):
    """For the staff's buttons: "tomorrow", "today", "Friday", or "Fri 28 Nov" further ahead."""
    if d == today:
        return "today"
    if d == today + timedelta(days=1):
        return "tomorrow"
    if (d - today).days < 7:
        return B.DAY_NAMES[d.weekday()]
    from .Guests import MONTHS3
    return "%s %d %s" % (B.DAY_NAMES[d.weekday()][:3], d.day, MONTHS3[d.month - 1])


def title_for(word):
    """ "Remind tomorrow's guests", "Remind Friday's guests", "Remind the guests of Fri 28 Nov"."""
    if word in ("today", "tomorrow") or word in B.DAY_NAMES:
        return "Remind %s's guests" % word
    return "Remind the guests of %s" % word


def _rows(r, d, now):
    """Bookings worth reminding on date d: confirmed ones (requests still wait for approval), not started yet."""
    rows = [x for x in app_tables.reservations.search(restaurant=r, date=d) if x["status"] == "confirmed"]
    if d == now.date():
        rows = [x for x in rows if int(x["start_min"] or 0) > now.hour * 60 + now.minute]
    return sorted(rows, key=lambda x: (int(x["start_min"] or 0), B._created_key(x)))


def message(r, res, today):
    lang = lang_of(res["language"] or B.language(r))
    t = TEXT[lang]
    when = when_text(res["date"], today, lang)
    text = fill(t["msg"], n=(res["name"] or "").split(" ")[0] or res["name"] or "", when=when,
                t=time_text(int(res["start_min"] or 0), lang), r=r["name"] or "", p=party_text(res["party"], lang),
                link=guest_link(res))
    return text, fill(t["subject"], r=r["name"] or "", when=when), lang


def item(r, res, today):
    text, subject, lang = message(r, res, today)
    flags = B.history_flags(res)
    out = {"id": res.get_id(), "name": res["name"] or "", "time": B.hm(int(res["start_min"] or 0)), "party": int(res["party"] or 0),
           "phone": res["phone"] or "", "email": res["email"] or "", "language": lang, "message": text, "subject": subject,
           "reminded": flags["reminded"], "coming": flags["coming"]}
    out.update(links(r, res["phone"], res["email"] or "", text, subject))
    return out


def summary(r, ctx, now):
    """Today's "Remind tomorrow's guests (12)" button: the day, how many bookings, reminded, coming."""
    d = next_day(ctx, now.date())
    rows = _rows(r, d, now)
    flags = [B.history_flags(x) for x in rows]
    reminded = len([f for f in flags if f["reminded"]])
    word = day_word(d, now.date())
    return {"date": d.isoformat(), "word": word, "title": title_for(word), "bookings": len(rows), "reminded": reminded,
            "left": len(rows) - reminded, "coming": len([f for f in flags if f["coming"]])}


# ---------------------------------------------------------------- callables
@anvil.server.callable(require_user=True)
def get_reminders(rid, day=None):
    """The reminder list for a day (default: tomorrow, or the next open day): every confirmed booking with its message
    in the guest's language, WhatsApp / SMS / email links, and whether it was reminded or the guest said they're coming."""
    r = _rest(rid)
    now = B.local_now(r)
    today = now.date()
    if day:
        try:
            d = B.parse_date(day)
        except ValueError:
            return {"ok": False, "error": "Pick a day."}
    else:
        d = next_day(B.Ctx(r), today)
    if d < today:
        return {"ok": False, "error": "That day is over. Reminders are for bookings still to come."}
    rows = _rows(r, d, now)
    items = [item(r, x, today) for x in rows]
    waiting = len([x for x in app_tables.reservations.search(restaurant=r, date=d) if x["status"] == "pending"])
    word = day_word(d, today)
    return {"ok": True, "date": d.isoformat(), "today": today.isoformat(), "word": word,
            "title": title_for(word),
            "items": items, "reminded": len([i for i in items if i["reminded"]]), "coming": len([i for i in items if i["coming"]]),
            "pending": waiting}


@anvil.server.callable(require_user=True)
def mark_reminded(rid, res_id, channel):
    """The host tapped a reminder link (or copied the message): note it on the booking, so every screen shows
    "Reminded 18:02 · WhatsApp"."""
    r = _rest(rid)
    if channel not in CHANNELS:
        return {"ok": False, "error": "Unknown channel."}
    res = _child(app_tables.reservations, r, res_id)
    what = "Reminder copied, to send by hand." if channel == "copy" else "Reminder sent by %s." % CHANNELS[channel]
    res["updated"] = B.now_utc()
    B.add_history(res, "staff", what, kind="remind", channel=channel)
    return {"ok": True, "reminded": B.history_flags(res)["reminded"]}
