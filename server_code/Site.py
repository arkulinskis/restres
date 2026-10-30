# Site — Server Module. Restaurant websites, generated from one form (the Website tab).
#
# Every restaurant gets one website built on the same template (the sections of dilettante.lv: header, hero with photo
# or video, today strip, about, specials, menu, events, location & hours, gallery, reviews, highlights, contact, footer).
# Restaurants differ by their content and their colour palette.
#
#   hosted     /_/api/site/<path>            rendered fresh on every visit (so hours, specials, menu, events,
#                                            photo of the day and gallery are always current); counts visits
#   live parts /_/api/site/<path>?live=1     JSON {part: html}; a downloaded copy refreshes itself from here
#   download   download_site(rid)            a .zip with index.html + images/ + README.txt, to host anywhere
#   preview    preview_site(rid, data)       the HTML for unsaved form data (the builder's preview pane)
#
# The content lives in sites.content (JSON); name, address, phone and email stay on the restaurant row, so the
# booking form, emails and website never disagree.
import html as _html
import io
import json
import re
import zipfile
from datetime import timedelta
from urllib.parse import quote

import anvil
import anvil.server
from anvil.tables import app_tables

from . import Booking as B
from . import Media as MD
from . import Board as BD
from .Menu import _menu, hours_feed, TAGS
from .Portal import _rest, _nav, _user, EMAIL_RE

# ---------------------------------------------------------------- palettes (the colour toggle)
PALETTES = [
    {"key": "ivory", "name": "Ivory & brass", "bg": "#f6f3ee", "surface": "#fffdf9", "ink": "#1d1b18", "muted": "#6a655d",
     "line": "#e4ded4", "accent": "#9c7a43", "deep": "#1d1b18", "deep_ink": "#f3eee6"},
    {"key": "olive", "name": "Olive & copper", "bg": "#f6f2e9", "surface": "#fffdf8", "ink": "#23301b", "muted": "#5c6353",
     "line": "#e3ddcf", "accent": "#c7752f", "deep": "#2e481a", "deep_ink": "#f4efe4"},
    {"key": "bordeaux", "name": "Bordeaux", "bg": "#faf5f2", "surface": "#fffbf9", "ink": "#2a1418", "muted": "#6b585a",
     "line": "#eadcd8", "accent": "#8c2f39", "deep": "#3f1219", "deep_ink": "#f6ebe8"},
    {"key": "mauve", "name": "Mauve", "bg": "#f7f2f4", "surface": "#fffbfc", "ink": "#2a1f29", "muted": "#6a5d68",
     "line": "#e8dde3", "accent": "#b4536f", "deep": "#4b2e44", "deep_ink": "#f7edf3"},
    {"key": "harbour", "name": "Harbour blue", "bg": "#f2f5f7", "surface": "#fbfdfe", "ink": "#13212c", "muted": "#53616c",
     "line": "#dbe3e9", "accent": "#2f6f8f", "deep": "#12304a", "deep_ink": "#eef4f8"},
    {"key": "terracotta", "name": "Terracotta", "bg": "#fbf3ec", "surface": "#fffaf6", "ink": "#2d1d14", "muted": "#6c584b",
     "line": "#efdfd2", "accent": "#c0583a", "deep": "#4f2716", "deep_ink": "#fbefe6"},
    {"key": "garden", "name": "Garden green", "bg": "#f3f5f0", "surface": "#fcfdfa", "ink": "#1d2a20", "muted": "#566258",
     "line": "#dfe5d9", "accent": "#5e7d4f", "deep": "#233826", "deep_ink": "#eef3ea"},
    {"key": "noir", "name": "Night", "bg": "#121110", "surface": "#1b1a18", "ink": "#ece7de", "muted": "#a39d92",
     "line": "#2e2b27", "accent": "#c9a56a", "deep": "#050505", "deep_ink": "#ece7de"},
]
PALETTE = {p["key"]: p for p in PALETTES}
SECTIONS = ["today", "about", "specials", "menu", "events", "location", "gallery", "reviews", "highlights", "contact"]
SOCIAL = ["facebook", "instagram", "tripadvisor", "google", "tiktok", "youtube"]
URL_RE = re.compile(r"^https?://[^\s<>\"']{3,500}$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

LABELS = {
    "en": {"reserve": "Reserve a table", "menu": "Menu", "about": "About", "location": "Hours & location", "gallery": "Gallery",
           "contact": "Contact", "events": "Events", "specials": "Specials", "view_menu": "View the menu", "open_today": "Open today",
           "closed_today": "Closed today", "today": "Today", "photo_of_day": "Photo of the day", "today_specials": "On today",
           "coming_up": "Coming up", "address": "Address", "hours": "Opening hours", "closed": "Closed", "directions": "Get directions",
           "phone": "Phone", "email": "Email", "whatsapp": "WhatsApp", "follow": "Follow us", "made_with": "Website by PlanPlate",
           "reviews": "What our guests say", "full_menu": "Full menu", "special_days": "Coming up", "private": "Private event",
           "until": "Until", "only_today": "Today only", "every": "Every", "book_event": "Reserve for this event",
           "skip": "Skip to content", "menu_soon": "Our menu is coming soon.", "map": "Map", "rating": "Rated %d out of 5",
           "reserve_short": "Reserve", "open_menu": "Menu", "close": "Close", "posted": "Posted", "special_hours": "Special hours"},
    "fr": {"reserve": "Réserver une table", "menu": "Menu", "about": "À propos", "location": "Horaires et adresse", "gallery": "Galerie",
           "contact": "Contact", "events": "Événements", "specials": "Suggestions", "view_menu": "Voir le menu", "open_today": "Ouvert aujourd'hui",
           "closed_today": "Fermé aujourd'hui", "today": "Aujourd'hui", "photo_of_day": "Photo du jour", "today_specials": "Aujourd'hui",
           "coming_up": "À venir", "address": "Adresse", "hours": "Heures d'ouverture", "closed": "Fermé", "directions": "Itinéraire",
           "phone": "Téléphone", "email": "Courriel", "whatsapp": "WhatsApp", "follow": "Suivez-nous", "made_with": "Site créé avec PlanPlate",
           "reviews": "Ce qu'en disent nos clients", "full_menu": "Menu complet", "special_days": "Dates à noter", "private": "Événement privé",
           "until": "Jusqu'au", "only_today": "Aujourd'hui seulement", "every": "Chaque", "book_event": "Réserver pour cet événement",
           "skip": "Aller au contenu", "menu_soon": "Notre menu arrive bientôt.", "map": "Carte", "rating": "Noté %d sur 5",
           "reserve_short": "Réserver", "open_menu": "Menu", "close": "Fermer", "posted": "Publié", "special_hours": "Horaires spéciaux"},
    "lv": {"reserve": "Rezervēt galdiņu", "menu": "Ēdienkarte", "about": "Par mums", "location": "Darba laiks un adrese", "gallery": "Galerija",
           "contact": "Kontakti", "events": "Pasākumi", "specials": "Piedāvājumi", "view_menu": "Skatīt ēdienkarti", "open_today": "Šodien atvērts",
           "closed_today": "Šodien slēgts", "today": "Šodien", "photo_of_day": "Dienas foto", "today_specials": "Šodien",
           "coming_up": "Drīzumā", "address": "Adrese", "hours": "Darba laiks", "closed": "Slēgts", "directions": "Kā nokļūt",
           "phone": "Tālrunis", "email": "E-pasts", "whatsapp": "WhatsApp", "follow": "Sekojiet mums", "made_with": "Mājaslapa veidota ar PlanPlate",
           "reviews": "Viesu atsauksmes", "full_menu": "Pilna ēdienkarte", "special_days": "Īpašas dienas", "private": "Privāts pasākums",
           "until": "Līdz", "only_today": "Tikai šodien", "every": "Katru", "book_event": "Rezervēt šim pasākumam",
           "skip": "Pāriet uz saturu", "menu_soon": "Ēdienkarte drīzumā.", "map": "Karte", "rating": "Vērtējums %d no 5",
           "reserve_short": "Rezervēt", "open_menu": "Izvēlne", "close": "Aizvērt", "posted": "Publicēts", "special_hours": "Īpašs darba laiks"},
}
DAYS = {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "fr": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"],
        "lv": ["Pirmdiena", "Otrdiena", "Trešdiena", "Ceturtdiena", "Piektdiena", "Sestdiena", "Svētdiena"]}
MONTHS = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
          "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
          "lv": ["janv.", "febr.", "marts", "apr.", "maijs", "jūn.", "jūl.", "aug.", "sept.", "okt.", "nov.", "dec."]}


