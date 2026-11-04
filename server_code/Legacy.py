# Legacy — Server Module. Menu files (photos or PDFs of a menu, per language, like "Food" and "Drinks"), and the public
# addresses of the OLD PlanPlate apps (client.planplate.com, restaurant.planplate.com), so restaurant websites that
# embed the old code keep working once those domains point at this app:
#
#   /restaurant/<old id>          the booking page (the old "Reserve" pop-up loads it in an iframe)  -> #book/<slug>
#   /_/api/v1/<old id>/<lang>     opening hours as an HTML list (the old <div restaurant="..."> widget)
#   /_/api/menus/<old id>/<lang>  links to the menu files in that language (the old <div menus="..."> widget)
#   /_/api/menu/<old id>/<file>   one menu file, shown in the browser
#   /_/api/gallery/<old id>       the gallery feed (Media.gallery_feed also finds restaurants by old id)
#
# The old id is the restaurant's UUID in the old apps (restaurants.legacy_id, set in Settings). Learned from the public
# pages of dilettante.lv and the old APIs' public answers (Nov 2026); photos there live on Cloudinary under
# restaurants/<old id>/, and Media.folder() uploads into the same folder when the old id is set.
import html
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
            "type": f["content_type"] or "", "name": f["file"].name if f["file"] is not None else "",
            "url": "%s/_/api/menu/%s/%s" % (anvil.server.get_app_origin(), ref, f["key"]), "position": int(f["position"] or 0)}


def files_of(r, lang=None):
    rows = sorted(app_tables.menu_files.search(restaurant=r), key=lambda f: (int(f["position"] or 0), B._created_key(f)))
    return [f for f in rows if not lang or not f["language"] or f["language"] == lang]


@anvil.server.callable(require_user=True)
def get_menu_files(rid):
    r = P._rest(rid, "manager")
    return {"ok": True, "files": [_file_view(f, r) for f in files_of(r)], "languages": list(B.LANGS)}


@anvil.server.callable(require_user=True)
def add_menu_file(rid, media, title, language=""):
    r = P._rest(rid, "manager")
    title = str(title or "").strip()[:60]
    if not title:
        return {"ok": False, "error": "Give the menu a name, like Food or Drinks."}
    if media is None:
        return {"ok": False, "error": "Choose a PDF or a photo of the menu."}
    ctype = (media.content_type or "").lower()
    if ctype not in FILE_TYPES:
        return {"ok": False, "error": "Menus can be PDFs or photos (JPEG, PNG, WebP)."}
    if len(media.get_bytes()) > MAX_FILE:
        return {"ok": False, "error": "That file is over 15 MB. Make it smaller first."}
    language = language if language in B.LANGS else ""
    app_tables.menu_files.add_row(restaurant=r, key=uuid.uuid4().hex, title=title, language=language, file=media,
                                  content_type=ctype, position=len(files_of(r)), created=B.now_utc())
    return get_menu_files(rid)


@anvil.server.callable(require_user=True)
def delete_menu_file(rid, fid):
    r = P._rest(rid, "manager")
    P._child(app_tables.menu_files, r, fid).delete()
    return get_menu_files(rid)


def public_files(r, lang):
    return [{"title": f["title"] or "", "url": _file_view(f, r)["url"], "type": f["content_type"] or ""} for f in files_of(r, lang)]


# ---------------------------------------------------------------- the old public addresses
@anvil.server.route("/restaurant/:ref")
def old_booking_page(ref, **kw):
    """The old booking page: send the guest to the new booking form (the old pop-up shows it in its iframe)."""
    r = by_ref(ref)
    target = "/#book/%s" % r["slug"] if r is not None else "/"
    return anvil.server.HttpResponse(302, "", headers={"Location": target})


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
    r = by_ref(ref)
    f = app_tables.menu_files.get(key=str(key or "")) if re.match(r"^[0-9a-f-]{24,36}$", str(key or "")) else None
    if r is None or f is None or f["restaurant"] != r or f["file"] is None:
        return _text(404, "Not found", "text/plain; charset=utf-8")
    name = re.sub(r"[^\w .-]", "", f["file"].name or "menu") or "menu"
    return anvil.server.HttpResponse(200, f["file"], headers=dict(CORS, **{"Content-Type": f["content_type"] or "application/octet-stream",
                                                                         "Content-Disposition": 'inline; filename="%s"' % name,
                                                                         "Cache-Control": "max-age=300"}))
