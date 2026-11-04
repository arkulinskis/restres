# Legacy — Server Module. Menu files (photos or PDFs of a menu, per language, like "Food" and "Drinks"), and the public
# addresses of the OLD PlanPlate apps (client.planplate.com, restaurant.planplate.com), so restaurant websites that
# embed the old code keep working once those domains point at this app:
#
#   /restaurant/<old id>[/<lang>[/<token>]]  the booking page (the old "Reserve" pop-up's iframe)  -> #book/<slug>[/<lang>]
#   /reserve/<old id>/<lang>      the PRINTED booking QR codes -> #book; on restaurant.* the owners' printable QR page
#   /menus/<old id>/<file>/<lang> (restaurant.*) the printable QR page of one menu file
#   /reservations/<old id>        (restaurant.*) the link in the old approval emails -> #reservations
#   /_/theme/planplate_client.js, planplate_client2.js  the old embed scripts, rewritten to call this app (theme/assets)
#   /_/api/v1/<old id>/<lang>     opening hours as an HTML list (the old <div restaurant="..."> widget)
#   /_/api/menus/<old id>/<lang>  links to the menu files in that language (the old <div menus="..."> widget);
#                                 with a menu file's id instead of <lang> (the old MENU QR codes) -> that file
#   /_/api/menu/<old id>/<file>   one menu file, shown in the browser
#   /_/api/gallery/<old id>       the gallery feed (Media.gallery_feed also finds restaurants by old id)
#
# The old id is the restaurant's UUID in the old apps (restaurants.legacy_id, set in Settings). Learned from the public
# pages of dilettante.lv and the old APIs' public answers (Nov 2026); photos there live on Cloudinary under
# restaurants/<old id>/, and Media.folder() uploads into the same folder when the old id is set.
import html
import json
import re
import uuid
from datetime import timedelta

import anvil.server
from anvil.tables import app_tables

from . import Booking as B
from . import Portal as P

LANG_WORDS = {"closed": {"en": "Closed", "fr": "Fermé", "lv": "Slēgts"}}
DAYS = {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "fr": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"],
        "lv": ["Pirmdiena", "Otrdiena", "Trešdiena", "Ceturtdiena", "Piektdiena", "Sestdiena", "Svētdiena"]}
UUID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")
MAX_FILE = 15 * 1048576
FILE_TYPES = ("application/pdf", "image/jpeg", "image/png", "image/webp")
CORS = {"Access-Control-Allow-Origin": "*"}


def by_ref(ref):
    """A restaurant by old id (UUID), booking-link slug or row id."""
    ref = str(ref or "").strip()
    if not ref:
        return None
    if UUID_RE.match(ref):
        r = app_tables.restaurants.get(legacy_id=ref.lower())
        if r is not None:
            return r
    from . import Media
    return Media.find_restaurant(ref)


def _lang(r, lang):
    return lang if lang in B.LANGS else B.language(r)


def _text(code, body, ctype="text/html; charset=utf-8"):
    return anvil.server.HttpResponse(code, body, headers=dict(CORS, **{"Content-Type": ctype, "Cache-Control": "max-age=60"}))


# ---------------------------------------------------------------- menu files (managers)
def _file_view(f, r):
    ref = r["legacy_id"] or r["slug"]
    return {"id": f.get_id(), "key": f["key"], "title": f["title"] or "", "language": f["language"] or "",
            "type": f["content_type"] or "", "name": f["file"].name if f["file"] is not None else "", "missing": f["file"] is None,
            "url": "%s/_/api/menu/%s/%s" % (anvil.server.get_app_origin(), ref, f["key"]), "position": int(f["position"] or 0)}


def files_of(r, lang=None):
    rows = sorted(app_tables.menu_files.search(restaurant=r), key=lambda f: (int(f["position"] or 0), B._created_key(f)))
    return [f for f in rows if not lang or not f["language"] or f["language"] == lang]


@anvil.server.callable(require_user=True)
def get_menu_files(rid):
    r = P._rest(rid, "manager")
    return {"ok": True, "files": [_file_view(f, r) for f in files_of(r)], "languages": list(B.LANGS)}


def _check_file(media):
    """The error for a menu file that can't be used, or None."""
    if media is None:
        return "Choose a PDF or a photo of the menu."
    if (media.content_type or "").lower() not in FILE_TYPES:
        return "Menus can be PDFs or photos (JPEG, PNG, WebP)."
    if len(media.get_bytes()) > MAX_FILE:
        return "That file is over 15 MB. Make it smaller first."
    return None


@anvil.server.callable(require_user=True)
def add_menu_file(rid, media, title, language=""):
    r = P._rest(rid, "manager")
    title = str(title or "").strip()[:60]
    if not title:
        return {"ok": False, "error": "Give the menu a name, like Food or Drinks."}
    err = _check_file(media)
    if err:
        return {"ok": False, "error": err}
    ctype = (media.content_type or "").lower()
    language = language if language in B.LANGS else ""
    app_tables.menu_files.add_row(restaurant=r, key=uuid.uuid4().hex, title=title, language=language, file=media,
                                  content_type=ctype, position=len(files_of(r)), created=B.now_utc())
    return get_menu_files(rid)