# ---------------------------------------------------------------- content: defaults, example, cleaning
def default_content(r):
    """A first draft from what PlanPlate already knows about the restaurant."""
    lang = B.language(r)
    L = LABELS[lang]
    return {
        "cuisine": "", "tagline": r["description"] or "", "logo": "", "logo_light": False,
        "hero": {"kind": "photo", "photo": "", "video": "", "youtube": ""},
        "about": {"heading": L["about"], "text": r["description"] or "", "photo1": "", "photo2": ""},
        "menu": {"heading": L["menu"], "intro": "", "photo": "", "link": ""},
        "location": {"heading": L["location"], "directions": "", "map": "", "show_map": True},
        "gallery": {"heading": "Our favourites" if lang == "en" else L["gallery"]},
        "specials_heading": L["specials"], "events_heading": L["events"],
        "reviews_heading": L["reviews"], "reviews": [],
        "highlights_heading": "", "highlights": [],
        "contact": {"whatsapp": False},
        "social": {k: "" for k in SOCIAL},
        "sections": {k: True for k in SECTIONS},
        "seo": (r["description"] or "")[:300],
    }


EXAMPLE_PHOTOS = [  # (theme asset, caption, in gallery)
    ("ex-dlt-hero.jpg", "The dining room at Dilettante", False), ("ex-dlt-about1.jpg", "A plated dish at Dilettante", False),
    ("ex-dlt-about2.jpg", "A plated dish at Dilettante", False), ("ex-dlt-menu.jpg", "A spread of dishes at Dilettante", False),
    ("ex-dlt-logo.png", "Dilettante logo", False),
    ("ex-dlt-g93.jpg", "Bruschetta trio", True), ("ex-dlt-g315.jpg", "Pasta with a glass of red", True),
    ("ex-dlt-g292.jpg", "Wood-fired pizza", True), ("ex-dlt-g267.jpg", "Risotto of the day", True),
    ("ex-dlt-g242.jpg", "Dessert and espresso", True), ("ex-dlt-g16.jpg", "Cocktails at the bar", True),
    ("ex-dlt-g118.jpg", "Antipasti to share", True), ("ex-dlt-g11.jpg", "Fresh pasta", True),
]


def example_photos(r):
    """Add the Dilettante example pictures to the restaurant's photos (once) and return {asset name: key}."""
    have = {p["url"]: p for p in app_tables.photos.search(restaurant=r, provider="example")}
    keys = {}
    for name, caption, gallery in EXAMPLE_PHOTOS:
        row = have.get(name)
        if row is None:
            w, h = (1021, 244) if name.endswith(".png") else (800, 533)
            row = MD._new_row(r, kind="image", provider="example", url=name, caption=caption, in_gallery=gallery,
                              format=name.rsplit(".", 1)[1], width=float(w), height=float(h))
        keys[name] = row["key"]
    return keys


def example_content(keys):
    """The first PlanPlate-generated website: Dilettante, a modern Italian restaurant in Old Riga (dilettante.lv)."""
    return {
        "cuisine": "Modern Italian restaurant", "tagline": "Bruschetta, pizza, pasta and good wine in a restored 18th-century mansion in Old Riga.",
        "logo": keys["ex-dlt-logo.png"], "logo_light": True,
        "hero": {"kind": "photo", "photo": keys["ex-dlt-hero.jpg"], "video": "", "youtube": ""},
        "about": {"heading": "About us", "photo1": keys["ex-dlt-about1.jpg"], "photo2": keys["ex-dlt-about2.jpg"], "text":
                  "Experience our restaurant in **Old Riga** inside a beautifully restored 18th century mansion – cozy and welcoming.\n\n"
                  "Dilettante is a modern Italian restaurant. Order anything from salads, bruschetta or soup. Move on to pizza, pasta or risotto "
                  "with **delicious cocktails** and **good wine**.\n\n"
                  "All this can be enjoyed in a modern interior consisting of dark mauve walls offset by brightly upholstered chairs and lots of "
                  "**natural light** from large windows.\n\n"
                  "We would love to see you at **Dilettante**, where we can serve you a unique moment of epicurious delight."},
        "menu": {"heading": "The menus", "intro": "Starters & bruschetta, pizza, pasta & risotto, desserts and a wine list chosen to go with them.",
                 "photo": keys["ex-dlt-menu.jpg"], "link": ""},
        "location": {"heading": "Old Riga", "directions": "In the heart of Old Riga, a short walk from the Freedom Monument.",
                     "map": "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2176.0200123997483!2d24.10944437716603!3d56.94845839927006!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x46eecfe04e2c3af3%3A0xce505c6e160cb043!2sDILETTANTE!5e0!3m2!1sen!2sca!4v1707236365746!5m2!1sen!2sca",
                     "show_map": True},
        "gallery": {"heading": "Our favourites"},
        "specials_heading": "Today's specials", "events_heading": "Events",
        "reviews_heading": "Latest reviews", "reviews": [
            {"name": "Thomas S.", "source": "Tripadvisor", "rating": 5,
             "text": "Unbelievable dining restaurant, interesting dishes, good pricing and really attentive staff made our evening great, thanks!"},
            {"name": "Mattias L.", "source": "Facebook", "rating": 5,
             "text": "Really a great spot for food lovers. Affordable prices for an old town. Recommend trying the bruschettas – they're a unique specialty here."},
            {"name": "Ellen J.", "source": "Facebook", "rating": 5,
             "text": "We were very happy with this restaurant. Very good food, nice location and lovely staff! We highly recommend this place!"}],
        "highlights_heading": "Experience Dilettante", "highlights": [
            {"title": "At our location in Riga", "text": "At Dilettante, we are proud to be recognized as one of the best Italian restaurants in Riga, offering guests a truly authentic and unforgettable dining experience."},
            {"title": "Perfect for date nights", "text": "Looking for the ideal place to take someone special? Dilettante is known as one of the top spots for romantic dates in Riga, with candle-lit dinners and a cozy, welcoming atmosphere."},
            {"title": "Authentic Italian cuisine", "text": "From handmade pasta and Italian flour pizza to premium wines and delectable desserts, our menu is crafted with love and respect for traditional Italian cooking."},
            {"title": "Book your table", "text": "Whether you're celebrating an occasion or just craving great Italian food, reserve your table today and discover why so many call us a top Italian restaurant in the region."}],
        "contact": {"whatsapp": True},
        "social": {"facebook": "https://www.facebook.com/dilettantelv/", "instagram": "https://www.instagram.com/dilettanteriga/",
                   "tripadvisor": "https://www.tripadvisor.com/Restaurant_Review-g274967-d19121339-Reviews-Dilettante-Riga_Riga_Region.html",
                   "google": "", "tiktok": "", "youtube": ""},
        "sections": {k: True for k in SECTIONS},
        "seo": "Experience modern Italian cuisine at Dilettante. Enjoy bruschetta, pizza, pasta, and more in our beautiful location in Riga.",
    }


def _s(v, n):
    return str(v or "").strip()[:n]


def _url(v):
    v = _s(v, 500)
    return v if URL_RE.match(v) else ""


def youtube_id(text):
    text = _s(text, 300)
    m = re.search(r"(?:youtu\.be/|[?&]v=|/embed/|/shorts/|/live/)([\w-]{11})", text) or re.match(r"^([\w-]{11})$", text)
    return m.group(1) if m else ""


def map_src(text):
    """An embeddable map URL from what the owner pasted: a Google Maps embed link, or a whole <iframe ...> snippet."""
    text = _s(text, 3000)
    m = re.search(r'src="([^"]+)"', text)
    if m:
        text = _html.unescape(m.group(1))
    if re.match(r"^https://(www\.)?google\.[a-z.]+/maps/embed\?", text) or re.match(r"^https://www\.openstreetmap\.org/export/embed\.html\?", text):
        return text[:2000]
    return ""


def clean_content(data, r):
    """Whatever the form sent, made safe and complete: known keys only, text trimmed, photos checked to be this
    restaurant's, links checked to be http(s)."""
    base = default_content(r)
    d = dict(data or {})

    def key(v):
        return v if MD.by_key(r, v) is not None else ""

    def sub(name):
        return dict(d.get(name) or {})

    hero, about, menu, loc, gal = sub("hero"), sub("about"), sub("menu"), sub("location"), sub("gallery")
    reviews = []
    for x in (d.get("reviews") or [])[:8]:
        x = dict(x or {})
        if _s(x.get("text"), 600) or _s(x.get("name"), 60):
            try:
                rating = max(1, min(5, int(x.get("rating") or 5)))
            except (TypeError, ValueError):
                rating = 5
            reviews.append({"name": _s(x.get("name"), 60), "source": _s(x.get("source"), 60), "rating": rating, "text": _s(x.get("text"), 600)})
    highlights = []
    for x in (d.get("highlights") or [])[:8]:
        x = dict(x or {})
        if _s(x.get("title"), 80) or _s(x.get("text"), 500):
            highlights.append({"title": _s(x.get("title"), 80), "text": _s(x.get("text"), 500)})
    sections = dict(base["sections"])
    for k, v in dict(d.get("sections") or {}).items():
        if k in sections:
            sections[k] = bool(v)
    social = {k: _url(dict(d.get("social") or {}).get(k)) for k in SOCIAL}
    kind = hero.get("kind") if hero.get("kind") in ("photo", "video", "youtube") else "photo"
    raw_map = _s(loc.get("map"), 3000)
    return {
        "cuisine": _s(d.get("cuisine"), 80), "tagline": _s(d.get("tagline"), 240), "logo": key(d.get("logo")),
        "logo_light": bool(d.get("logo_light")),
        "hero": {"kind": kind, "photo": key(hero.get("photo")), "video": key(hero.get("video")), "youtube": youtube_id(hero.get("youtube"))},
        "about": {"heading": _s(about.get("heading"), 80), "text": _s(about.get("text"), 4000), "photo1": key(about.get("photo1")),
                  "photo2": key(about.get("photo2"))},
        "menu": {"heading": _s(menu.get("heading"), 80), "intro": _s(menu.get("intro"), 400), "photo": key(menu.get("photo")),
                 "link": _url(menu.get("link"))},
        "location": {"heading": _s(loc.get("heading"), 80), "directions": _s(loc.get("directions"), 400),
                     "map": map_src(raw_map) or _url(raw_map), "show_map": loc.get("show_map", True) is not False},
        "gallery": {"heading": _s(gal.get("heading"), 80)},
        "specials_heading": _s(d.get("specials_heading"), 80), "events_heading": _s(d.get("events_heading"), 80),
        "reviews_heading": _s(d.get("reviews_heading"), 80), "reviews": reviews,
        "highlights_heading": _s(d.get("highlights_heading"), 80), "highlights": highlights,
        "contact": {"whatsapp": bool(dict(d.get("contact") or {}).get("whatsapp"))},
        "social": social, "sections": sections, "seo": _s(d.get("seo"), 300),
    }


