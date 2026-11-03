"""Page addresses: #name/arg1/arg2 -> a page Form (open_form), with sign-in rules.

Links in templates are plain <a href="#dashboard">; code calls router.go("hours", rid).

    PAGES[name] = (who may open it, browser-tab title)   who: None = anyone, "guest" = signed out only, "user", "admin"
    NAV = the main menu (header + phone tab bar, signed-in people): (page, label, icon). At most 4.
    PUBLIC = guest pages without the app's header and footer (the booking form is embedded in restaurants' websites).
    RESTAURANT = per-restaurant pages, #<page>/<restaurant id>[/more]; their tabs are in Components/RestaurantNav.
The guest addresses are the same as before the Forms rebuild (#book/<slug>[/<lang>], #r/<token>, #menu/<slug>), so
links in emails, QR codes and websites keep working.
"""
import anvil
import anvil.js
from anvil.js import window

from . import state

PAGES = {
    "landing": (None, "Restaurant reservations, made simple"),
    "auth": ("guest", "Sign in"),
    "dashboard": ("user", "Your restaurants"),
    "today": ("user", "Today"),
    "reservations": ("user", "Reservations"),
    "guests": ("user", "Guests"),
    "hours": ("user", "Opening hours"),
    "tables": ("user", "Tables & layout"),
    "events": ("user", "Events"),
    "dishes": ("user", "Menu"),
    "gallery": ("user", "Gallery"),
    "website": ("user", "Website"),
    "share": ("user", "Share & QR codes"),
    "settings": ("user", "Settings"),
    "profile": ("user", "Your profile"),
    "admin": ("admin", "Admin"),
    "book": (None, "Book a table"),
    "r": (None, "Your reservation"),
    "menu": (None, "Menu"),
}
NAV = [("dashboard", "Restaurants", "grid")]
PUBLIC = ("book", "r", "menu")
RESTAURANT = ("today", "reservations", "guests", "hours", "tables", "events", "dishes", "gallery", "website", "share", "settings")
APP_NAME = "PlanPlate"
_r: dict = {"after": "", "listening": False, "page": ""}


def _form(name):
    """The page's Form class (imported when first needed, so start-up and the booking form stay quick)."""
    if name == "landing":
        from .Pages.Landing import Landing
        return Landing
    if name == "auth":
        from .Pages.Auth import Auth
        return Auth
    if name == "dashboard":
        from .Pages.Dashboard import Dashboard
        return Dashboard
    if name == "today":
        from .Pages.Today import Today
        return Today
    if name == "reservations":
        from .Pages.Reservations import Reservations
        return Reservations
    if name == "guests":
        from .Pages.Guests import Guests
        return Guests
    if name == "hours":
        from .Pages.Hours import Hours
        return Hours
    if name == "tables":
        from .Pages.Tables import Tables
        return Tables
    if name == "events":
        from .Pages.Events import Events
        return Events
    if name == "dishes":
        from .Pages.Dishes import Dishes
        return Dishes
    if name == "gallery":
        from .Pages.Gallery import Gallery
        return Gallery
    if name == "website":
        from .Pages.Website import Website
        return Website
    if name == "share":
        from .Pages.Share import Share
        return Share
    if name == "settings":
        from .Pages.Settings import Settings
        return Settings
    if name == "profile":
        from .Pages.Profile import Profile
        return Profile
    if name == "book":
        from .Pages.Book import Book
        return Book
    if name == "r":
        from .Pages.Manage import Manage
        return Manage
    if name == "menu":
        from .Pages.PublicMenu import PublicMenu
        return PublicMenu
    from .Pages.Admin import Admin
    return Admin


def parse(hash_text):
    h = (hash_text or "").lstrip("#").lstrip("!").lstrip("/").split("?")[0]
    parts = [window.decodeURIComponent(p) for p in h.split("/") if p]
    return (parts[0] if parts else ""), parts[1:]


def href(name, *args):
    """'#name/arg1/arg2' with every part URL-encoded (row ids contain brackets and commas)."""
    return "#" + "/".join([name] + [window.encodeURIComponent(str(a)) for a in args if a not in (None, "")])


def home_page():
    return "dashboard" if state.me() else "landing"


def current():
    return _r["page"]


def show():
    """Open the page for the current address."""
    name, args = parse(window.location.hash)
    if name not in PAGES:
        name, args = home_page(), []
    who = PAGES[name][0]
    if name == "landing" and state.me():
        name, args = "dashboard", []
    if who == "guest" and state.me():
        name, args = "dashboard", []
    elif who in ("user", "admin") and not state.me():
        _r["after"] = window.location.hash
        name, args = "auth", []
    elif who == "admin" and not state.is_admin():
        state.toast("That page is for admins only.", "error")
        name, args = "dashboard", []
    if name in RESTAURANT and not args:
        name, args = "dashboard", []
    _r["page"] = name
    window.document.title = PAGES[name][1] + " · " + APP_NAME
    root = window.document.documentElement
    if root is not None:
        root.classList.toggle("pp-public", name in PUBLIC)
    window.UI_READY = False
    page = _form(name)(args=args)
    anvil.open_form(page)
    shell = getattr(page, "layout", None)
    if shell is not None and hasattr(shell, "refresh"):
        shell.refresh(name)  # Anvil reuses the layout between pages: tell it who is signed in and which page is open
    window.scrollTo(0, 0)
    window.UI_READY = True  # tests and screenshots wait for this


def go(name, *args):
    """Go to a page. Same address again = reload the page."""
    target = href(name, *args)
    if window.location.hash == target:
        show()
    else:
        window.location.hash = target


def replace(name, *args):
    """Change the address without opening anything (a page that switches its own view)."""
    window.history.replaceState(None, "", href(name, *args))


def after_sign_in():
    """Where to go once someone signs in: the page they were heading for, or their restaurants."""
    target = _r["after"]
    _r["after"] = ""
    if target and target != window.location.hash:
        window.location.hash = target
    else:
        go("dashboard")


def remember_after(target):
    _r["after"] = target


def _on_hash(event):
    show()


def start():
    if not _r["listening"]:
        window.addEventListener("hashchange", anvil.js.report_exceptions(_on_hash))
        _r["listening"] = True
    show()
