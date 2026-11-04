"""PlanPlate's shared client helpers: the restaurant tabs and roles, dates and times, links, QR codes, the clipboard,
and photo/video uploads. The browser-only parts live in theme/assets/pp-kit.js (window.PP)."""
import json

import anvil.js
import anvil.server
from anvil.js import window

from . import state

# [page, label, icon, lowest role that sees it]
TABS = [("today", "Today", "sun", "staff"), ("reservations", "Reservations", "calendar", "staff"),
        ("guests", "Guests", "users", "staff"), ("hours", "Opening hours", "clock", "manager"),
        ("tables", "Tables & layout", "table", "manager"), ("events", "Events", "star", "manager"),
        ("dishes", "Menu", "list", "manager"), ("gallery", "Gallery", "image", "manager"),
        ("website", "Website", "globe", "manager"), ("share", "Share & QR", "qr", "manager"),
        ("settings", "Settings", "cog", "manager")]
RANK = {"staff": 1, "manager": 2, "owner": 3}
ROLE = {"owner": "Owner", "manager": "Manager", "staff": "Staff"}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS3 = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
STATUS = {"pending": "Awaiting approval", "confirmed": "Confirmed", "declined": "Declined", "cancelled": "Cancelled",
          "seated": "Seated", "done": "Finished", "no_show": "No-show"}
STATUS_ROLE = {"pending": "badge-warn", "confirmed": "badge-good", "declined": "badge-bad", "cancelled": "badge",
               "seated": "badge-brand", "done": "badge", "no_show": "badge-bad"}
SOURCE = {"online": "Online", "phone": "Phone", "walk_in": "Walk-in", "staff": "Staff"}


def can(role, need):
    return RANK.get(role or "owner", 3) >= RANK[need]


def kit():
    return window.PP


def time_input(*boxes):
    """Give TextBoxes the browser's time picker (Anvil's TextBox has no "time" type)."""
    for box in boxes:
        node = anvil.js.get_dom_node(box)
        el = node if node.tagName == "INPUT" else node.querySelector("input")
        if el is not None:
            el.setAttribute("type", "time")


def html_class(name, on=True):
    """Add or remove a class on <html> (printing modes)."""
    root = window.document.documentElement
    if root is not None:
        root.classList.toggle(name, bool(on))


def setup():
    """Toasts raised inside pp-kit.js (copy, QR downloads) show as the app's own notifications."""
    window.PP.toastHook = lambda msg, err: state.toast(msg, "error" if err else None)


# ---------------------------------------------------------------- dates (all "YYYY-MM-DD", the restaurant's local time)
def add_days(iso, n):
    return window.PP.addDays(iso, n)


def weekday(iso):
    return int(window.PP.weekday(iso))


def fmt_date(iso, style="long"):
    """'Friday 14 November' (long), 'Fri 14 Nov' (short)."""
    if not iso:
        return ""
    return window.PP.fmtShort(iso) if style == "short" else window.PP.fmtDate(iso)


def to_min(hm):
    h, m = str(hm).split(":")
    return int(h) * 60 + int(m)


def hm(minutes):
    return "%02d:%02d" % (int(minutes) // 60, int(minutes) % 60)


def hours_text(intervals):
    return ", ".join("%s–%s" % (a, b) for a, b in intervals) if intervals else "Closed"


def today_iso():
    return window.PP.isoDate(window.Date())


# ---------------------------------------------------------------- links
def app_url():
    return window.PP.appUrl()


def book_url(slug, lang=None):
    return window.PP.bookUrl(slug) + ("/" + lang if lang else "")


def menu_url(slug):
    return window.PP.menuUrl(slug)


def manage_url(token):
    return window.PP.manageUrl(token)


def site_url(path):
    return window.PP.siteBase() + path


def copy(text, label="Copied"):
    window.PP.copy(text, label)


def qr_svg(text, px=180):
    return window.PP.qrSvg(text, px)


def qr_png(text, filename, caption=""):
    window.PP.qrPng(text, filename, caption or None)


def browser_tz():
    return window.PP.browserTz()


# ---------------------------------------------------------------- the time-zone search field (pp-kit.js draws it)
def tz_field_html(name, value, field_id):
    return window.PP.tzField(name, value, field_id)


def tz_label(zone):
    return window.PP.tzLabel(zone)


# ---------------------------------------------------------------- photos and videos
def _call(name, *args):
    try:
        return anvil.server.call(name, *args)
    except Exception as e:  # PermissionDenied and friends: show them like any expected problem
        return {"ok": False, "error": str(e) or "That didn't work."}


def media_emitter(rid):
    """The function pp-kit.js's PP.upload calls for each step (media_ticket, media_register, media_upload, media_video)."""

    def emit(event, payload_json):
        p = json.loads(payload_json) if payload_json else {}
        if event == "media_ticket":
            return _call("media_ticket", rid, p.get("kind") or "image")
        if event == "media_register":
            return _call("register_upload", rid, p.get("info"), p.get("meta"))
        if event == "media_upload":
            return _call("upload_photo", rid, p)
        if event == "media_video":
            media = anvil.js.to_media(window.PP._file)  # the File the browser picked, sent as Anvil Media (not JSON)
            window.PP._file = None
            return _call("upload_video", rid, media, p)
        return None

    return emit


def upload(rid, accept="image/*", multiple=False, meta=None, progress=None):
    """Let the person pick photo(s) or a video and upload them (Cloudinary when set up, else PlanPlate).
    Returns a list of {ok, photo | error, name} (empty if they cancelled). Blocks until done."""
    on_each = None
    if progress is not None:
        def on_each(i, n, name):
            progress(int(i), int(n), name)
    res = anvil.js.await_promise(window.PP.pickAndUpload(accept, multiple, media_emitter(rid), meta or {}, on_each))
    out = []
    for r in res:
        out.append({"ok": bool(r.ok), "photo": _plain(r.photo) if r.ok else None, "error": r.error if not r.ok else None,
                    "name": r.name})
    return out


def _plain(js_obj):
    """A JS object coming back from pp-kit.js -> a Python dict (through JSON)."""
    return json.loads(window.JSON.stringify(js_obj)) if js_obj else None


def thumb(photo):
    """The small picture URL of a photo view (or '' for none)."""
    if not photo:
        return ""
    return photo.get("thumb_url") or photo.get("poster_url") or ("" if photo.get("kind") == "video" else photo.get("url") or "")
