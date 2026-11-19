from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import ElementsTemplate
from ... import pp, router, state

JS_END = "</" + "script>"
BUTTON_OPTS = [  # the Reserve button's look: the address of /_/api/embed.js carries it (Public.embed_js)
    ("style", "Style", [("ink", "Dark"), ("brass", "Brass"), ("light", "Light"), ("outline", "Outline")]),
    ("shape", "Shape", [("pill", "Pill"), ("rounded", "Rounded")]),
    ("size", "Size", [("sm", "Small"), ("md", "Medium"), ("lg", "Large")]),
]
LANG_NAMES = {"en": "English", "fr": "Français", "lv": "Latviešu"}


class Elements(ElementsTemplate):
    """#elements/<rid>: every piece a restaurant pastes into its own website, grouped by type (booking, menu, opening
    hours, photos, developers). The Reserve button gets a style picker with a live preview of the real button
    (/_/api/embed.js); the own-button code is tucked under "advanced" so nobody pastes both (2026-11-19)."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_share", self.rid)
        self.rnav.show(self.D["nav"])
        s = self.D["settings"]
        self.slug, self.name = s["slug"], s["name"]
        self.origin = self.D.get("origin") or pp.app_url().rstrip("/")
        langs = self.D.get("languages") or ["en"]
        self.opts = {"style": state.store_get("rbStyle", "ink"), "shape": state.store_get("rbShape", "pill"),
                     "size": state.store_get("rbSize", "md"), "lang": ""}
        self.button_spec = list(BUTTON_OPTS)
        if len(langs) > 1:
            self.button_spec.append(("lang", "Language", [("", "Visitor's choice")] + [(l, LANG_NAMES.get(l, l)) for l in langs]))
        self.bg = "light"
        self.button_opts.add_event_handler("x-style", self._opt)
        state.set_attr(self.gallery_link, "href", router.href("gallery", self.rid))
        state.set_attr(self.share_link, "href", router.href("share", self.rid))
        self._codes()
        self._draw_button()

    # ---------------------------------------------------------------- the code blocks
    def _codes(self):
        o, slug, name = self.origin, self.slug, self.name
        book, menu = pp.book_url(slug), pp.menu_url(slug)
        c = self.D.get("counts") or {}
        self.booking_panel.items = [
            {"title": "Booking form inside a page", "text": "The whole form as part of your page, for a “Reservations” page. Nothing to click first.",
             "code": '<iframe src="%s" title="Reserve a table at %s" style="width:100%%;max-width:560px;height:860px;border:0"></iframe>' % (book, name)},
            {"title": "Booking link", "text": "For Instagram and Facebook, your Google Business Profile, email signatures and messages.", "code": book, "open": book},
        ]
        self.own_panel.items = [
            {"title": "Your own button or link", "text": "Give your element the attribute data-planplate-open, then add the script once on the page.",
             "code": '<a href="#" data-planplate-open>Book a table</a>\n<script src="%s/_/api/embed.js?r=%s&button=none">%s' % (o, slug, JS_END)},
        ]
        self.menu_count.text = "%s · %s" % (state.plural(c.get("dishes", 0), "dish", "dishes"), state.plural(c.get("files", 0), "menu file"))
        self.menu_panel.items = [
            {"title": "Live menu", "text": "Your uploaded menu files (PDFs, photos) as buttons, then the dishes typed into PlanPlate. Sold-out dishes hide themselves.",
             "code": '<div data-planplate-menu></div>\n<script src="%s/_/api/menu.js?r=%s">%s' % (o, slug, JS_END)},
            {"title": "Menu page link", "text": "The same page the menu QR code opens: for a “Menu” button or link on your site.", "code": menu, "open": menu},
        ]
        self.hours_panel.items = [
            {"title": "Live opening hours", "text": "The week's hours from your periods, plus special days coming up (holidays, closures).",
             "code": '<div data-planplate-hours></div>\n<script src="%s/_/api/hours.js?r=%s">%s' % (o, slug, JS_END)},
        ]
        self.photo_count.text = state.plural(c.get("photos", 0), "photo") + " in the gallery"
        self.photos_panel.items = [
            {"title": "Photo gallery", "text": "Your gallery in the look you chose on the Gallery page (layout, colours, full-screen view). Change the look there and every site follows.",
             "code": '<planplate-showcase restaurant="%s"></planplate-showcase>\n<script src="%s/_/theme/pp-showcase.js" defer>%s' % (slug, o, JS_END)},
        ]
        self.dev_panel.items = [
            {"title": "JSON feeds", "text": "The same data for your own code: menu (with menu files), opening hours, and the gallery (look + photos).",
             "code": "%s/_/api/menu?r=%s\n%s/_/api/hours?r=%s\n%s/_/api/showcase/%s" % (o, slug, o, slug, o, slug)},
        ]

    # ---------------------------------------------------------------- the Reserve button
    def _button_src(self):
        q = "r=%s" % self.slug
        for k, default in (("style", "ink"), ("shape", "pill"), ("size", "md")):
            if self.opts[k] != default:
                q += "&%s=%s" % (k, self.opts[k])
        if self.opts.get("lang"):
            q += "&lang=" + self.opts["lang"]
        words = (self.label_box.text or "").strip()
        if words:
            q += "&label=" + window.encodeURIComponent(words)
        return "%s/_/api/embed.js?%s" % (self.origin, q)

    def _draw_button(self):
        self.button_opts.items = [{"key": k, "label": label, "choices": ch, "value": self.opts.get(k, "")} for k, label, ch in self.button_spec]
        src = self._button_src()
        self.button_code.text = '<script src="%s">%s' % (src, JS_END)
        for b in ("light", "dark"):
            getattr(self, "bg_" + b).classes["on"] = self.bg == b
        self.button_prev.classes["dark"] = self.bg == "dark"
        slot = self.dom_nodes["button_slot"]
        slot.innerHTML = ""
        tag = window.document.createElement("script")  # the real script draws the real button here
        setattr(tag, "src", src + "&preview=" + str(window.Date.now()))
        slot.appendChild(tag)

    def _opt(self, key, value, **event_args):
        self.opts[key] = value
        if key in ("style", "shape", "size"):
            state.store_set("rb" + key.capitalize(), value)
        self._draw_button()

    @handle("label_box", "lost_focus")
    def label_box_lost_focus(self, **event_args):
        self._draw_button()

    def bg_click(self, event):
        self.bg = event.currentTarget.getAttribute("data-b")
        self._draw_button()

    @handle("button_copy", "click")
    def button_copy_click(self, **event_args):
        pp.copy(self.button_code.text, "Reserve button code")

    def toc_click(self, event):
        event.preventDefault()
        el = window.document.getElementById(event.currentTarget.getAttribute("data-t"))
        if el:
            el.scrollIntoView({"behavior": "smooth", "block": "start"})