@anvil.server.callable(require_user=True)
def replace_menu_file(rid, fid, media):
    """Put a file into a menu file (one imported from the old PlanPlate arrives without its file). Keeps its id, so the
    old website links and QR codes to it work again."""
    r = P._rest(rid, "manager")
    f = P._child(app_tables.menu_files, r, fid)
    err = _check_file(media)
    if err:
        return {"ok": False, "error": err}
    f.update(file=media, content_type=(media.content_type or "").lower())
    return get_menu_files(rid)


@anvil.server.callable(require_user=True)
def delete_menu_file(rid, fid):
    r = P._rest(rid, "manager")
    P._child(app_tables.menu_files, r, fid).delete()
    return get_menu_files(rid)


def public_files(r, lang):
    return [{"title": f["title"] or "", "url": _file_view(f, r)["url"], "type": f["content_type"] or ""}
            for f in files_of(r, lang) if f["file"] is not None]


# ---------------------------------------------------------------- the old public addresses
def _go(target):
    return anvil.server.HttpResponse(302, "", headers={"Location": target})


def _book_target(ref, lang=""):
    r = by_ref(ref)
    if r is None:
        return "/"
    return "/#book/%s" % r["slug"] + ("/%s" % lang if lang in B.LANGS else "")


def _host():
    try:
        return str(anvil.server.request.headers.get("host") or "").lower()
    except Exception:
        return ""


@anvil.server.route("/restaurant/:ref")
def old_booking_page(ref, **kw):
    """The old booking page: send the guest to the new booking form (the old pop-up shows it in its iframe)."""
    return _go(_book_target(ref))


@anvil.server.route("/restaurant/:ref/:lang")
def old_booking_page_lang(ref, lang, **kw):
    """The old pop-up with a language (the old embed code: iframe_launcher="<id>/en")."""
    return _go(_book_target(ref, lang))


@anvil.server.route("/restaurant/:ref/:lang/:token")
def old_booking_page_staff(ref, lang, token, **kw):
    """The old staff link (booked without approval). Staff now add bookings in the portal; this opens the guest form."""
    return _go(_book_target(ref, lang))


@anvil.server.route("/reserve/:ref/:lang")
def old_reserve(ref, lang, **kw):
    """client.planplate.com/reserve/<id>/<lang>: what the PRINTED booking QR codes open -> the booking form.
    restaurant.planplate.com/reserve/<id>/<lang>: the owners' printable QR page."""
    if _host().startswith("restaurant."):
        r = by_ref(ref)
        if r is None:
            return _text(404, "Restaurant not found", "text/plain; charset=utf-8")
        lang = _lang(r, lang)
        url = anvil.server.get_app_origin() + _book_target(ref, lang)
        return _qr_page(r["name"], url, {"en": "Reserve today!", "fr": "Réservez dès aujourd'hui!", "lv": "Rezervē jau šodien!"}[lang], lang)
    return _go(_book_target(ref, lang))


@anvil.server.route("/menus/:ref/:key/:lang")
def old_menu_qr_page(ref, key, lang, **kw):
    """restaurant.planplate.com/menus/<id>/<menu file>/<lang>: the owners' printable QR page for one menu file."""
    r = by_ref(ref)
    f = _file_by_key(r, key)
    if r is None or f is None:
        return _text(404, "Not found", "text/plain; charset=utf-8")
    lang = _lang(r, lang)
    return _qr_page(r["name"], _file_view(f, r)["url"],
                    {"en": "Here is the menu QR code!", "fr": "Voici le code QR du menu !", "lv": "Šeit ir ēdienkartes QR kods!"}[lang], lang)


@anvil.server.route("/reservations/:ref")
def old_staff_list(ref, **kw):
    """restaurant.planplate.com/reservations/<id>: the link in the old approval emails -> the Reservations page."""
    r = by_ref(ref)
    return _go("/#reservations/%s" % r.get_id() if r is not None else "/#dashboard")


@anvil.server.route("/demo")
def old_demo(**kw):
    return _go("/#book/maison-lumiere")


def _qr_page(name, url, caption, lang):
    """A plain printable page: the restaurant's name, a big QR code and a caption (drawn in the browser)."""
    body = """<!doctype html><html lang="%(lang)s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(name)s</title><meta name="robots" content="noindex">
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcode-generator/1.4.4/qrcode.min.js"></script>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#fff;color:#222;font-family:Georgia,serif;text-align:center}
h1{font-weight:400;font-size:2.4rem;margin:0 0 18px}#q svg{width:min(70vw,360px);height:auto}p{font-size:1.6rem;margin:18px 0 0}
small{display:block;margin-top:10px;font:13px system-ui,sans-serif;color:#777;word-break:break-all}@media print{small{display:none}}</style></head>
<body><main><h1>%(name)s</h1><div id="q"></div><p>%(caption)s</p><small>%(url)s</small></main>
<script>var q=qrcode(0,'M');q.addData(%(js_url)s);q.make();document.getElementById('q').innerHTML=q.createSvgTag({cellSize:8,margin:2,scalable:true});</script>
</body></html>""" % {"lang": lang, "name": html.escape(name or "PlanPlate"), "caption": html.escape(caption), "url": html.escape(url),
                     "js_url": json.dumps(url)}
    return anvil.server.HttpResponse(200, body, headers={"Content-Type": "text/html; charset=utf-8"})