def content_of(r, s):
    """The saved content, filled in with defaults for anything missing."""
    saved = s["content"] or {}
    return clean_content(saved, r) if saved else default_content(r)


# ---------------------------------------------------------------- the builder's callables
def site_url(s, origin=None):
    return (origin or anvil.server.get_app_origin()) + "/_/api/site/" + s["path"]


def _palette(s):
    return s["palette"] if s["palette"] in PALETTE else "ivory"


def _lang(r, s):
    return s["language"] if s["language"] in B.LANGS else B.language(r)


def _view(r, s):
    today = B.local_now(r).date()
    return {"path": s["path"], "published": bool(s["published"]), "palette": _palette(s), "accent": s["accent"] or "",
            "language": _lang(r, s), "content": content_of(r, s), "started": bool(s["content"]), "url": site_url(s),
            "updated": B.iso(s["updated"]), "published_at": B.iso(s["published_at"]), "views": int(s["views"] or 0),
            "visits_week": BD.week_visits(s, today),
            "restaurant": {"name": r["name"] or "", "address": r["address"] or "", "phone": r["phone"] or "",
                           "email": r["email"] or "", "slug": r["slug"]}}


def _reply(r, s):
    today = B.local_now(r).date()
    return {"ok": True, "nav": _nav(r), "site": _view(r, s), "palettes": PALETTES, "photos": [MD.view(p) for p in MD.all_photos(r)],
            "storage": "cloudinary" if MD.cloudinary() else "planplate", "origin": anvil.server.get_app_origin(),
            "counts": {"menu": len(list(app_tables.menu_items.search(restaurant=r))), "gallery": len(MD.gallery_photos(r)),
                       "specials": len(BD.specials_on(r, today)), "events": len(BD.public_events(r, today)),
                       "post": BD.latest_post(r, today) is not None},
            "languages": list(B.LANGS)}


@anvil.server.callable(require_user=True)
def get_site(rid):
    r = _rest(rid, "manager")
    return _reply(r, MD.site_row(r))


def _apply(r, s, data):
    """Check and store the builder's form. Returns an error message or None."""
    data = dict(data or {})
    upd = {}
    if "path" in data:
        path = B.slugify(data["path"])
        if path in MD.RESERVED:
            return "“%s” is reserved. Pick another web address." % path
        other = app_tables.sites.get(path=path)
        if other is not None and other != s:
            return "The web address “%s” is taken. Try another." % path
        upd["path"] = path
    if data.get("palette") in PALETTE:
        upd["palette"] = data["palette"]
    if "accent" in data:
        upd["accent"] = data["accent"].lower() if HEX_RE.match(str(data.get("accent") or "")) else ""
    if data.get("language") in B.LANGS:
        upd["language"] = data["language"]
    if "content" in data:
        upd["content"] = clean_content(data["content"], r)
    rest = dict(data.get("restaurant") or {})
    rupd = {}
    for k, n in (("name", 80), ("address", 200), ("phone", 40), ("email", 200)):
        if k in rest:
            rupd[k] = _s(rest[k], n)
    if "name" in rupd and not rupd["name"]:
        return "The restaurant needs a name."
    if rupd.get("email") and not EMAIL_RE.match(rupd["email"]):
        return "The email address doesn't look right."
    if "published" in data:
        upd["published"] = bool(data["published"])
        if upd["published"] and not s["published"]:
            upd["published_at"] = B.now_utc()
    upd["updated"] = B.now_utc()
    s.update(**upd)
    if rupd:
        r.update(**rupd)
    return None


@anvil.server.callable(require_user=True)
def save_site(rid, data):
    r = _rest(rid, "manager")
    s = MD.site_row(r)
    err = _apply(r, s, data)
    if err:
        return {"ok": False, "error": err}
    return _reply(r, s)


@anvil.server.callable(require_user=True)
def publish_site(rid, on=True):
    r = _rest(rid, "manager")
    s = MD.site_row(r)
    _apply(r, s, {"published": bool(on)})
    return _reply(r, s)


@anvil.server.callable(require_user=True)
def load_site_example(rid):
    """Fill the website with the Dilettante example (text, photos, colours) to see a finished site.
    The restaurant's own name, address, phone and email are kept; empty ones get Dilettante's."""
    r = _rest(rid, "manager")
    s = MD.site_row(r)
    keys = example_photos(r)
    s.update(content=example_content(keys), palette="olive", accent="", language="en", updated=B.now_utc())
    fill = {"address": "Teātra iela 6, Rīga, Latvia", "phone": "+371 26 544 718", "email": "dilettanteriga@gmail.com"}
    r.update(**{k: v for k, v in fill.items() if not r[k]})
    return _reply(r, s)


@anvil.server.callable(require_user=True)
def preview_site(rid, data=None):
    """The website as it would look with this (unsaved) form data."""
    r = _rest(rid, "manager")
    s = MD.site_row(r)
    data = dict(data or {})
    look = {"palette": data.get("palette") if data.get("palette") in PALETTE else _palette(s),
            "accent": data.get("accent") if HEX_RE.match(str(data.get("accent") or "")) else ("" if "accent" in data else s["accent"] or ""),
            "language": data.get("language") if data.get("language") in B.LANGS else _lang(r, s)}
    content = clean_content(data["content"], r) if "content" in data else content_of(r, s)
    info = dict(data.get("restaurant") or {})
    return {"ok": True, "html": Render(r, s, content, "preview", look=look, info=info).page()}


@anvil.server.callable(require_user=True)
def download_site(rid):
    """A .zip of the website to host anywhere: index.html, the pictures, and a README."""
    r = _rest(rid, "manager")
    s = MD.site_row(r)
    content = content_of(r, s)
    origin = anvil.server.get_app_origin()
    probe = Render(r, s, content, "download", origin)
    probe.page()
    files, local = {}, {}
    for key, row in probe.used.items():
        data = _photo_bytes(row, origin)
        if data:
            ext = (row["format"] or ("mp4" if row["kind"] == "video" else "jpg")).lower()
            name = "images/%s.%s" % (key[:12], ext)
            files[name] = data
            local[key] = name
            if row["kind"] == "video" and row["thumb"] is not None:
                files["images/%s-poster.jpg" % key[:12]] = row["thumb"].get_bytes()
                local[key + ":poster"] = "images/%s-poster.jpg" % key[:12]
    page = Render(r, s, content, "download", origin, local=local).page()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.html", page)
        for name, data in files.items():
            z.writestr(name, data, compress_type=zipfile.ZIP_STORED)
        z.writestr("README.txt", README % {"name": r["name"], "url": site_url(s, origin), "origin": origin})
    name = (s["path"] or "website") + "-website.zip"
    return anvil.BlobMedia("application/zip", buf.getvalue(), name=name)


README = """%(name)s website, made with PlanPlate
=============================================

To put it online, upload everything in this folder (index.html and the images folder) to any web host:
your current hosting, Netlify Drop (drag the folder onto app.netlify.com/drop), GitHub Pages, or similar.

It stays connected to PlanPlate. Every time someone opens the page it refreshes, from PlanPlate:
  - today's opening hours and the week's hours
  - your specials, events and photo of the day
  - your menu and your photo gallery
"Reserve a table" opens your PlanPlate booking form.

So keep updating everything in PlanPlate; you only need to download a new copy after changing the
website's text, photos or colours.

Your PlanPlate-hosted website is at:
%(url)s
"""


def _photo_bytes(row, origin):
    try:
        if row["provider"] == "planplate" and row["media"] is not None:
            return row["media"].get_bytes()
        import anvil.http
        u = MD.urls(row, origin)["url"]
        resp = anvil.http.request(u, method="GET")
        return resp.get_bytes() if hasattr(resp, "get_bytes") else None
    except Exception as e:
        print("download: couldn't fetch", row["key"], e)
        return None


