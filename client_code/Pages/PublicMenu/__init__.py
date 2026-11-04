from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import PublicMenuTemplate
from ... import i18n, pp, state

T = i18n.T


class PublicMenu(PublicMenuTemplate):
    """#menu/<slug>: the restaurant's menu for guests (what the table QR code opens). Always the live menu."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        state.heading(self.name_label, 1)  # the restaurant's name is the main heading
        self.slug = args[0] if args else ""
        self.D = anvil.server.call("get_menu", self.slug)
        R = self.D.get("restaurant") or {}
        i18n.set_lang(R.get("language") or "en")
        self.langs_panel.add_event_handler("x-chip", self._lang)
        self._draw()

    def _draw(self):
        D, R = self.D, self.D.get("restaurant") or {}
        ok = bool(D.get("ok"))
        langs = R.get("languages") or []
        self.langs_panel.visible = ok and len(langs) > 1
        self.langs_panel.items = [{"label": l.upper(), "value": l, "on": l == i18n.lang(), "title": i18n.NAMES.get(l, l),
                                   "aria": i18n.NAMES.get(l, l)} for l in langs]
        self.eyebrow.text = T("menu")
        if not ok:
            self.name_label.text, self.desc_label.text = T("menuNotFound"), D.get("error") or ""
            self.sections_panel.items, self.cta.visible, self.legend_label.visible = [], False, False
            return
        self.name_label.text = R["name"]
        self.desc_label.visible = bool(R.get("description"))
        self.desc_label.text = R.get("description") or ""
        files = [f for f in D.get("files") or [] if not f["language"] or f["language"] == i18n.lang()]
        self.files_box.visible = bool(files)
        self.files_panel.items = files
        self.sections_panel.items = D["sections"]
        self.empty_label.visible = not D["sections"] and not files
        self.empty_label.text = T("menuSoon")
        used = sorted({t for s in D["sections"] for i in s["items"] for t in i["tags"]})
        self.legend_label.visible = bool(used)
        self.legend_label.text = " · ".join("%s %s" % (t, D["tags"].get(t, "")) for t in used)
        self.cta.visible = bool(R.get("accepting"))
        self.book_label.text = T("reserve")
        state.set_attr(self.book_link, "href", pp.book_url(self.slug))
        window.document.title = "%s · %s" % (T("menu"), R["name"])

    def _lang(self, value, **event_args):
        i18n.set_lang(value)
        self._draw()
