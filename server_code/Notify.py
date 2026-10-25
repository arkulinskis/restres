# Notify — Server Module. Emails about reservations, sent with Anvil's Email service.
#   guests: confirmed / request received / declined / cancelled / changed, in the booking's language,
#           with the restaurant's own message (Settings → Emails) and the private link to their reservation
#   staff:  "approval needed" the moment a booking goes pending (to the restaurant's alert address, or the owner)
#   team:   an invitation when someone is given access
# Every caller wraps these in try/except: a failed email must never break a booking.
import anvil.server

from . import Booking as B

TEXT = {
    "en": {
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "date_fmt": "{wd} {d} {m}",
        "s_confirmed": "Your table at {r} is confirmed", "s_pending": "We've received your request – {r}",
        "s_declined": "About your reservation request at {r}", "s_cancelled": "Your reservation at {r} is cancelled",
        "s_changed": "Your reservation at {r} has been updated",
        "b_confirmed": "We look forward to welcoming you.",
        "b_pending": "Thank you for your request. The restaurant will confirm it shortly, and we'll email you as soon as they do.",
        "b_declined": "Unfortunately the restaurant can't accept your request for this time. Please choose another time, or call them.",
        "b_cancelled": "Your reservation has been cancelled. We hope to see you another time.",
        "b_changed": "Your reservation has been updated. Here are the details.",
        "hello": "Dear {n},", "date": "Date", "time": "Time", "guests": "Guests",
        "manage": "View, change or cancel your reservation", "private": "This link is private: anyone who has it can change your reservation.",
        "book_again": "Book another time",
    },
    "fr": {
        "days": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
        "date_fmt": "{wd} {d} {m}",
        "s_confirmed": "Votre table chez {r} est confirmée", "s_pending": "Nous avons bien reçu votre demande – {r}",
        "s_declined": "Votre demande de réservation chez {r}", "s_cancelled": "Votre réservation chez {r} est annulée",
        "s_changed": "Votre réservation chez {r} a été modifiée",
        "b_confirmed": "Nous nous réjouissons de vous accueillir.",
        "b_pending": "Merci pour votre demande. Le restaurant va la confirmer sous peu ; nous vous écrirons dès que ce sera fait.",
        "b_declined": "Malheureusement, le restaurant ne peut pas accepter votre demande pour cet horaire. Choisissez un autre horaire ou appelez-le.",
        "b_cancelled": "Votre réservation a été annulée. Au plaisir de vous recevoir une autre fois.",
        "b_changed": "Votre réservation a été modifiée. Voici les détails.",
        "hello": "Bonjour {n},", "date": "Date", "time": "Heure", "guests": "Personnes",
        "manage": "Voir, modifier ou annuler votre réservation", "private": "Ce lien est personnel : toute personne qui l'a peut modifier votre réservation.",
        "book_again": "Réserver un autre horaire",
    },
    "lv": {
        "days": ["pirmdiena", "otrdiena", "trešdiena", "ceturtdiena", "piektdiena", "sestdiena", "svētdiena"],
        "months": ["janvāris", "februāris", "marts", "aprīlis", "maijs", "jūnijs", "jūlijs", "augusts", "septembris", "oktobris", "novembris", "decembris"],
        "date_fmt": "{wd}, {d}. {m}",
        "s_confirmed": "Jūsu galdiņš restorānā {r} ir apstiprināts", "s_pending": "Esam saņēmuši jūsu pieprasījumu – {r}",
        "s_declined": "Par jūsu rezervācijas pieprasījumu restorānā {r}", "s_cancelled": "Jūsu rezervācija restorānā {r} ir atcelta",
        "s_changed": "Jūsu rezervācija restorānā {r} ir mainīta",
        "b_confirmed": "Gaidīsim jūs!",
        "b_pending": "Paldies par pieprasījumu. Restorāns to drīz apstiprinās, un mēs jums uzrakstīsim, tiklīdz tas notiks.",
        "b_declined": "Diemžēl restorāns šajā laikā nevar pieņemt jūsu pieprasījumu. Lūdzu, izvēlieties citu laiku vai piezvaniet.",
        "b_cancelled": "Jūsu rezervācija ir atcelta. Ceram jūs redzēt citreiz.",
        "b_changed": "Jūsu rezervācija ir mainīta. Lūk, informācija.",
        "hello": "Labdien, {n}!", "date": "Datums", "time": "Laiks", "guests": "Viesi",
        "manage": "Skatīt, mainīt vai atcelt rezervāciju", "private": "Šī saite ir personīga: ikviens, kam tā ir, var mainīt jūsu rezervāciju.",
        "book_again": "Rezervēt citu laiku",
    },
}