# ---------------------------------------------------------------- the public website
BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|embedly|whatsapp|curl|wget|python", re.I)


def _count_visit(s, r):
    try:
        req = getattr(anvil.server, "request", None)
        ua = ((getattr(req, "headers", None) or {}).get("user-agent") or "") if req is not None else ""
        if BOT_RE.search(ua):
            return
        today = B.local_now(r).date()
        visits = {k: v for k, v in (s["visits"] or {}).items() if k >= (today - timedelta(days=30)).isoformat()}
        visits[today.isoformat()] = int(visits.get(today.isoformat(), 0)) + 1
        s.update(visits=visits, views=int(s["views"] or 0) + 1)
    except Exception as e:
        print("visit count failed:", e)


def _page(status, body, ctype="text/html; charset=utf-8", cache="max-age=60"):
    return anvil.server.HttpResponse(status, body, headers={"Content-Type": ctype, "Cache-Control": cache,
                                                            "Access-Control-Allow-Origin": "*"})


@anvil.server.http_endpoint("/site/:path")
def site_page(path, live=None, **kw):
    s = app_tables.sites.get(path=str(path or "").strip().lower())
    if s is None or not s["published"] or s["restaurant"] is None:
        return _page(404, NOT_FOUND)
    r = s["restaurant"]
    content = content_of(r, s)
    if live:
        rd = Render(r, s, content, "hosted")
        return _page(200, json.dumps(rd.live_parts()), "application/json; charset=utf-8")
    _count_visit(s, r)
    return _page(200, Render(r, s, content, "hosted").page())


NOT_FOUND = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Not found</title>"
             "<body style=\"font:16px/1.6 system-ui,sans-serif;display:grid;place-items:center;min-height:90vh;margin:0;background:#f6f3ee;color:#1d1b18\">"
             "<div style='text-align:center;padding:20px'><h1 style='font:500 2rem Georgia,serif'>This website isn't here</h1>"
             "<p>The address may be mistyped, or the restaurant hasn't published its website yet.</p></div>")


# ---------------------------------------------------------------- rendering
def esc(x):
    return _html.escape(str(x if x is not None else ""), quote=True)


def prose(text):
    """Paragraphs (blank lines) with **bold**, escaped."""
    out = []
    for para in re.split(r"\n\s*\n", str(text or "").strip()):
        if not para.strip():
            continue
        p = esc(para.strip()).replace("\n", "<br>")
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        out.append("<p>%s</p>" % p)
    return "".join(out)


