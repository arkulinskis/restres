import json

from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import FillNightTemplate
from ... import i18n, pp, state


class FillNight(FillNightTemplate):
    """Fill a quiet night (Today -> The week ahead -> Fill it, managers). A 1080x1920 story image (window.PP.storyPng:
    the name, "Tables free tonight", the free times, a QR code, the photo of the day when there is one) with a caption
    in each of the restaurant's languages, and Share (the phone's share sheet) / Download / Copy text / WhatsApp /
    Copy link. Every link opens the booking form on that date (#book/<slug>/<lang>/<date>). Closes with None."""

    def __init__(self, rid, date, **properties):
        super().__init__(**properties)
        self.rid, self.date = rid, date
        self.K: dict = {}
        self.lang = "en"
        self.png = ""
        self.captions: dict = {}  # the manager's own edits, per language
        self._loaded = False
        self.grid.visible = False
        self.langs_panel.add_event_handler("x-chip", self._lang)
        state.set_attr(self.story_img, "alt", "The story image to share")

    @handle("", "show")
    def form_show(self, **event_args):
        if not self._loaded:
            self._loaded = True
            self._load()

    def _load(self):
        try:
            k = anvil.server.call_s("get_fill_kit", self.rid, self.date)
        except Exception:
            k = {"ok": False, "error": "The share kit didn't load. Check the connection and try again."}
        if not k or not k.get("ok"):
            self._fail((k or {}).get("error") or "Something went wrong.")
            return
        self.K = k
        self.lang = k["language"] if k["language"] in k["texts"] else k["languages"][0]
        day = "tonight" if k["date"] == k["today"] else ("tomorrow" if k["date"] == pp.add_days(k["today"], 1) else pp.DAYS[pp.weekday(k["date"])])
        self.title_label.text = "Fill %s" % day if day in ("tonight", "tomorrow") else "Fill %s night" % day
        self.seats_badge.visible = bool(k["seats"])
        self.seats_badge.text = "%d of %d seats booked" % (k["covers"], k["seats"])
        if not k["times"]:
            self._fail("No free times left on %s: every time is booked or already over." % pp.fmt_date(k["date"]))
            return
        self.lead_label.text = ("Post it as a story on Instagram or Facebook, or send it on WhatsApp. The QR code and the link "
                                "open your booking form on %s." % pp.fmt_date(k["date"]))
        four = len(k.get("four") or [])
        self.times_label.text = "Free for 2 at %s.%s" % (", ".join(k["times"][:10]) + (" and more" if len(k["times"]) > 10 else ""),
                                                        " %d of those times also seat 4." % four if four else " No table for 4 is left.")
        self._draw()

    def _fail(self, msg):
        self.loading_label.visible = False
        self.grid.visible = False
        self.message.visible, self.message.text = True, msg

    def _texts(self) -> dict:
        texts: dict = self.K.get("texts") or {}
        return texts.get(self.lang) or {}

    def _draw(self):
        k, t = self.K, self._texts()
        langs: list = list(k.get("languages") or [])
        self.langs_panel.visible = len(langs) > 1
        self.langs_panel.items = [{"label": l.upper(), "value": l, "on": l == self.lang, "group": "lang",
                                   "aria": i18n.NAMES.get(l, l)} for l in langs]
        self.caption_box.text = self.captions.get(self.lang) or t.get("caption") or ""
        self.loading_label.visible = True
        self.loading_label.text = "Drawing your story…"
        photo = k.get("photo") or {}
        times = [x.replace(":", "h") if self.lang == "fr" else x for x in k.get("shown") or []]
        date_text = window.PP.parseDate(k["date"]).toLocaleDateString(i18n.LOCALES.get(self.lang, "en-GB"),
                                                                       {"weekday": "long", "day": "numeric", "month": "long"})
        opts = {"name": k["name"], "h1": t.get("h1"), "h2": t.get("h2"), "dateText": date_text, "times": times,
                "scan": t.get("scan"), "sub": t.get("sub"), "by": t.get("by"), "link": t.get("link"),
                "photo": photo.get("url") or None}
        try:
            self.png = window.PP.storyPng(window.JSON.parse(json.dumps(opts)))  # a JS promise: Python gets the value
        except Exception:
            self.png = ""
        self.loading_label.visible = False
        if not self.png:
            self._fail("The image couldn't be drawn in this browser. The caption and link still work: copy them below.")
            self.grid.visible = True
            return
        state.set_attr(self.story_img, "src", self.png)
        self.grid.visible = True

    def _lang(self, value, **event_args):
        self.captions[self.lang] = self.caption_box.text or ""
        self.lang = value
        self._draw()

    def _caption(self):
        return (self.caption_box.text or "").strip() or self._texts().get("caption") or ""

    def _file(self):
        return "%s-%s.png" % (self.K.get("slug") or "planplate", self.date)

    @handle("caption_box", "change")
    def caption_box_change(self, **event_args):
        self.captions[self.lang] = self.caption_box.text or ""

    @handle("share_button", "click")
    def share_button_click(self, **event_args):
        if not self.png:
            pp.copy(self._caption(), "Caption")
            return
        how = window.PP.shareFile(self.png, self._caption(), self._file())
        if how == "shared":
            state.toast("Shared", "ok")

    @handle("download_button", "click")
    def download_button_click(self, **event_args):
        if self.png:
            window.PP.downloadUrl(self.png, self._file())

    @handle("copy_text_button", "click")
    def copy_text_button_click(self, **event_args):
        pp.copy(self._caption(), "Caption")

    @handle("whatsapp_button", "click")
    def whatsapp_button_click(self, **event_args):
        window.open("https://wa.me/?text=" + window.encodeURIComponent(self._caption()), "_blank", "noopener")

    @handle("copy_link_button", "click")
    def copy_link_button_click(self, **event_args):
        pp.copy(self._texts().get("link") or "", "Booking link")

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
