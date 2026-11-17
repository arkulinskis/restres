from anvil import *
from anvil.js import window

from ._anvil_designer import HowToTemplate
from ... import howto_content as C
from ... import router, state

# which sections each audience filter shows (the "who" of every section is set in docs/howto/guide.json)
SHOWS = {"all": None,
         "manager": ("Everyone", "Owners and managers", "Managers"),
         "staff": ("Everyone", "Staff")}


def _esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class HowTo(HowToTemplate):
    """#howto[/<section id>]: the how-to guide with screenshots, for managers and staff. The words and pictures are
    generated into howto_content.py by `tools/howto/howto.py build` from docs/howto (never edited here). The restaurant
    pages link to their own section (Components/RestaurantNav)."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.target = args[0] if args else ""
        self.who = "all"
        try:
            self.who = window.UI.store.get("howtoWho") or "all"  # remembered per browser
        except Exception:
            pass
        if self.who not in SHOWS:
            self.who = "all"
        self.dom_nodes["lead"].textContent = C.SUBTITLE
        self.dom_nodes["toc"].addEventListener("click", self._toc_click)
        self._draw()
        if self.target:  # the router scrolls to the top after opening a page: jump to the section just after that
            window.setTimeout(lambda: self._jump(self.target, False), 350)

    def _sections(self):
        keep = SHOWS[self.who]
        out = [s for s in C.SECTIONS if keep is None or s["who"] in keep]
        if self.target and not any(s["id"] == self.target for s in out):  # a deep link always shows its section
            out = [s for s in C.SECTIONS if keep is None or s["who"] in keep or s["id"] == self.target]
        return out

    def _draw(self):
        for k in SHOWS:
            getattr(self, "who_" + k).classes["on"] = k == self.who
            state.set_attr(getattr(self, "who_" + k), "aria-pressed", "true" if k == self.who else "false")
        secs = self._sections()
        self.dom_nodes["toc"].innerHTML = '<h2>Contents</h2><ol>%s</ol>' % "".join(
            '<li><a href="#howto/%s" data-to="%s">%s</a></li>' % (s["id"], s["id"], _esc(s["title"])) for s in secs)
        self.dom_nodes["body"].innerHTML = "".join(
            '<section id="howto-%s" class="pp-howto-sec"><div class="pp-howto-sec-head"><h2>%s</h2><span class="ui-badge brand">%s</span></div>%s</section>'
            % (s["id"], _esc(s["title"]), _esc(s["who"]), s["html"]) for s in secs)

    def who_click(self, event):
        self.who = event.currentTarget.getAttribute("data-who")
        try:
            window.UI.store.set("howtoWho", self.who)
        except Exception:
            pass
        self._draw()

    def _toc_click(self, event):
        a = event.target.closest("a[data-to]")
        if a is None:
            return
        event.preventDefault()
        self._jump(a.getAttribute("data-to"), True)

    def _jump(self, sid, smooth):
        el = window.document.getElementById("howto-" + sid)
        if el is None:
            return
        router.replace("howto", sid)  # the address names the section (shareable), without reopening the page
        el.scrollIntoView({"behavior": "smooth" if smooth else "auto", "block": "start"})