def _ink_for(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#1a1714" if (0.299 * r + 0.587 * g + 0.114 * b) > 165 else "#ffffff"


ICONS = {
    "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "camera": '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    "menu": '<path d="M3 6h18M3 12h18M3 18h18"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "star": '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    "facebook": '<path d="M15 3h-2.5A4.5 4.5 0 0 0 8 7.5V10H5.5v3.5H8V21h3.5v-7.5H14l.5-3.5h-3V7.8c0-.7.5-1.3 1.3-1.3H15z"/>',
    "instagram": '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.3" cy="6.7" r=".8"/>',
    "tripadvisor": '<circle cx="7" cy="13" r="3.5"/><circle cx="17" cy="13" r="3.5"/><path d="M2 8.5h4M18 8.5h4M6 8.5c3.5-2.5 8.5-2.5 12 0"/><circle cx="7" cy="13" r=".6"/><circle cx="17" cy="13" r=".6"/>',
    "google": '<path d="M20.5 12.2c0-.6-.1-1.2-.2-1.7H12v3.3h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.6-3.9 2.6-6.5z"/><path d="M12 21c2.4 0 4.5-.8 5.9-2.2l-2.9-2.2c-.8.5-1.8.9-3 .9a5.3 5.3 0 0 1-5-3.6H4v2.3A9 9 0 0 0 12 21z"/><path d="M7 13.9a5.3 5.3 0 0 1 0-3.6V8H4a9 9 0 0 0 0 8.1z"/><path d="M12 6.6c1.3 0 2.5.5 3.4 1.3l2.6-2.6A9 9 0 0 0 4 8l3 2.3a5.3 5.3 0 0 1 5-3.7z"/>',
    "tiktok": '<path d="M14 3v11.5a3.5 3.5 0 1 1-3-3.4"/><path d="M14 3c.5 2.6 2.2 4.2 5 4.5"/>',
    "youtube": '<rect x="2.5" y="5.5" width="19" height="13" rx="3.5"/><path d="m10 9.5 5 2.5-5 2.5z"/>',
    "whatsapp": '<path d="M3.5 20.5 5 16a8.5 8.5 0 1 1 3.2 3.1z"/><path d="M9 8.6c0 3.3 3.1 6.4 6.4 6.4l1-1.6-2-1-1 .8c-1.2-.5-2-1.3-2.6-2.6l.8-1-1-2z"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
}
SOCIAL_NAMES = {"facebook": "Facebook", "instagram": "Instagram", "tripadvisor": "Tripadvisor", "google": "Google",
                "tiktok": "TikTok", "youtube": "YouTube"}


def icon(name, cls="ic"):
    return ('<svg class="%s" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true">%s</svg>' % (cls, ICONS.get(name, "")))


class Render(object):
    """Builds the website's HTML. mode: hosted | preview | download.
    In download mode, `local` maps photo keys to files in the zip; `used` collects the photos the page shows."""

    def __init__(self, r, s, content, mode, origin=None, look=None, info=None, local=None):
        self.r, self.s, self.c, self.mode = r, s, content, mode
        self.origin = origin or anvil.server.get_app_origin()
        look = look or {}
        self.palette = PALETTE.get(look.get("palette") or _palette(s), PALETTE["ivory"])
        self.accent = look["accent"] if "accent" in look else (s["accent"] or "")
        self.lang = look.get("language") or _lang(r, s)
        self.L = LABELS[self.lang]
        info = info or {}
        self.name = _s(info.get("name"), 80) or r["name"] or ""
        self.address = _s(info["address"], 200) if "address" in info else (r["address"] or "")
        self.phone = _s(info["phone"], 40) if "phone" in info else (r["phone"] or "")
        self.email = _s(info["email"], 200) if "email" in info else (r["email"] or "")
        self.local = local or {}
        self.used = {}
        self.today = B.local_now(r).date()
        self.on = dict(content.get("sections") or {})
        self.book_url = "%s/#book/%s/%s" % (self.origin, r["slug"], self.lang)

    # -- pictures
    def photo(self, key):
        return MD.by_key(self.r, key) if key else None

    def src(self, row, which="url"):
        if row is None:
            return ""
        if self.mode == "download" and row["provider"] != "cloudinary":
            self.used[row["key"]] = row
            if which == "poster_url" and (row["key"] + ":poster") in self.local:
                return self.local[row["key"] + ":poster"]
            if which != "poster_url" and row["key"] in self.local:
                return self.local[row["key"]]
        u = MD.urls(row, self.origin)
        return u.get(which) or u["url"]

    def img(self, row, cls="", sizes_full=True, eager=False):
        if row is None:
            return ""
        w, h = row["width"], row["height"]
        dims = ' width="%d" height="%d"' % (int(w), int(h)) if w and h else ""
        return '<img%s src="%s" alt="%s"%s%s>' % (' class="%s"' % cls if cls else "", esc(self.src(row, "url" if sizes_full else "thumb_url")),
                                                  esc(row["caption"] or self.name), dims, "" if eager else ' loading="lazy" decoding="async"')

    # -- small pieces
    def fdate(self, d):
        return "%s %d %s" % (DAYS[self.lang][d.weekday()], d.day, MONTHS[self.lang][d.month - 1])

    def hours_text(self, iv):
        return ", ".join("%s–%s" % (a, b) for a, b in iv) if iv else self.L["closed"]

    def heading(self, text, eyebrow=""):
        return ('<div class="eyebrow">%s</div>' % esc(eyebrow) if eyebrow else "") + "<h2>%s</h2>" % esc(text)

    def book_btn(self, label=None, cls="btn"):
        return '<a class="%s" href="%s" target="_blank" rel="noopener" data-pp-book>%s</a>' % (cls, esc(self.book_url), esc(label or self.L["reserve"]))

    # -- sections
    def css(self):
        p = dict(self.palette)
        if self.accent:
            p["accent"] = self.accent
        p["accent_ink"] = _ink_for(p["accent"])
        vars_ = ("--bg:%(bg)s;--surface:%(surface)s;--ink:%(ink)s;--muted:%(muted)s;--line:%(line)s;--accent:%(accent)s;"
                 "--accent-ink:%(accent_ink)s;--deep:%(deep)s;--deep-ink:%(deep_ink)s;" % p)
        return ":root{%s%s}%s" % (vars_, "color-scheme:dark;" if p["key"] == "noir" else "", CSS)

    def header(self):
        logo = self.photo(self.c.get("logo"))
        brand = ('<img src="%s" alt="%s"%s>' % (esc(self.src(logo)), esc(self.name), ' class="inv"' if (self.palette["key"] == "noir") else "")
                 if logo else "<span>%s</span>" % esc(self.name))
        links = []
        if self.on.get("menu"):
            links.append(("#menu", self.L["menu"]))
        if self.on.get("events") and BD.public_events(self.r, self.today):
            links.append(("#events", self.L["events"]))
        if self.on.get("location"):
            links.append(("#location", self.L["location"]))
        if self.on.get("gallery") and MD.gallery_photos(self.r):
            links.append(("#gallery", self.L["gallery"]))
        if self.on.get("contact"):
            links.append(("#contact", self.L["contact"]))
        nav = "".join('<a href="%s">%s</a>' % (h, esc(t)) for h, t in links)
        return ('<header class="hd" data-hd><div class="wrap in"><a class="brand" href="#top">%s</a><nav class="nav" id="pp-nav">%s</nav>'
                '%s<button class="burger" type="button" aria-controls="pp-nav" aria-expanded="false" aria-label="%s">%s</button></div></header>'
                % (brand, nav, self.book_btn(self.L["reserve_short"], "btn sm"), esc(self.L["open_menu"]), icon("menu")))

    def hero(self):
        h = self.c.get("hero") or {}
        photo = self.photo(h.get("photo"))
        bg = ""
        if h.get("kind") == "video" and self.photo(h.get("video")) is not None:
            v = self.photo(h.get("video"))
            poster = self.src(v, "poster_url") or (self.src(photo) if photo else "")
            ctype = {"mp4": "video/mp4", "webm": "video/webm", "mov": "video/mp4"}.get((v["format"] or "mp4").lower(), "video/mp4")
            bg = ('<video autoplay muted loop playsinline preload="metadata"%s><source src="%s" type="%s"></video>'
                  % (' poster="%s"' % esc(poster) if poster else "", esc(self.src(v)), ctype))
        elif h.get("kind") == "youtube" and h.get("youtube"):
            yid = h["youtube"]
            bg = ((self.img(photo, "poster", eager=True) if photo else "") +
                  '<iframe class="yt" src="https://www.youtube-nocookie.com/embed/%s?autoplay=1&amp;mute=1&amp;loop=1&amp;playlist=%s&amp;controls=0'
                  '&amp;playsinline=1&amp;rel=0&amp;modestbranding=1" title="" tabindex="-1" aria-hidden="true" allow="autoplay; encrypted-media"></iframe>'
                  % (esc(yid), esc(yid)))
        elif photo is not None:
            bg = self.img(photo, eager=True)
        logo = self.photo(self.c.get("logo"))
        title = ('<img class="hero-logo%s" src="%s" alt="%s">' % (" light" if self.c.get("logo_light") else "", esc(self.src(logo)), esc(self.name))
                 if logo else esc(self.name))
        btns = self.book_btn() + ('<a class="btn line" href="#menu">%s</a>' % esc(self.L["view_menu"]) if self.on.get("menu") else "")
        return ('<section class="hero%s" id="top"><div class="bg">%s</div><div class="wrap in">%s<h1>%s</h1>%s<div class="btns">%s</div></div></section>'
                % ("" if bg else " plain", bg, '<div class="eyebrow">%s</div>' % esc(self.c.get("cuisine")) if self.c.get("cuisine") else "",
                   title, '<p class="tagline">%s</p>' % esc(self.c.get("tagline")) if self.c.get("tagline") else "", btns))

    def today_part(self):
        if not self.on.get("today"):
            return ""
        ctx = B.Ctx(self.r)
        iv, src = B.day_hours(ctx, self.today)
        hours = B.intervals_text(iv)
        pills = ['<span class="pill"><span class="dot%s"></span><b>%s</b>%s</span>' % (
            "" if hours else " off", esc(self.L["open_today"] if hours else self.L["closed_today"]),
            (" " + esc(self.hours_text(hours))) if hours else (" · " + esc(src["label"]) if src["kind"] == "special" else ""))]
        sp = BD.specials_on(self.r, self.today)
        if sp and self.on.get("specials"):
            pills.append('<a class="pill" href="#specials">%s<b>%s</b> %s</a>' % (icon("star"), esc(self.L["today_specials"]),
                                                                              esc(", ".join(x["title"] for x in sp[:3]))))
        evs = [e for e in BD.public_events(self.r, self.today, 7)]
        if evs and self.on.get("events"):
            e = evs[0]
            when = self.L["today"] if e["date"] == self.today else self.fdate(e["date"])
            pills.append('<a class="pill" href="#events">%s<b>%s</b> %s · %s</a>' % (icon("calendar"), esc(e["title"]), esc(when),
                                                                                  esc(B.hm(int(e["start_min"] or 0)))))
        post = BD.latest_post(self.r, self.today)
        pod = ""
        if post is not None:
            ph = post["photo"]
            label = self.L["photo_of_day"] if post["date"] == self.today else "%s · %s" % (self.L["photo_of_day"], self.fdate(post["date"]))
            pod = ('<figure class="pod">%s<figcaption><span class="eyebrow">%s</span>%s</figcaption></figure>'
                   % (self.img(ph, sizes_full=False) if ph is not None else "", esc(label), esc(post["text"])))
        return ('<section class="today" data-live="today" aria-label="%s"><div class="wrap in"><div class="pills">%s</div>%s</div></section>'
                % (esc(self.L["today"]), "".join(pills), pod))

    def about(self):
        a = self.c.get("about") or {}
        if not self.on.get("about") or not (a.get("text") or a.get("photo1")):
            return ""
        p1, p2 = self.photo(a.get("photo1")), self.photo(a.get("photo2"))
        pics = "".join(self.img(p) for p in (p1, p2) if p is not None)
        return ('<section class="about" id="about"><div class="wrap in%s">%s<div class="prose">%s%s%s</div></div></section>'
                % ("" if pics else " solo", '<div class="pics n%d">%s</div>' % (len([p for p in (p1, p2) if p]), pics) if pics else "",
                   self.heading(a.get("heading") or self.L["about"]), prose(a.get("text")),
                   '<a class="btn" href="#menu">%s</a>' % esc(self.L["view_menu"]) if self.on.get("menu") else ""))

    def specials_part(self):
        sp = BD.specials_on(self.r, self.today) if self.on.get("specials") else []
        if not sp:
            return '<div data-live="specials"></div>'
        cards = []
        for x in sp:
            if x["start"] and x["end"] and x["start"] == x["end"]:
                when = self.L["only_today"]
            elif x["end"]:
                when = "%s %d %s" % (self.L["until"], x["end"].day, MONTHS[self.lang][x["end"].month - 1])
            elif x["days"] and len(x["days"]) < 7:
                when = "%s: %s" % (self.L["every"], ", ".join(DAYS[self.lang][d][:3] for d in sorted(x["days"])))
            else:
                when = ""
            ph = x["photo"]
            cards.append('<article class="card sp">%s<div class="body"><div class="row"><h3>%s</h3>%s</div>%s%s</div></article>' % (
                self.img(ph, sizes_full=False) if ph is not None else "", esc(x["title"]),
                '<span class="price">%s</span>' % esc(x["price"]) if x["price"] else "",
                '<p>%s</p>' % esc(x["description"]) if x["description"] else "", '<span class="when">%s</span>' % esc(when) if when else ""))
        return ('<section class="specials" id="specials" data-live="specials"><div class="wrap">%s<div class="cards">%s</div></div></section>'
                % (self.heading(self.c.get("specials_heading") or self.L["specials"], self.L["today"]), "".join(cards)))

    def menu_part(self):
        m = self.c.get("menu") or {}
        if not self.on.get("menu"):
            return '<div data-live="menu"></div>'
        sections = _menu(self.r)
        tabs = "".join('<button class="tab%s" type="button" data-tab="m%d">%s</button>' % (" on" if i == 0 else "", i, esc(s["title"]))
                       for i, s in enumerate(sections)) if len(sections) > 1 else ""
        panels = []
        for i, s in enumerate(sections):
            items = "".join(
                '<div class="dish"><div class="row"><b>%s</b>%s<span class="lead"></span><span class="price">%s</span></div>%s</div>' % (
                    esc(it["name"]), "".join('<span class="tag" title="%s">%s</span>' % (esc(TAGS[t]), esc(t)) for t in it["tags"]),
                    esc(it["price"]), '<p>%s</p>' % esc(it["description"]) if it["description"] else "")
                for it in s["items"])
            panels.append('<div class="panel%s" data-panel="m%d">%s%s%s</div>' % (
                " on" if i == 0 else "", i, "<h3>%s</h3>" % esc(s["title"]) if len(sections) < 2 else "",
                '<p class="note">%s</p>' % esc(s["description"]) if s["description"] else "", items))
        photo = self.photo(m.get("photo"))
        body = ("".join(panels) if panels else '<p class="note">%s</p>' % esc(self.L["menu_soon"]))
        link = '<a class="btn line" href="%s" target="_blank" rel="noopener">%s</a>' % (esc(m["link"]), esc(self.L["full_menu"])) if m.get("link") else ""
        return ('<section class="menu" id="menu" data-live="menu"><div class="wrap in%s"><div>%s%s<div class="tabs" role="tablist">%s</div>%s'
                '<div class="btns">%s%s</div></div>%s</div></section>'
                % ("" if photo else " solo", self.heading(m.get("heading") or self.L["menu"]),
                   '<p class="lead">%s</p>' % esc(m.get("intro")) if m.get("intro") else "", tabs, body, self.book_btn(), link,
                   '<div class="pic">%s</div>' % self.img(photo) if photo else ""))

    def events_part(self):
        evs = BD.public_events(self.r, self.today) if self.on.get("events") else []
        if not evs:
            return '<div data-live="events"></div>'
        cards = []
        for e in evs[:6]:
            d = e["date"]
            cards.append('<article class="card ev">%s<div class="date"><b>%d</b><span>%s</span></div><div class="body"><h3>%s</h3>'
                         '<div class="meta">%s · %s–%s</div>%s%s</div></article>' % (
                             self.img(e["photo"], "evpic", sizes_full=False) if e["photo"] is not None else "", d.day, esc(MONTHS[self.lang][d.month - 1]),
                             esc(e["title"]), esc(DAYS[self.lang][d.weekday()]), B.hm(int(e["start_min"] or 0)), B.hm(int(e["end_min"] or 0)),
                             '<p>%s</p>' % esc(e["description"]) if e["description"] else "",
                             self.book_btn(self.L["book_event"], "btn sm line") if not e["blocks"] else ""))
        return ('<section class="events" id="events" data-live="events"><div class="wrap">%s<div class="evs">%s</div></div></section>'
                % (self.heading(self.c.get("events_heading") or self.L["events"], self.L["coming_up"]), "".join(cards)))

    def hours_part(self):
        f = hours_feed(self.r, days=1)
        rows = "".join('<tr%s><th>%s</th><td>%s</td></tr>' % (
            ' class="now"' if i == self.today.weekday() else "", esc(DAYS[self.lang][i]), esc(self.hours_text(w["hours"])))
            for i, w in enumerate(f["week"]))
        sp = [x for x in f["special_days"] if x["date"] <= (self.today + timedelta(days=45)).isoformat()][:6]
        specials = ""
        if sp:
            items = "".join('<li><b>%s</b> %s · %s</li>' % (esc(self.fdate(B.parse_date(x["date"]))), esc(x["label"]),
                                                          esc(self.L["closed"] if x["closed"] else self.hours_text(x["hours"]))) for x in sp)
            specials = '<div class="spdays"><div class="eyebrow">%s</div><ul>%s</ul></div>' % (esc(self.L["special_days"]), items)
        return '<div data-live="hours"><table class="hours">%s</table>%s</div>' % (rows, specials)

    def location(self):
        if not self.on.get("location"):
            return ""
        loc = self.c.get("location") or {}
        mp = loc.get("map") or ""
        src = mp if map_src(mp) else ("https://maps.google.com/maps?q=%s&z=16&output=embed" % quote(self.address) if self.address else "")
        directions = mp if (mp and not map_src(mp)) else ("https://www.google.com/maps/dir/?api=1&destination=%s" % quote(self.address) if self.address else "")
        mapframe = ('<div class="map"><iframe src="%s" title="%s" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe></div>'
                    % (esc(src), esc(self.L["map"])) if (src and loc.get("show_map", True)) else "")
        info = ('<div class="info">%s%s%s<h3>%s %s</h3>%s<div class="btns">%s%s</div></div>' % (
            self.heading(loc.get("heading") or self.L["location"]),
            '<p class="addr">%s%s</p>' % (icon("pin"), esc(self.address)) if self.address else "",
            '<p class="note">%s</p>' % esc(loc.get("directions")) if loc.get("directions") else "",
            icon("clock"), esc(self.L["hours"]), self.hours_part(), self.book_btn(),
            '<a class="btn line" href="%s" target="_blank" rel="noopener">%s</a>' % (esc(directions), esc(self.L["directions"])) if directions else ""))
        return '<section class="location" id="location"><div class="wrap in%s">%s%s</div></section>' % ("" if mapframe else " solo", info, mapframe)

    def gallery(self):
        if not self.on.get("gallery") or not MD.gallery_photos(self.r):
            return ""
        g = MD.gallery_style(self.s)
        heading = (self.c.get("gallery") or {}).get("heading") or g.get("heading") or self.L["gallery"]
        return ('<section class="gallery" id="gallery"><div class="wrap"><h2>%s</h2></div><planplate-gallery feed-url="%s" theme="%s" bg-style="%s" '
                'picture-style="%s" size="%s" motion="%s" mobile-layout="%s" accent-color="%s" background-color="%s"></planplate-gallery></section>' % (
                    esc(heading), esc(self.origin + "/_/api/gallery/" + self.r["slug"]), g["theme"], g["bg_style"], g["picture_style"], g["size"],
                    g["motion"], g["mobile_layout"], esc(self.accent or g["accent"]), esc(self.palette["deep"])))

    def reviews(self):
        rv = self.c.get("reviews") or []
        if not self.on.get("reviews") or not rv:
            return ""
        cards = "".join('<figure class="card rv"><div class="stars" role="img" aria-label="%s">%s</div><blockquote>%s</blockquote>'
                        '<figcaption><b>%s</b>%s</figcaption></figure>' % (
                            esc(self.L["rating"] % x["rating"]), icon("star", "ic on") * x["rating"] + icon("star", "ic") * (5 - x["rating"]),
                            esc(x["text"]), esc(x["name"]), (" · " + esc(x["source"])) if x["source"] else "") for x in rv)
        return '<section class="reviews"><div class="wrap">%s<div class="cards">%s</div></div></section>' % (
            self.heading(self.c.get("reviews_heading") or self.L["reviews"]), cards)

    def highlights(self):
        hl = self.c.get("highlights") or []
        if not self.on.get("highlights") or not hl:
            return ""
        items = "".join('<div class="hl"><span class="n">%02d</span><div><h3>%s</h3><p>%s</p></div></div>' % (i + 1, esc(x["title"]), esc(x["text"]))
                        for i, x in enumerate(hl))
        return '<section class="highlights"><div class="wrap">%s<div class="hls">%s</div></div></section>' % (
            self.heading(self.c.get("highlights_heading") or self.name), items)

    def contact(self):
        if not self.on.get("contact"):
            return ""
        cards = []
        if self.phone:
            digits = re.sub(r"\D", "", self.phone)
            if (self.c.get("contact") or {}).get("whatsapp") and digits:
                cards.append(("whatsapp", self.L["whatsapp"], self.phone, "https://wa.me/" + digits))
            cards.append(("phone", self.L["phone"], self.phone, "tel:" + re.sub(r"[^\d+]", "", self.phone)))
        if self.email:
            cards.append(("mail", self.L["email"], self.email, "mailto:" + self.email))
        if self.address:
            cards.append(("pin", self.L["address"], self.address, "#location"))
        body = "".join('<a class="card cc" href="%s"%s>%s<span><small>%s</small>%s</span></a>' % (
            esc(href), ' target="_blank" rel="noopener"' if href.startswith("http") else "", icon(ic), esc(label), esc(val)) for ic, label, val, href in cards)
        return ('<section class="contact" id="contact"><div class="wrap">%s<div class="ccs">%s<a class="card cc book" href="%s" target="_blank" rel="noopener" data-pp-book>%s<span><small>%s</small>%s</span></a></div></div></section>'
                % (self.heading(self.L["contact"]), body, esc(self.book_url), icon("calendar"), esc(self.name), esc(self.L["reserve"])))

    def footer(self):
        soc = self.c.get("social") or {}
        links = "".join('<a href="%s" target="_blank" rel="noopener" aria-label="%s">%s</a>' % (esc(soc[k]), SOCIAL_NAMES[k], icon(k))
                        for k in SOCIAL if soc.get(k))
        return ('<footer class="ft"><div class="wrap in"><div><div class="fname">%s</div><div class="small">%s</div></div>'
                '<div class="social">%s</div><div class="small fine">© %d %s · <a href="https://planplate.com" target="_blank" rel="noopener">%s</a></div></div></footer>'
                % (esc(self.name), esc(self.address), (('<span class="small">%s</span>' % esc(self.L["follow"])) + links) if links else "",
                   self.today.year, esc(self.name), esc(self.L["made_with"])))

    def jsonld(self):
        f = hours_feed(self.r, days=1)
        spec = []
        for i, w in enumerate(f["week"]):
            for a, b in w["hours"]:
                spec.append({"@type": "OpeningHoursSpecification", "dayOfWeek": B.DAY_NAMES[i], "opens": a, "closes": "23:59" if b == "24:00" else b})
        data = {"@context": "https://schema.org", "@type": "Restaurant", "name": self.name, "acceptsReservations": self.book_url,
                "hasMenu": "%s/#menu/%s" % (self.origin, self.r["slug"]), "openingHoursSpecification": spec}
        if self.mode == "hosted":
            data["url"] = site_url(self.s, self.origin)
        if self.address:
            data["address"] = {"@type": "PostalAddress", "streetAddress": self.address}
        if self.phone:
            data["telephone"] = self.phone
        if self.c.get("cuisine"):
            data["servesCuisine"] = self.c["cuisine"]
        hero = self.photo((self.c.get("hero") or {}).get("photo"))
        if hero is not None:
            data["image"] = MD.urls(hero, self.origin)["url"]
        same = [v for v in (self.c.get("social") or {}).values() if v]
        if same:
            data["sameAs"] = same
        return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    def live_parts(self):
        return {"today": self.today_part(), "specials": self.specials_part(), "menu": self.menu_part(),
                "events": self.events_part(), "hours": self.hours_part()}

    def page(self):
        hero_row = self.photo((self.c.get("hero") or {}).get("photo"))
        og = MD.urls(hero_row, self.origin)["url"] if hero_row is not None else ""
        desc = self.c.get("seo") or self.c.get("tagline") or ""
        title = self.name + (" – " + self.c["cuisine"] if self.c.get("cuisine") else "")
        logo = self.photo(self.c.get("logo"))
        canonical = site_url(self.s, self.origin) if self.mode == "hosted" else ""
        live = (self.origin + "/_/api/site/" + self.s["path"] + "?live=1") if self.mode == "download" else ""
        main = "".join([self.hero(), self.today_part(), self.about(), self.specials_part(), self.menu_part(), self.events_part(),
                        self.location(), self.gallery(), self.reviews(), self.highlights(), self.contact()])
        head = ['<!doctype html>', '<html lang="%s">' % self.lang, "<head>", '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">', "<title>%s</title>" % esc(title),
                '<meta name="description" content="%s">' % esc(desc), '<meta name="generator" content="PlanPlate">',
                '<meta name="theme-color" content="%s">' % self.palette["deep"],
                '<meta property="og:type" content="restaurant"><meta property="og:title" content="%s"><meta property="og:description" content="%s">'
                % (esc(title), esc(desc))]
        if og:
            head.append('<meta property="og:image" content="%s">' % esc(og))
        if canonical:
            head.append('<link rel="canonical" href="%s"><meta property="og:url" content="%s">' % (esc(canonical), esc(canonical)))
        if logo is not None:
            head.append('<link rel="icon" href="%s">' % esc(self.src(logo)))
        head += ['<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
                 '<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Inter+Tight:wght@400;500;600&display=swap" rel="stylesheet">',
                 "<style>%s</style>" % self.css(), '<script type="application/ld+json">%s</script>' % self.jsonld()]
        if self.on.get("gallery") and MD.gallery_photos(self.r):
            head.append('<script src="%s/_/theme/planplate-gallery.js" defer></script>' % esc(self.origin))
        head.append("</head>")
        body = ['<body><a class="skip" href="#main">%s</a>' % esc(self.L["skip"]), self.header(), '<main id="main">%s</main>' % main, self.footer(),
                "<script>%s</script>" % (SITE_JS.replace("__BOOK__", json.dumps(self.book_url)).replace("__LIVE__", json.dumps(live))
                                         .replace("__CLOSE__", json.dumps(self.L["close"]))), "</body></html>"]
        return "\n".join(head + body)


# The page's small script: phone menu, booking pop-up, menu tabs, and (downloaded copies) live refresh from PlanPlate.
SITE_JS = r"""(function(){
  var BOOK=__BOOK__, LIVE=__LIVE__, CLOSE=__CLOSE__, d=document;
  d.documentElement.classList.add('js');
  var hd=d.querySelector('[data-hd]');
  d.addEventListener('click',function(e){
    var b=e.target.closest('.burger');
    if(b){var open=!hd.classList.contains('open');hd.classList.toggle('open',open);b.setAttribute('aria-expanded',String(open));return;}
    if(e.target.closest('.nav a')&&hd){hd.classList.remove('open');}
    var t=e.target.closest('[data-tab]');
    if(t){var box=t.closest('section');box.querySelectorAll('[data-tab]').forEach(function(x){x.classList.toggle('on',x===t);});
      box.querySelectorAll('[data-panel]').forEach(function(p){p.classList.toggle('on',p.getAttribute('data-panel')===t.getAttribute('data-tab'));});return;}
    var k=e.target.closest('[data-pp-book]');
    if(k&&!e.metaKey&&!e.ctrlKey&&window.innerWidth>0){e.preventDefault();book();}
  });
  function book(){
    var o=d.createElement('div');o.className='ppbook';o.setAttribute('role','dialog');o.setAttribute('aria-modal','true');
    o.innerHTML='<div class="box"><button class="x" type="button" aria-label="'+CLOSE+'">&times;</button><iframe title="Booking" src="'+BOOK+'"></iframe></div>';
    function close(){o.remove();d.removeEventListener('keydown',esc);d.body.style.overflow='';}
    function esc(e){if(e.key==='Escape')close();}
    o.addEventListener('click',function(e){if(e.target===o||e.target.closest('.x'))close();});
    d.addEventListener('keydown',esc);d.body.appendChild(o);d.body.style.overflow='hidden';o.querySelector('.x').focus();
  }
  if(LIVE&&window.fetch){
    fetch(LIVE).then(function(r){return r.ok?r.json():null;}).then(function(parts){
      if(!parts)return;
      Object.keys(parts).forEach(function(k){
        var el=d.querySelector('[data-live="'+k+'"]');
        if(el)el.outerHTML=parts[k]||'<div data-live="'+k+'"></div>';
      });
    }).catch(function(){});
  }
})();"""

CSS = r"""
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:76px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "Inter Tight",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
img,video,iframe{max-width:100%;display:block}
a{color:inherit;text-underline-offset:3px}
h1,h2,h3{font-family:Lora,Georgia,serif;font-weight:500;line-height:1.15;margin:0 0 .5em;letter-spacing:-.01em}
h2{font-size:clamp(1.9rem,4.2vw,2.9rem)}
h3{font-size:1.3rem}
p{margin:0 0 1em}
.skip{position:absolute;left:-9999px}.skip:focus{left:12px;top:12px;z-index:100;background:var(--surface);padding:8px 12px;border-radius:8px}
.wrap{max-width:1160px;margin:0 auto;padding:0 20px}
section{padding:clamp(56px,8vw,104px) 0}
.eyebrow{font:600 .72rem/1.2 "Inter Tight",sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:12px;display:block}
.ic{width:20px;height:20px;flex:none}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:.85rem 1.7rem;border-radius:999px;background:var(--accent);color:var(--accent-ink);border:1px solid var(--accent);font:600 .95rem/1.2 "Inter Tight",sans-serif;text-decoration:none;cursor:pointer;transition:filter .15s,transform .15s;white-space:nowrap}
.btn:hover{filter:brightness(1.07)}.btn:active{transform:translateY(1px)}
.btn.line{background:transparent;color:inherit;border-color:currentColor}
.btn.sm{padding:.55rem 1.1rem;font-size:.86rem}
.btns{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px}
.note{color:var(--muted)}
.small{font-size:.86rem}
.hd{position:sticky;top:0;z-index:40;background:var(--surface);border-bottom:1px solid var(--line)}
.hd .in{display:flex;align-items:center;gap:18px;min-height:66px}
.brand{display:flex;align-items:center;text-decoration:none;font:600 1.35rem Lora,Georgia,serif;min-width:0}
.brand img{height:36px;width:auto;max-width:180px;object-fit:contain}.brand img.inv{filter:invert(1)}
.nav{display:flex;gap:2px;margin-left:auto}
.nav a{padding:8px 12px;border-radius:99px;text-decoration:none;font-size:.94rem;color:var(--muted)}
.nav a:hover{color:var(--ink);background:color-mix(in srgb,var(--accent) 12%,transparent)}
.burger{display:none;background:none;border:0;color:var(--ink);padding:8px;cursor:pointer}.burger .ic{width:24px;height:24px}
@media (max-width:880px){
  .nav{position:absolute;top:100%;left:0;right:0;flex-direction:column;background:var(--surface);border-bottom:1px solid var(--line);padding:6px 14px 14px;display:none;margin:0}
  .nav a{padding:12px 10px;font-size:1.05rem}
  .hd.open .nav{display:flex}
  .hd .in > .btn{margin-left:auto}
  .burger{display:grid}
}
.hero{position:relative;min-height:min(86vh,780px);display:grid;place-items:center;text-align:center;color:#fff;overflow:hidden;background:var(--deep);padding:90px 0}
.hero .bg{position:absolute;inset:0}
.hero .bg img,.hero .bg video{width:100%;height:100%;object-fit:cover}
.hero .bg .yt{position:absolute;top:50%;left:50%;width:max(100%,calc(min(86vh,780px)*1.78));aspect-ratio:16/9;height:auto;min-height:100%;transform:translate(-50%,-50%);border:0;pointer-events:none}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.28),rgba(0,0,0,.5) 60%,rgba(0,0,0,.6))}
.hero.plain::after{display:none}
.hero .in{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center}
.hero .eyebrow{color:#fff;opacity:.9}
.hero h1{font-size:clamp(2.6rem,8vw,5.2rem);margin:0 0 .25em;color:#fff}
.hero .hero-logo{max-width:min(28rem,86vw);width:100%;height:auto;margin:0 auto}.hero .hero-logo.light{filter:invert(1) brightness(2)}
.hero .tagline{font-size:clamp(1.05rem,2.2vw,1.3rem);max-width:40rem;opacity:.94;margin:0 auto}
.hero .btns{justify-content:center}
.hero .btn.line{color:#fff}
.today{padding:22px 0;background:color-mix(in srgb,var(--accent) 10%,var(--bg));border-bottom:1px solid var(--line)}
.today .in{display:flex;flex-wrap:wrap;gap:16px 28px;align-items:center;justify-content:space-between}
.pills{display:flex;flex-wrap:wrap;gap:8px;min-width:0}
.pill{display:inline-flex;gap:8px;align-items:center;padding:8px 14px;border-radius:99px;background:var(--surface);border:1px solid var(--line);font-size:.92rem;text-decoration:none;max-width:100%}
.pill .ic{width:16px;height:16px;color:var(--accent)}
.pill .dot{width:8px;height:8px;border-radius:50%;background:#3f8f5a;flex:none}.pill .dot.off{background:#b04a3a}
.pod{display:flex;gap:14px;align-items:center;margin:0;max-width:440px}
.pod img{width:84px;height:84px;object-fit:cover;border-radius:12px;flex:none}
.pod .eyebrow{margin-bottom:4px}.pod figcaption{font-size:.95rem}
.about .in{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:clamp(28px,5vw,72px);align-items:center}
.about .in.solo{grid-template-columns:minmax(0,46rem)}
.pics{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pics.n1{grid-template-columns:1fr}
.pics img{width:100%;height:auto;aspect-ratio:3/4.2;object-fit:cover;border-radius:16px}.pics img:nth-child(2){margin-top:52px}
.prose p{color:var(--muted)}.prose strong{color:var(--ink);font-weight:600}
.specials{background:var(--surface)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px;margin-top:28px}
.sp{overflow:hidden;display:flex;flex-direction:column}.sp img{width:100%;aspect-ratio:4/3;height:auto;object-fit:cover}
.sp .body{padding:18px 20px 20px}.sp .row{display:flex;gap:12px;align-items:baseline;justify-content:space-between}.sp h3{margin:0}
.price{font-weight:600;color:var(--accent);white-space:nowrap}.sp p{color:var(--muted);margin:8px 0 0}
.when{display:inline-block;margin-top:12px;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.menu .in{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:clamp(28px,5vw,64px);align-items:start}
.menu .in.solo{grid-template-columns:minmax(0,48rem)}
.menu .pic img{width:100%;height:auto;border-radius:16px;object-fit:cover;position:sticky;top:90px}
.lead{font-size:1.08rem;color:var(--muted)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:18px 0 10px}
.tab{padding:8px 16px;border-radius:99px;border:1px solid var(--line);background:transparent;cursor:pointer;font:500 .92rem "Inter Tight",sans-serif;color:var(--muted)}
.tab.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.js .panel{display:none}.js .panel.on{display:block}.panel{margin-top:6px}.panel h3{margin-top:18px}
.dish{padding:13px 0;border-bottom:1px solid var(--line)}
.dish .row{display:flex;gap:10px;align-items:baseline}
.dish b{font-weight:600}.dish .lead{flex:1;border-bottom:1px dotted var(--line);min-width:20px;transform:translateY(-4px)}
.dish .price{color:var(--ink)}.dish p{margin:3px 0 0;color:var(--muted);font-size:.93rem}
.tag{font-size:.68rem;padding:1px 6px;border:1px solid var(--line);border-radius:99px;color:var(--muted);letter-spacing:.04em}
.evs{display:grid;gap:16px;margin-top:28px}
.ev{display:grid;grid-template-columns:auto minmax(0,1fr);gap:20px;padding:20px;align-items:start}
.ev .evpic{display:none}
.ev .date{width:74px;text-align:center;border-radius:12px;background:var(--accent);color:var(--accent-ink);padding:10px 4px}
.ev .date b{display:block;font:500 2rem/1 Lora,Georgia,serif}.ev .date span{font-size:.78rem;letter-spacing:.1em;text-transform:uppercase}
.ev h3{margin:0 0 4px}.ev .meta{color:var(--muted);font-size:.9rem;margin-bottom:8px}.ev p{color:var(--muted);margin:0 0 12px}
@media (min-width:760px){.ev{grid-template-columns:auto minmax(0,1fr) 220px}.ev .evpic{display:block;grid-column:3;grid-row:1;width:100%;height:150px;object-fit:cover;border-radius:12px}}
.location{background:var(--surface)}
.location .in{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:clamp(28px,5vw,64px);align-items:start}
.location .in.solo{grid-template-columns:minmax(0,40rem)}
.addr{display:flex;gap:10px;align-items:flex-start;font-size:1.05rem}.addr .ic{color:var(--accent);margin-top:3px}
.location h3{display:flex;gap:10px;align-items:center;margin:22px 0 8px;font-size:1.15rem}.location h3 .ic{color:var(--accent)}
.hours{border-collapse:collapse;width:100%;max-width:420px}
.hours th,.hours td{padding:7px 0;border-bottom:1px solid var(--line);text-align:left;font-weight:400}
.hours td{text-align:right;font-variant-numeric:tabular-nums}
.hours tr.now th,.hours tr.now td{font-weight:600;color:var(--accent)}
.spdays{margin-top:18px}.spdays ul{list-style:none;padding:0;margin:0}.spdays li{padding:4px 0;color:var(--muted)}.spdays b{color:var(--ink);font-weight:600}
.map{border-radius:16px;overflow:hidden;border:1px solid var(--line);min-height:380px;height:100%}
.map iframe{width:100%;height:100%;min-height:380px;border:0}
.gallery{background:var(--deep);color:var(--deep-ink);padding-bottom:clamp(40px,6vw,80px)}
.gallery h2{text-align:center;margin-bottom:24px}
planplate-gallery{display:block}
.rv{margin:0;padding:24px}.stars{display:flex;gap:2px;margin-bottom:12px}.stars .ic{width:18px;height:18px;color:var(--line)}
.stars .ic.on{color:var(--accent);fill:var(--accent)}
.rv blockquote{margin:0 0 16px;font:italic 1.08rem/1.6 Lora,Georgia,serif}.rv figcaption{color:var(--muted);font-size:.9rem}.rv figcaption b{color:var(--ink)}
.highlights{background:var(--surface)}
.hls{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:10px 48px;margin-top:24px}
.hl{display:flex;gap:18px;padding:20px 0;border-top:1px solid var(--line)}
.hl .n{font:500 1.6rem/1 Lora,Georgia,serif;color:var(--accent);min-width:2.2ch}.hl h3{margin:0 0 6px}.hl p{color:var(--muted);margin:0}
.ccs{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-top:24px}
.cc{display:flex;gap:14px;align-items:center;padding:20px;text-decoration:none;transition:border-color .15s}
.cc:hover{border-color:var(--accent)}.cc .ic{width:26px;height:26px;color:var(--accent)}
.cc span{min-width:0;overflow-wrap:anywhere}.cc small{display:block;color:var(--muted);font-size:.78rem;letter-spacing:.08em;text-transform:uppercase}
.cc.book{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}.cc.book .ic,.cc.book small{color:var(--accent-ink)}
.ft{background:var(--deep);color:var(--deep-ink);padding:44px 0 36px}
.ft .in{display:flex;flex-wrap:wrap;gap:20px 40px;align-items:center;justify-content:space-between}
.fname{font:500 1.5rem Lora,Georgia,serif}.ft .small{opacity:.75}
.social{display:flex;gap:6px;align-items:center}.social .small{margin-right:8px}
.social a{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;border:1px solid color-mix(in srgb,var(--deep-ink) 30%,transparent)}
.social a:hover{background:color-mix(in srgb,var(--deep-ink) 12%,transparent)}
.fine{width:100%;opacity:.6}.fine a{color:inherit}
.ppbook{position:fixed;inset:0;z-index:1000;background:rgba(15,13,11,.6);display:flex;align-items:center;justify-content:center;padding:16px}
.ppbook .box{position:relative;width:min(560px,100%);height:min(820px,100%);background:#faf8f4;border-radius:16px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.4)}
.ppbook iframe{width:100%;height:100%;border:0}
.ppbook .x{position:absolute;top:8px;right:10px;z-index:2;border:0;background:rgba(255,255,255,.8);width:36px;height:36px;border-radius:50%;font:26px/1 Georgia,serif;color:#333;cursor:pointer}
@media (max-width:860px){
  .about .in,.menu .in,.location .in{grid-template-columns:minmax(0,1fr)}
  .menu .pic{order:-1}.menu .pic img{position:static;max-height:300px}
  .map,.map iframe{min-height:300px}
  .pics img:nth-child(2){margin-top:28px}
}
@media (max-width:560px){
  .ppbook{padding:0}.ppbook .box{height:100%;border-radius:0}
  .ev{grid-template-columns:minmax(0,1fr);gap:12px}.ev .date{display:flex;gap:8px;align-items:baseline;width:auto;justify-self:start;padding:6px 12px}
  .ev .date b{font-size:1.3rem}
  .hd .in > .btn{padding:.5rem .9rem}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.hero .bg video,.hero .bg .yt{display:none}}
"""
