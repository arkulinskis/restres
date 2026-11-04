# GuestNews — Server Module. PlanPlate's own agreement with the guests who book through its form (EU rules, Nov 2026).
#   Required tick (no tick, no booking): PlanPlate, the booking service, keeps a record of the booking and emails the
#     guest about it. Stored on the reservation: pp_consent, pp_consent_text (the exact words), pp_consent_at.
#   Optional tick, never pre-ticked: PlanPlate may email news and offers. Stored in pp_contacts (one row per email
#     address, PlanPlate's own list, kept apart from the restaurants' data) and reservations.pp_news.
#     Guests stop it on their booking page (#r/<token>) or with the stop link (/_/api/news/stop/<token>);
#     a stopped address keeps its row (subscribed False + stopped_at) so it is never emailed again.
#   Admin -> News list: counts and a CSV of the people who said yes (with each one's stop link).
# The texts below are the ones the form shows (sent to the browser by get_booking_form / get_reservation), so
# what is stored is exactly what the guest saw.
import csv
import io

import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

from . import Booking as B
from . import common as C

TEXT = {
    "en": {
        "consent": "I agree that PlanPlate, the booking service this restaurant uses, keeps a record of my booking and emails me about it.",
        "news": "PlanPlate may also email me now and then with news and offers. Optional: I can stop any time.",
        "manage": "Send me PlanPlate news and offers by email (I can stop any time).",
        "policy": "PlanPlate's Privacy Policy",
        "need": "Please tick the two required boxes: we need them to take your reservation.",
        "saved": "Saved",
        "stop_title": "Stop PlanPlate news",
        "stop_q": "Stop PlanPlate's news and offers emails to {e}?",
        "stop_btn": "Stop the emails",
        "stopped": "Done. PlanPlate won't send news or offers to {e} any more. Emails about your reservations still arrive.",
        "unknown": "This link doesn't work any more. If you still get PlanPlate news, reply to the email and we'll stop it.",
        "email_line": "You chose to get PlanPlate news and offers. Stop them any time: {u}",
    },
    "fr": {
        "consent": "J'accepte que PlanPlate, le service de réservation utilisé par ce restaurant, conserve une trace de ma réservation et m'écrive à son sujet.",
        "news": "PlanPlate peut aussi m'envoyer de temps en temps des nouvelles et des offres par e-mail. Facultatif : je peux arrêter à tout moment.",
        "manage": "M'envoyer les nouvelles et les offres de PlanPlate par e-mail (je peux arrêter à tout moment).",
        "policy": "Politique de confidentialité de PlanPlate",
        "need": "Veuillez cocher les deux cases obligatoires : elles sont nécessaires pour prendre votre réservation.",
        "saved": "Enregistré",
        "stop_title": "Arrêter les nouvelles de PlanPlate",
        "stop_q": "Arrêter les e-mails de nouvelles et d'offres de PlanPlate envoyés à {e} ?",
        "stop_btn": "Arrêter les e-mails",
        "stopped": "C'est fait. PlanPlate n'enverra plus de nouvelles ni d'offres à {e}. Les e-mails sur vos réservations continuent d'arriver.",
        "unknown": "Ce lien ne fonctionne plus. Si vous recevez encore des nouvelles de PlanPlate, répondez à l'e-mail et nous les arrêterons.",
        "email_line": "Vous avez choisi de recevoir les nouvelles et les offres de PlanPlate. Pour les arrêter à tout moment : {u}",
    },
    "lv": {
        "consent": "Piekrītu, ka PlanPlate – rezervāciju serviss, ko izmanto šis restorāns, – saglabā manas rezervācijas datus un sūta man e-pastus par to.",
        "news": "PlanPlate var man laiku pa laikam sūtīt jaunumus un piedāvājumus pa e-pastu. Nav obligāti: varu atteikties jebkurā laikā.",
        "manage": "Sūtīt man PlanPlate jaunumus un piedāvājumus pa e-pastu (varu atteikties jebkurā laikā).",
        "policy": "PlanPlate privātuma politika",
        "need": "Lūdzu, atzīmējiet abas obligātās rūtiņas: tās ir nepieciešamas, lai pieņemtu jūsu rezervāciju.",
        "saved": "Saglabāts",
        "stop_title": "Atteikties no PlanPlate jaunumiem",
        "stop_q": "Pārtraukt PlanPlate jaunumu un piedāvājumu e-pastus uz {e}?",
        "stop_btn": "Pārtraukt e-pastus",
        "stopped": "Gatavs. PlanPlate vairs nesūtīs jaunumus un piedāvājumus uz {e}. E-pasti par jūsu rezervācijām pienāks kā līdz šim.",
        "unknown": "Šī saite vairs nedarbojas. Ja joprojām saņemat PlanPlate jaunumus, atbildiet uz e-pastu, un mēs tos pārtrauksim.",
        "email_line": "Jūs izvēlējāties saņemt PlanPlate jaunumus un piedāvājumus. Atteikties var jebkurā laikā: {u}",
    },
}
FORM_KEYS = ("consent", "news", "manage", "policy", "need", "saved")


