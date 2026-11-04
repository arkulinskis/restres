"""The website builder's form data and its sections (Pages.Website). Values are read and written by dotted paths:
"content.about.heading", "content.reviews.0.name", "restaurant.address"."""
import copy

SOCIAL = [("facebook", "Facebook"), ("instagram", "Instagram"), ("tripadvisor", "Tripadvisor"), ("google", "Google reviews"),
          ("tiktok", "TikTok"), ("youtube", "YouTube")]
LANG_NAMES = {"en": "English", "fr": "Français", "lv": "Latviešu"}


class Model:
    """F = {path, palette, accent, language, content, restaurant}; D = the get_site reply (photos, counts, palettes...)."""

    def __init__(self, data):
        self.load(data)
        self.on_change = None

    def load(self, data):
        self.D = data
        s = data["site"]
        self.F = copy.deepcopy({"path": s["path"], "palette": s["palette"], "accent": s["accent"], "language": s["language"],
                                "content": s["content"], "restaurant": s["restaurant"]})
        self.F["restaurant"].pop("slug", None)
        self.dirty = False

    def get(self, path, default=None):
        o = self.F
        for k in path.split("."):
            if isinstance(o, list):
                i = int(k)
                o = o[i] if i < len(o) else None
            elif isinstance(o, dict):
                o = o.get(k)
            else:
                o = None
            if o is None:
                return default
        return o

    def set(self, path, value):
        ks = path.split(".")
        o = self.F
        for i, k in enumerate(ks[:-1]):
            nxt = ks[i + 1]
            if isinstance(o, list):
                o = o[int(k)]
                continue
            if o.get(k) is None:
                o[k] = [] if nxt.isdigit() else {}
            o = o[k]
        last = ks[-1]
        if isinstance(o, list):
            o[int(last)] = value
        else:
            o[last] = value
        self.dirty = True
        if self.on_change:
            self.on_change(path)

    def photo(self, key):
        for p in self.D["photos"]:
            if p["key"] == key:
                return p
        return None

    def add_photo(self, p):
        if p and not self.photo(p["key"]):
            self.D["photos"].append(p)

    def palette(self):
        for p in self.D["palettes"]:
            if p["key"] == self.F["palette"]:
                return p
        return self.D["palettes"][0]


def plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def sections(m):
    """[{id, title, toggle, ok, sum, fields: [spec]}] for the builder. A spec is {type, path?, label?, ...}."""
    F, D, c = m.F, m.D, m.D["counts"]
    con = F["content"]
    hero = con.get("hero") or {}
    k = hero.get("kind") or "photo"
    out = [
        {"id": "look", "title": "Web address & colours", "ok": bool(F["path"]), "sum": m.palette()["name"] + (" + own accent" if F["accent"] else ""),
         "fields": [{"type": "path", "label": "Web address", "prefix": D["origin"].split("//")[-1] + "/_/api/site/",
                     "hint": "Letters, numbers and dashes. Share this address, or point your own domain at it later."},
                    {"type": "palette", "label": "Colours"}, {"type": "accent"},
                    {"type": "language", "label": "Language of the website's buttons and labels", "hint": "Your own texts stay as you write them."}]},
        {"id": "hero", "title": "Top of the page", "ok": bool(hero.get("photo") or hero.get("video") or hero.get("youtube")),
         "sum": {"photo": "Photo", "video": "Video", "youtube": "YouTube video"}.get(k, ""),
         "fields": [{"type": "text", "path": "restaurant.name", "label": "Restaurant name"},
                    {"type": "text", "path": "content.cuisine", "label": "What you are", "ph": "Modern Italian restaurant"},
                    {"type": "text", "path": "content.tagline", "label": "One line that sells it", "ph": "Handmade pasta and natural wine in Old Riga"},
                    {"type": "photo", "path": "content.logo", "label": "Logo (optional; a PNG with a transparent background looks best)"},
                    {"type": "check", "path": "content.logo_light", "label": "Show the logo in white over the photo"},
                    {"type": "hero"},
                    {"type": "photo", "path": "content.hero.photo",
                     "label": "Background photo (wide, at least 1600px)" if k == "photo" else "Photo shown while the video loads, and on phones that save data"}]
         + ([{"type": "photo", "path": "content.hero.video", "label": "Video (MP4, short and silent loops work best)", "kind": "video"}] if k == "video" else [])
         + ([{"type": "text", "path": "content.hero.youtube", "label": "YouTube link", "ph": "https://www.youtube.com/watch?v=…",
              "hint": "It plays silently in the background, on repeat."}] if k == "youtube" else [])},
        {"id": "about", "title": "About", "toggle": "about", "ok": bool((con.get("about") or {}).get("text")),
         "fields": [{"type": "show", "key": "about", "label": "this section"}, {"type": "text", "path": "content.about.heading", "label": "Heading"},
                    {"type": "area", "path": "content.about.text", "label": "Your story", "h": 170,
                     "hint": "Leave an empty line between paragraphs. Put **two stars** around words to make them bold."},
                    {"type": "photo", "path": "content.about.photo1", "label": "Photo 1"}, {"type": "photo", "path": "content.about.photo2", "label": "Photo 2"}]},
        {"id": "menu", "title": "Menu", "toggle": "menu", "ok": c["menu"] > 0 or bool((con.get("menu") or {}).get("link")), "sum": plural(c["menu"], "dish", "dishes"),
         "fields": [{"type": "show", "key": "menu", "label": "the menu"},
                    {"type": "info", "text": "The dishes come from your Menu page: %s now. Sold-out dishes hide themselves." % plural(c["menu"], "dish", "dishes"),
                     "go": "dishes", "go_label": "Edit the menu"},
                    {"type": "text", "path": "content.menu.heading", "label": "Heading"},
                    {"type": "area", "path": "content.menu.intro", "label": "A line about the menu", "h": 60},
                    {"type": "photo", "path": "content.menu.photo", "label": "Menu photo"},
                    {"type": "text", "path": "content.menu.link", "label": "Link to a full menu (optional)", "ph": "https://…/menu.pdf"}]},
        {"id": "live", "title": "Today, specials & events", "ok": True, "sum": "Updates itself",
         "fields": [{"type": "info", "text": "These change by themselves as you use PlanPlate: today's hours, your specials, the photo of the day and public events."},
                    {"type": "show", "key": "today", "label": "the “today” strip (hours, photo of the day)"}, {"type": "show", "key": "specials", "label": "specials"},
                    {"type": "text", "path": "content.specials_heading", "label": "Specials heading"},
                    {"type": "show", "key": "events", "label": "public events"}, {"type": "text", "path": "content.events_heading", "label": "Events heading"},
                    {"type": "info", "text": "%s on today · %s coming up%s" % (plural(c["specials"], "special"), plural(c["events"], "public event"),
                                                                            " · photo of the day posted" if c["post"] else ""), "go": "today", "go_label": "Today"}]},
        {"id": "location", "title": "Location & hours", "toggle": "location", "ok": bool(F["restaurant"].get("address")),
         "sum": "" if F["restaurant"].get("address") else "Add your address",
         "fields": [{"type": "show", "key": "location", "label": "the location and hours"},
                    {"type": "text", "path": "restaurant.address", "label": "Address", "ph": "12 rue Saint-Paul, Montréal"},
                    {"type": "text", "path": "content.location.heading", "label": "Heading", "ph": "Old Montréal"},
                    {"type": "area", "path": "content.location.directions", "label": "How to find you (optional)", "h": 60},
                    {"type": "area", "path": "content.location.map", "label": "Google Maps link (optional)", "h": 60,
                     "ph": "Paste the “Embed a map” code from Google Maps", "hint": "Without it, the map is found from your address."},
                    {"type": "check", "path": "content.location.show_map", "label": "Show a map"},
                    {"type": "info", "text": "Opening hours come from your Opening hours page, special days included.", "go": "hours", "go_label": "Opening hours"}]},
        {"id": "gallery", "title": "Gallery", "toggle": "gallery", "ok": c["gallery"] > 0, "sum": plural(c["gallery"], "photo"),
         "fields": [{"type": "show", "key": "gallery", "label": "the photo gallery"},
                    {"type": "text", "path": "content.gallery.heading", "label": "Heading", "ph": "Our favourites"},
                    {"type": "info", "text": "%s in your gallery. Add, order and style them on the Gallery page." % plural(c["gallery"], "photo"),
                     "go": "gallery", "go_label": "Gallery"}]},
        {"id": "reviews", "title": "Reviews", "toggle": "reviews", "ok": bool(con.get("reviews")), "sum": str(len(con.get("reviews") or [])) or "",
         "fields": [{"type": "show", "key": "reviews", "label": "reviews"}, {"type": "text", "path": "content.reviews_heading", "label": "Heading"},
                    {"type": "list", "list": "reviews"}]},
        {"id": "highlights", "title": "Highlights", "toggle": "highlights", "ok": bool(con.get("highlights")), "sum": str(len(con.get("highlights") or [])) or "",
         "fields": [{"type": "show", "key": "highlights", "label": "highlights"},
                    {"type": "text", "path": "content.highlights_heading", "label": "Heading", "ph": "Why guests love us"}, {"type": "list", "list": "highlights"}]},
        {"id": "contact", "title": "Contact & social links", "toggle": "contact", "ok": bool(F["restaurant"].get("phone") or F["restaurant"].get("email")),
         "fields": [{"type": "show", "key": "contact", "label": "contact details"}, {"type": "text", "path": "restaurant.phone", "label": "Phone"},
                    {"type": "text", "path": "restaurant.email", "label": "Email"},
                    {"type": "check", "path": "content.contact.whatsapp", "label": "Guests can message this number on WhatsApp"}]
         + [{"type": "text", "path": "content.social." + key, "label": name + " link", "ph": "https://"} for key, name in SOCIAL]},
        {"id": "seo", "title": "Google & sharing", "ok": bool(con.get("seo")),
         "fields": [{"type": "area", "path": "content.seo", "label": "Description for Google and link previews", "h": 80,
                     "hint": "One or two sentences. It shows under your name in Google results and when the link is shared."},
                    {"type": "info", "text": "Your website also tells Google your opening hours, address and booking link, so they can show in search results."}]},
    ]
    for s in out:
        on = not s.get("toggle") or bool(m.get("content.sections." + str(s["toggle"])))
        s["on"] = on
        s.setdefault("sum", "")
        if not on:
            s["sum"] = "Hidden"
    return out