def _t(lang):
    return TEXT.get(lang) or TEXT["en"]


def fmt_date(d, lang):
    t = _t(lang)
    return t["date_fmt"].format(wd=t["days"][d.weekday()], d=d.day, m=t["months"][d.month - 1])


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def origin():
    try:
        return anvil.server.get_app_origin()
    except Exception:
        return ""


def _send(to, subject, text, html, r=None):
    import anvil.email
    kw = {"to": to, "subject": subject, "text": text, "html": html, "from_name": (r["name"] if r is not None else "PlanPlate")}
    if r is not None and r["email"]:
        kw["reply_to"] = r["email"]
    anvil.email.send(**kw)


def _page(title, paragraphs, facts=None, button=None, footer=""):
    """A plain, elegant HTML email (inline styles only, as mail clients need)."""
    rows = "".join('<p style="margin:0 0 14px;font:15px/1.6 Georgia,serif;color:#1d1b18">%s</p>' % p for p in paragraphs)
    fx = ""
    if facts:
        cells = "".join('<td style="padding:14px 8px;text-align:center;border-top:1px solid #e4ded4;border-bottom:1px solid #e4ded4">'
                        '<div style="font:20px Georgia,serif;color:#1d1b18">%s</div><div style="font:11px Arial,sans-serif;letter-spacing:2px;'
                        'text-transform:uppercase;color:#6f6a62;margin-top:4px">%s</div></td>' % (_esc(v), _esc(k)) for k, v in facts)
        fx = '<table role="presentation" width="100%%" cellspacing="0" style="margin:8px 0 22px"><tr>%s</tr></table>' % cells
    btn = ""
    if button:
        btn = ('<p style="margin:6px 0 18px"><a href="%s" style="display:inline-block;background:#1d1b18;color:#faf8f4;text-decoration:none;'
               'font:14px Arial,sans-serif;padding:13px 24px;border-radius:999px">%s</a></p>' % (_esc(button[1]), _esc(button[0])))
    return ('<div style="background:#f6f3ee;padding:32px 12px"><div style="max-width:520px;margin:0 auto;background:#fffdf9;'
            'border:1px solid #e4ded4;border-radius:12px;padding:32px 30px">'
            '<h1 style="margin:0 0 18px;font:28px/1.2 Georgia,serif;font-weight:normal;color:#1d1b18">%s</h1>%s%s%s'
            '<p style="margin:18px 0 0;font:12px/1.5 Arial,sans-serif;color:#a19a8f">%s</p></div></div>') % (_esc(title), rows, fx, btn, footer)


