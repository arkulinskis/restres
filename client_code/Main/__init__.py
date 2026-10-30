# Main — Custom HTML form, the Startup Form. HTML: forms/Main.html
# Three ways in, chosen by the URL hash:
#   #book/<slug>[/<lang>]  the public booking form (no account; embeddable in an iframe)
#   #r/<token>             a guest's reservation page (no account; the token is the key)
#   #menu/<slug>           the public menu (what the menu QR code opens)
#   anything else  the manager portal (sign-in required)
import json

from ._anvil_designer import MainTemplate
from anvil import *
import anvil
import anvil.server
import anvil.users
import anvil.js

from .. import pp_ui, legal
from ..AuthPage import AuthPage
from ..DashboardPage import DashboardPage
from ..TodayPage import TodayPage
from ..EventsPage import EventsPage
from ..GalleryPage import GalleryPage
from ..SitePage import SitePage
from ..ReservationsPage import ReservationsPage
from ..HoursPage import HoursPage
from ..TablesPage import TablesPage
from ..MenuEditPage import MenuEditPage
from ..MenuPage import MenuPage
from ..SettingsPage import SettingsPage
from ..BookPage import BookPage
from ..ManagePage import ManagePage

PAGES = {
    "auth": AuthPage,
    "dashboard": DashboardPage,
    "today": TodayPage,
    "reservations": ReservationsPage,
    "hours": HoursPage,
    "tables": TablesPage,
    "events": EventsPage,
    "menu": MenuEditPage,
    "gallery": GalleryPage,
    "website": SitePage,
    "settings": SettingsPage,
}

RESTAURANT_PAGES = ("today", "reservations", "hours", "tables", "events", "menu", "gallery", "website", "settings")


def _route():
    h = anvil.get_url_hash()
    h = h if isinstance(h, str) else ""
    if h.startswith("book/"):
        return "book", h[5:].strip("/")
    if h.startswith("r/"):
        return "manage", h[2:].strip("/")
    if h.startswith("menu/"):
        return "menu", h[5:].strip("/")
    return "portal", None


class Main(MainTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.header = None
        self.me = None
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        if self.header is not None:
            return
        kind, key = _route()
        if kind != "portal":
            anvil.js.window.document.documentElement.classList.add("pp-public")
            self.header = False
            if kind == "book":
                slug, _, lang = key.partition("/")
                self.add_component(BookPage(slug=slug, lang=lang or None))
            elif kind == "menu":
                self.add_component(MenuPage(slug=key))
            else:
                self.add_component(ManagePage(token=key))
            return
        self.header = pp_ui.mount(self, "header", {}, self._on_header_event)
        if anvil.users.get_user():
            self.signed_in()
        else:
            self.go("auth")

    # ---- navigation (pages call get_open_form().go(...)) ----
    def go(self, page, **kwargs):
        if page != "auth" and not anvil.users.get_user():
            page, kwargs = "auth", {}
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        if page in RESTAURANT_PAGES and not kwargs.get("restaurant_id"):
            page, kwargs = "dashboard", {}
        self.clear()
        self.add_component(PAGES[page](**kwargs))
        self.header.setActive(page)
        pp_ui.scroll_top()

    def signed_in(self):
        self.me = anvil.server.call("get_me")
        self.header.setUser(json.dumps(self.me))
        self.go("dashboard")
        legal.refresh_soon()  # Privacy & Terms: records the sign-up tick, or reminds people to review

    def refresh_alerts(self, alerts=None):
        alerts = alerts or anvil.server.call("get_alerts")
        if self.header:
            self.header.setAlerts(json.dumps(alerts))

    def sign_out(self):
        anvil.users.logout()
        self.me = None
        legal.signed_out()
        self.header.setUser(None)
        self.go("auth")

    def _on_header_event(self, event, payload):
        if event == "nav":
            self.go(payload.get("page", "dashboard"))
        elif event == "open_alert":
            self.go("reservations", restaurant_id=payload.get("restaurant_id"), day=payload.get("date"))
        elif event == "poll":
            try:
                return anvil.server.call_s("get_alerts")
            except Exception:
                return None
        elif event == "signout":
            self.sign_out()