def t(lang):
    return TEXT.get(lang) or TEXT["en"]


def texts():
    """The form's texts in every language, for the browser."""
    return {lang: {k: v[k] for k in FORM_KEYS} for lang, v in TEXT.items()}


def _key(email):
    return str(email or "").strip().lower()


def contact(email):
    key = _key(email)
    return app_tables.pp_contacts.get(email=key) if key else None


def subscribed(email):
    row = contact(email)
    return bool(row is not None and row["subscribed"])


def stop_url(row):
    try:
        base = anvil.server.get_api_origin()
    except Exception:
        base = ""
    return base + "/news/stop/" + row["token"]


@tables.in_transaction
def set_news(email, name, lang, restaurant_name, on, consent_text):
    """Say yes (on) or stop (not on) for one email address. Returns the pp_contacts row (or None if there was none to stop)."""
    key, now = _key(email), C.now()
    row = app_tables.pp_contacts.get(email=key)
    if not on:
        if row is not None and row["subscribed"]:
            row.update(subscribed=False, stopped_at=now, updated=now)
        return row
    name, place = str(name or "")[:100], str(restaurant_name or "")[:200]
    if row is None:
        row = app_tables.pp_contacts.add_row(email=key, token=B.new_token(), name=name, language=lang, restaurant_name=place,
                                             subscribed=True, consent_text=consent_text, consent_at=now, stopped_at=None, updated=now)
    else:
        row.update(name=name, language=lang, restaurant_name=place, subscribed=True, consent_text=consent_text, consent_at=now,
                   stopped_at=None, updated=now)
    return row


def on_booking(res, news):
    """After an online booking: add the guest to PlanPlate's news list if they ticked the optional box."""
    if news:
        lang = res["language"] or "en"
        set_news(res["email"], res["name"], lang, res["restaurant"]["name"], True, t(lang)["news"])


def email_line(res):
    """The stop line for a guest email, or "" when this address isn't on the news list."""
    row = contact(res["email"])
    if row is None or not row["subscribed"]:
        return ""
    return t(res["language"] or "en")["email_line"].format(u=stop_url(row))


# ---------------------------------------------------------------- the guest switches it on or off
@anvil.server.callable
def set_guest_news(token, on, lang=None):
    """From the guest's reservation page (#r/<token>): the token is the key, as for every guest action."""
    from . import Public
    res = Public._by_token(token)
    if res is None:
        return {"ok": False, "error": "Reservation not found."}
    lang = lang if lang in TEXT else (res["language"] or "en")
    on = bool(on)
    set_news(res["email"], res["name"], lang, res["restaurant"]["name"], on, t(lang)["manage"])
    res["pp_news"] = on
    B.add_history(res, "guest", "PlanPlate news: %s." % ("yes" if on else "stopped"))
    return {"ok": True, "on": on}