def _file_by_key(r, key):
    key = str(key or "")
    if r is None or not re.match(r"^[0-9a-fA-F-]{24,36}$", key):
        return None
    f = app_tables.menu_files.get(key=key)
    return f if f is not None and f["restaurant"] == r and f["file"] is not None else None


@anvil.server.http_endpoint("/v1/:ref/:lang")
def old_hours(ref, lang, **kw):
    """Opening hours as the old widget's HTML: the weekly hours, then the special days coming up."""
    r = by_ref(ref)
    if r is None:
        return _text(404, "Restaurant not found", "text/plain; charset=utf-8")
    lang = _lang(r, lang)
    ctx = B.Ctx(r)
    today = B.local_now(r).date()
    monday = today - timedelta(days=today.weekday())
    week = []
    for i in range(7):
        d = monday + timedelta(days=7 + i) if (monday + timedelta(days=i)) < today else monday + timedelta(days=i)
        iv, src = B.day_hours(ctx, d)
        if src.get("kind") == "special":  # a holiday this week: show the usual hours here, the holiday below
            iv, src = B.day_hours(ctx, d + timedelta(days=7))
        txt = ", ".join("%s-%s" % (a, b) for a, b in B.intervals_text(iv)) or LANG_WORDS["closed"][lang]
        week.append("<li><strong>%s:</strong> %s</li>" % (DAYS[lang][i], html.escape(txt)))
    special = []
    for s in sorted(app_tables.special_days.search(restaurant=r), key=lambda x: x["date"]):
        if s["date"] is None or s["date"] < today or s["date"] > today + timedelta(days=365):
            continue
        txt = LANG_WORDS["closed"][lang] if s["closed"] else ", ".join("%s-%s" % (a, b) for a, b in B.intervals_text(B.clean_intervals(s["hours"] or [])))
        special.append("<li><strong>%s:</strong> %s</li>" % (s["date"].isoformat(), html.escape(txt)))
    ul = "<ul style='list-style-type: none; padding-left: 0;'>%s</ul>"
    return _text(200, ul % "".join(week) + (ul % "".join(special) if special else ""))


@anvil.server.http_endpoint("/menus/:ref/:lang")
def old_menu_links(ref, lang, **kw):
    """Links to the menu files in that language, as the old widget showed them."""
    r = by_ref(ref)
    if r is None:
        return _text(404, "Restaurant not found", "text/plain; charset=utf-8")
    f = _file_by_key(r, lang)
    if f is not None:  # the old MENU QR codes point here with a menu file's id instead of a language: show that file
        return _serve_file(f)
    lang = _lang(r, lang)
    links = "".join(
        '<a href="%s" target="_blank" rel="noopener" style="display:block;margin:10px 0;padding:10px 15px;background-color:#555;color:#fff;'
        'text-decoration:none;border-radius:5px;transition:background-color .3s" onmouseover="this.style.backgroundColor=\'#333\'" '
        'onmouseout="this.style.backgroundColor=\'#555\'">%s</a>' % (html.escape(f["url"]), html.escape(f["title"])) for f in public_files(r, lang))
    if not links:  # no files: link to the live menu PlanPlate keeps
        links = '<a href="%s/#menu/%s" target="_blank" rel="noopener" style="display:block;margin:10px 0;padding:10px 15px;background-color:#555;color:#fff;text-decoration:none;border-radius:5px">%s</a>' % (
            anvil.server.get_app_origin(), r["slug"], {"en": "Menu", "fr": "Menu", "lv": "Ēdienkarte"}[lang])
    body = ('<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 20px auto; border-radius: 10px; background-color: #f0f0f0; '
            'box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);">%s</div>') % links
    return _text(200, body)


@anvil.server.http_endpoint("/menu/:ref/:key")
def old_menu_file(ref, key, **kw):
    f = _file_by_key(by_ref(ref), key)
    if f is None:
        return _text(404, "Not found", "text/plain; charset=utf-8")
    return _serve_file(f)


def _serve_file(f):
    name =re.sub(r"[^\w .-]", "", f["file"].name or "menu") or "menu"
    return anvil.server.HttpResponse(200, f["file"], headers=dict(CORS, **{"Content-Type": f["content_type"] or "application/octet-stream",
                                                                         "Content-Disposition": 'inline; filename="%s"' % name,
                                                                         "Cache-Control": "max-age=300"}))
