from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import BookTemplate
from ... import i18n, pp, state

T = i18n.T


class Book(BookTemplate):
    """#book/<slug>[/<lang>]: the guest booking form. No account; works inside an iframe on the restaurant's website
    (and in the Reserve button's pop-up). Pick guests, date and time, then name, email, phone and the privacy tick."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.slug = args[0] if args else ""
        self.D = anvil.server.call("get_booking_form", self.slug, args[1] if len(args) > 1 else None)
        self.R = self.D.get("restaurant") or {}
        self.step = "pick"
        self.result: dict = {}
        i18n.set_lang(self.D.get("lang") or self.R.get("language") or "en")
        self.langs_panel.add_event_handler("x-chip", self._lang)
        self.embedded = window.self != window.top
        self.close_row.visible = self.embedded
        if self.D.get("ok") and self.R.get("accepting"):
            self.picker.setup(self.slug, self.D["days"], self.D.get("today"), self.R.get("max_party"))
        self._draw()

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        R, ok = self.R, bool(self.D.get("ok"))
        accepting = ok and bool(R.get("accepting"))
        langs = R.get("languages") or []
        self.langs_panel.visible = ok and len(langs) > 1
        self.langs_panel.items = [{"label": l.upper(), "value": l, "on": l == i18n.lang(), "title": i18n.NAMES.get(l, l)} for l in langs]
        self.masthead.visible = ok
        self.eyebrow.text = T("reserve")
        self.name_label.text = R.get("name") or ""
        self.desc_label.visible = bool(R.get("description"))
        self.desc_label.text = R.get("description") or ""
        self.problem_card.visible = not accepting
        if not ok:
            self.problem_title.text, self.problem_text.text = T("notFound"), self.D.get("error") or ""
            self.call_link.visible = False
        elif not accepting:
            self.problem_title.text, self.problem_text.text = "", T("closedOnline")
            self.call_link.visible = bool(R.get("phone"))
            self.call_label.text = "%s · %s" % (T("callUs"), R.get("phone") or "")
            state.set_attr(self.call_link, "href", "tel:" + (R.get("phone") or ""))
        self.pick_card.visible = accepting and self.step == "pick"
        self.details_card.visible = accepting and self.step == "details"
        self.done_card.visible = accepting and self.step == "done"
        self.note_label.visible = bool(R.get("form_note"))
        self.note_label.text = R.get("form_note") or ""
        self.next_button.text = T("details") + " →"
        self.next_button.enabled = bool(self.picker.time)
        self.big_label.text = T("bigGroup")
        if self.step == "details":
            self._draw_details()
        if self.step == "done":
            self._draw_done()
        # footer: address (map), phone, the menu
        self.map_link.visible = bool(R.get("address"))
        self.addr_label.text = R.get("address") or ""
        state.set_attr(self.map_link, "href", "https://www.openstreetmap.org/search?query=" + window.encodeURIComponent(R.get("address") or ""))
        self.tel_link.visible = bool(R.get("phone"))
        self.tel_label.text = R.get("phone") or ""
        state.set_attr(self.tel_link, "href", "tel:" + (R.get("phone") or ""))
        self.menu_link.visible = ok
        self.menu_label.text = T("menu")
        state.set_attr(self.menu_link, "href", pp.menu_url(self.slug))
        if self.embedded:
            state.set_attr(self.menu_link, "target", "_blank")
        if ok:
            window.document.title = T("reserve") + " · " + (R.get("name") or "")

    def _draw_details(self):
        p = self.picker
        self.summary_label.text = "%s · %s · %d %s" % (pp.fmt_date(p.date), p.time, p.party, T("guest") if p.party == 1 else T("guestsN"))
        self.back_button.text = T("change")
        self.details_h.text = T("details")
        self.name_cap.text, self.email_cap.text, self.phone_cap.text = T("name"), T("email"), T("phone")
        self.notes_cap.text = "%s (%s)" % (T("notes"), T("optional"))
        self.notes_box.placeholder = T("notesPh")
        consent = T("consent", link=T("privacyLink"), r=self.R.get("name") or "")
        self.consent_box.text = consent
        self.privacy_link.text = T("privacyLink")
        self.privacy_text.text = self.R.get("privacy_text") or ""
        self.submit_button.text = T("submitReview") if p.review else T("submit")

    def _draw_done(self):
        res, ok = self.result["reservation"], self.result["status"] == "confirmed"
        self.tick.classes["wait"] = not ok
        self.tick_icon.classes["ic-check"] = ok
        self.tick_icon.classes["ic-clock"] = not ok
        self.done_title.text = T("doneTitle") if ok else T("doneWait")
        self.f_date.text = pp.fmt_date(res["date"], "short")
        self.f_time.text, self.f_party.text = res["time"], str(res["party"])
        self.f_date_l.text, self.f_time_l.text, self.f_party_l.text = T("date"), T("time"), T("guests")
        self.done_text.text = T("doneText") if ok else T("waitText")
        self.manage_label.text = T("manage")
        state.set_attr(self.manage_link, "href", pp.manage_url(self.result["token"]))
        if self.embedded:
            state.set_attr(self.manage_link, "target", "_blank")
        self.copy_button.text, self.ics_button.text = T("copy"), T("calendar")

    # ---------------------------------------------------------------- language
    def _lang(self, value, **event_args):
        i18n.set_lang(value)
        if self.D.get("privacy") and self.D["privacy"].get(value):
            self.R["privacy_text"] = self.D["privacy"][value]
        if self.D.get("ok") and self.R.get("accepting"):
            self.picker.redraw()
        self._draw()

    # ---------------------------------------------------------------- steps
    @handle("picker", "change")
    def picker_change(self, **event_args):
        self.next_button.enabled = bool(self.picker.time)

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        if self.picker.time:
            self.step = "details"
            self._draw()
            self.name_box.focus()

    @handle("back_button", "click")
    def back_button_click(self, **event_args):
        self.step = "pick"
        self.error_label.visible = False
        self._draw()

    @handle("privacy_link", "click")
    def privacy_link_click(self, **event_args):
        self.privacy_text.visible = not self.privacy_text.visible

    @handle("submit_button", "click")
    def submit_button_click(self, **event_args):
        name, email, phone = (self.name_box.text or "").strip(), (self.email_box.text or "").strip(), (self.phone_box.text or "").strip()
        problem = None
        if not name or not email or not phone:
            problem = "%s, %s, %s" % (T("name"), T("email"), T("phone"))
        elif not self.consent_box.checked:
            problem = T("consent", link=T("privacyLink"), r=self.R.get("name") or "")
        if problem:
            self.error_label.visible, self.error_label.text = True, problem
            return
        p = self.picker
        data = {"date": p.date, "time": p.time, "party": p.party, "name": name, "email": email, "phone": phone,
                "notes": self.notes_box.text or "", "consent": True, "website": self.website_box.text or "", "language": i18n.lang()}
        self.submit_button.enabled = False
        try:
            r = anvil.server.call("book", self.slug, data)
        finally:
            self.submit_button.enabled = True
        if r and r.get("ok"):
            self.result, self.step = r, "done"
            self.error_label.visible = False
            self._draw()
            window.scrollTo(0, 0)
            return
        err = (r or {}).get("error") or "Something went wrong."
        self.error_label.visible, self.error_label.text = True, err
        if "taken" in err or "available" in err:
            self.step = "pick"
            self.picker.setup(self.slug, self.D["days"], self.D.get("today"), self.R.get("max_party"), p.party, p.date)
            self._draw()

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        """Inside a website's pop-up: ask the page to close it (the old PlanPlate pop-up listens for "close_div")."""
        window.parent.postMessage("close_div", "*")
        window.parent.postMessage({"planplate": "close"}, "*")

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        pp.copy(pp.manage_url(self.result["token"]), T("copied"))

    @handle("ics_button", "click")
    def ics_button_click(self, **event_args):
        window.PP.ics(self.result["reservation"], self.R, pp.manage_url(self.result["token"]))