# ---------------------------------------------------------------- the stop link in emails
def _html(title, body, lang):
    return ('<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>%s</title></head>'
            '<body style="margin:0;background:#f6f3ee;font:16px/1.6 Georgia,serif;color:#1d1b18">'
            '<div style="max-width:520px;margin:40px auto;padding:32px 28px;background:#fffdf9;border:1px solid #e4ded4;border-radius:12px">'
            '<h1 style="margin:0 0 16px;font-weight:normal;font-size:26px">%s</h1>%s'
            '<p style="margin:24px 0 0;font:12px Arial,sans-serif;color:#a19a8f">PlanPlate</p></div></body></html>') % (
        lang, _esc(title), _esc(title), body)


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _page(html):
    return anvil.server.HttpResponse(200, html, headers={"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"})


@anvil.server.http_endpoint("/news/stop/:code", methods=["GET", "POST"])
def news_stop(code, **kw):
    """GET shows a Stop button (so mail scanners that open links don't unsubscribe anyone); POST stops the emails."""
    code = str(code or "")
    row = app_tables.pp_contacts.get(token=code) if len(code) == 32 else None
    if row is None:
        tx = t("en")
        return _page(_html(tx["stop_title"], "<p>%s</p>" % _esc(tx["unknown"]), "en"))
    lang = row["language"] or "en"
    tx = t(lang)
    method = "GET"
    try:
        method = anvil.server.request.method or "GET"
    except Exception:
        pass
    if method.upper() == "POST" or not row["subscribed"]:
        set_news(row["email"], row["name"], lang, row["restaurant_name"], False, "")
        return _page(_html(tx["stop_title"], "<p>%s</p>" % _esc(tx["stopped"].format(e=row["email"])), lang))
    form = ('<p>%s</p><form method="post"><button type="submit" style="font:15px Arial,sans-serif;padding:13px 24px;border-radius:999px;'
            'border:0;background:#1d1b18;color:#faf8f4;cursor:pointer">%s</button></form>') % (
        _esc(tx["stop_q"].format(e=row["email"])), _esc(tx["stop_btn"]))
    return _page(_html(tx["stop_title"], form, lang))


# ---------------------------------------------------------------- Admin -> News list
def _row(c):
    return {"email": c["email"], "name": c["name"] or "", "language": c["language"] or "", "restaurant": c["restaurant_name"] or "",
            "since": C.iso(c["consent_at"]), "stopped": C.iso(c["stopped_at"]), "subscribed": bool(c["subscribed"])}


@anvil.server.callable(require_user=True)
def admin_news():
    C.require_admin()
    rows = list(app_tables.pp_contacts.search())
    yes = sorted((c for c in rows if c["subscribed"]), key=lambda c: c["consent_at"] or c["updated"], reverse=True)
    return {"subscribed": len(yes), "stopped": len(rows) - len(yes), "recent": [_row(c) for c in yes[:50]]}


@anvil.server.callable(require_user=True)
def admin_news_csv():
    """Everyone who said yes, as a CSV (with what they agreed to, when, and their own stop link for each email you send)."""
    C.require_admin()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["email", "name", "language", "booked at", "agreed on (UTC)", "what they agreed to", "stop link"])
    for c in app_tables.pp_contacts.search(subscribed=True):
        w.writerow([c["email"], c["name"] or "", c["language"] or "", c["restaurant_name"] or "",
                    C.iso(c["consent_at"]) or "", c["consent_text"] or "", stop_url(c)])
    data = ("﻿" + out.getvalue()).encode("utf-8")  # the BOM makes Excel read accents right
    return anvil.BlobMedia("text/csv", data, name="planplate-news-list-%s.csv" % C.now().date().isoformat())