def guest_email(res, event):
    """(subject, text, html) for the guest, or None when there is nothing to send."""
    r = res["restaurant"]
    lang = res["language"] or B.language(r)
    t = _t(lang)
    key = {"created": res["status"], "confirmed": "confirmed", "declined": "declined", "cancelled": "cancelled", "changed": "changed"}.get(event)
    if key not in ("confirmed", "pending", "declined", "cancelled", "changed"):
        return None
    if event == "changed" and res["status"] == "pending":
        key = "pending"
    subject = t["s_" + key].format(r=r["name"])
    custom = {"confirmed": r["msg_confirmed"], "pending": r["msg_pending"], "declined": r["msg_declined"]}.get(key) or ""
    paras = [_esc(t["hello"].format(n=res["name"])), _esc(t["b_" + key])] + ([_esc(custom).replace("\n", "<br>")] if custom else [])
    d, start = res["date"], int(res["start_min"] or 0)
    facts = [(t["date"], fmt_date(d, lang)), (t["time"], B.hm(start)), (t["guests"], str(int(res["party"] or 0)))]
    link = origin() + "/#r/" + res["token"]
    if key in ("declined", "cancelled"):
        button, footer = (t["book_again"], origin() + "/#book/" + r["slug"]), ""
    else:
        button, footer = (t["manage"], link), t["private"]
    contact = " · ".join(x for x in (r["address"], r["phone"]) if x)
    html = _page(r["name"], paras, facts, button, _esc(footer) + ("<br>" if footer and contact else "") + _esc(contact))
    text = "\n\n".join([t["hello"].format(n=res["name"]), t["b_" + key]] + ([custom] if custom else []) +
                       ["%s: %s\n%s: %s\n%s: %s" % (facts[0] + facts[1] + facts[2]), "%s:\n%s" % button, footer, contact])
    return subject, text.strip(), html


def staff_alert(res):
    """(to, subject, text, html) telling the restaurant a booking waits for approval."""
    r = res["restaurant"]
    to = r["notify_email"] or (r["owner"]["email"] if r["owner"] else None)
    if not to:
        return None
    when = "%s at %s" % (fmt_date(res["date"], "en"), B.hm(res["start_min"]))
    subject = "Approval needed: %s, %d guests, %s" % (res["name"], int(res["party"] or 0), when)
    paras = ["A booking at <strong>%s</strong> is waiting for your decision." % _esc(r["name"]),
             _esc(res["review_reason"] or "It needs a manager's approval."),
             "%s · %s · %s" % (_esc(res["name"]), _esc(res["phone"]), _esc(res["email"]))] + (
        ["“%s”" % _esc(res["notes"])] if res["notes"] else [])
    html = _page("Approval needed", paras, [("Date", fmt_date(res["date"], "en")), ("Time", B.hm(res["start_min"])),
                                            ("Guests", str(int(res["party"] or 0)))],
                 ("Open PlanPlate to approve or decline", origin() + "/"), "Sent by PlanPlate because this booking needs approval.")
    text = "A booking at %s is waiting for your decision.\n\n%s\n\n%s, %s guests, %s\n%s · %s\n%s\n\nOpen PlanPlate: %s/" % (
        r["name"], res["review_reason"] or "", res["name"], int(res["party"] or 0), when, res["phone"] or "", res["email"] or "",
        res["notes"] or "", origin())
    return to, subject, text, html


def reservation_event(res, event, before=None):
    """event: created | changed | cancelled | confirmed | declined (from Public and Portal)."""
    r = res["restaurant"]
    sent = []
    if r["emails_on"] is not False and res["email"]:
        msg = guest_email(res, event)
        if msg and not (event == "confirmed" and before == "confirmed"):
            _send(res["email"], msg[0], msg[1], msg[2], r)
            sent.append("guest")
    became_pending = res["status"] == "pending" and (event == "created" or before != "pending")
    if became_pending:
        alert = staff_alert(res)
        if alert:
            _send(alert[0], alert[1], alert[2], alert[3])
            sent.append("staff")
    return sent


def invite(r, email, role, inviter):
    who = (inviter["display_name"] or inviter["email"]) if inviter else "A colleague"
    role_text = "a manager" if role == "manager" else "a member of staff"
    subject = "%s gave you access to %s on PlanPlate" % (who, r["name"])
    paras = ["%s added you to <strong>%s</strong> as %s." % (_esc(who), _esc(r["name"]), role_text),
             "Sign in, or create an account, with this email address (%s) and the restaurant appears in your list." % _esc(email)]
    html = _page("You're invited", paras, None, ("Open PlanPlate", origin() + "/"))
    text = "%s added you to %s as %s.\n\nSign in or create an account with %s at %s/" % (who, r["name"], role_text, email, origin())
    _send(email, subject, text, html)
