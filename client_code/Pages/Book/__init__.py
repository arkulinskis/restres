from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import BookTemplate
from ... import i18n, legal, pp, state

T = i18n.T


WINDOWS = (("lunch", "waitLunch"), ("dinner", "waitDinner"), ("any", "waitAny"))


def _is_date(text):
    t = str(text or "")
    return len(t) == 10 and t[4] == "-" and t[7] == "-" and (t[:4] + t[5:7] + t[8:]).isdigit()


class Book(BookTemplate):
    """#book/<slug>[/<lang>][/<YYYY-MM-DD>]: the guest booking form. No account; works inside an iframe on the
    restaurant's website (and in the Reserve button's pop-up). Pick guests, date and time, then name, email, phone.
    A date in the address opens that day (the "Fill a quiet night" share links). On a full day the picker offers the
    nearest days with room and, when the restaurant has it, the waitlist: step "wait" reuses the details card."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.slug = args[0] if args else ""
        rest = list(args[1:])
        lang = ([a for a in rest if a in i18n.TEXTS] or [None])[0]
        self.start_date = ([a for a in rest if _is_date(a)] or [None])[0]
        self.window = "any"
        self.D = anvil.server.call("get_booking_form", self.slug, lang)
        self.R = self.D.get("restaurant") or {}
        self.step = "pick"
        self.result: dict = {}
        i18n.set_lang(self.D.get("lang") or self.R.get("language") or "en")
        self.langs_panel.add_event_handler("x-chip", self._lang)
        self.embedded = window.self != window.top  # inside a website's iframe or the Reserve button's window (it has the only Close)
        pp.html_class("pp-embedded", self.embedded)
        self._a11y()
        self.window_panel.add_event_handler("x-chip", self._window)
        self.picker.waitlist = bool(self.D.get("waitlist"))
        if self.D.get("ok") and self.R.get("accepting"):
            self.picker.setup(self.slug, self.D["days"], self.D.get("today"), self.R.get("max_party"), date=self.start_date)
        self._draw()

    def _a11y(self):
        """What the screen reader and the browser's autofill need (WCAG AA)."""
        state.heading(self.name_label, 1)  # the restaurant's name is the page's main heading
        for cap in (self.name_cap, self.email_cap, self.phone_cap):  # required fields get a star (CSS .anvil-role-pp-req)
            cap.role = ["field-cap", "pp-req"]
        for box, kind in ((self.name_box, "name"), (self.email_box, "email"), (self.phone_box, "tel")):
            state.set_control_attr(box, "autocomplete", kind)
            state.set_control_attr(box, "aria-required", "true")
        # the hidden anti-spam box: out of the Tab order and away from autofill (a filled box blocks the booking)
        state.set_control_attr(self.website_box, "tabindex", "-1")
        state.set_control_attr(self.website_box, "autocomplete", "off")
        state.set_attr(self.done_title, "tabindex", "-1")

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        R, ok = self.R, bool(self.D.get("ok"))
        accepting = ok and bool(R.get("accepting"))
        langs = R.get("languages") or []
        self.langs_panel.visible = ok and len(langs) > 1
        self.langs_panel.items = [{"label": l.upper(), "value": l, "on": l == i18n.lang(), "title": i18n.NAMES.get(l, l),
                                   "aria": i18n.NAMES.get(l, l)} for l in langs]
        self.masthead.visible = ok
        self.kind_label.text = T("reserve")
        self.name_label.text = R.get("name") or ""
        self.desc_label.visible = bool(R.get("description"))
        self.desc_label.text = R.get("description") or ""
        self.desc_label.tooltip = R.get("description") or ""  # the header shows one line of it
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
        self.details_card.visible = accepting and self.step in ("details", "wait")
        self.done_card.visible = accepting and self.step in ("done", "waited")
        self.note_label.visible = bool(R.get("form_note"))
        self.note_label.text = R.get("form_note") or ""
        self.next_button.text = T("details") + " →"
        self.next_button.enabled = bool(self.picker.time)
        self.big_label.text = T("bigGroup")
        if self.step in ("details", "wait"):
            self._draw_details()
        if self.step == "done":
            self._draw_done()
        if self.step == "waited":
            self._draw_waited()
        # footer: address (map) and phone (no menu link here: the form is for booking)
        self.map_link.visible = bool(R.get("address"))
        self.addr_label.text = R.get("address") or ""
        state.set_attr(self.map_link, "href", "https://www.openstreetmap.org/search?query=" + window.encodeURIComponent(R.get("address") or ""))
        self.tel_link.visible = bool(R.get("phone"))
        self.tel_label.text = R.get("phone") or ""
        state.set_attr(self.tel_link, "href", "tel:" + (R.get("phone") or ""))
        if ok:
            window.document.title = T("reserve") + " · " + (R.get("name") or "")

    def _windows(self):
        """Lunch / Dinner only when that day has times then; Any time always."""
        times: list = [s["time"] for s in list((self.picker.slots or {}).get("slots") or [])]
        out = []
        for key, label in WINDOWS:
            if key == "any" or (key == "lunch" and any("11:00" <= x < "16:00" for x in times)) or (key == "dinner" and any(x >= "16:00" for x in times)):
                out.append((key, label))
        return out

    def _draw_details(self):
        p = self.picker
        waiting = self.step == "wait"
        party = "%d %s" % (p.party, T("guest") if p.party == 1 else T("guestsN"))
        if waiting:
            self.summary_label.text = "%s · %s · %s" % (T("waitTitle"), pp.fmt_date(p.date), party)
        else:
            self.summary_label.text = "%s · %s · %s" % (pp.fmt_date(p.date), p.time, party)
        self.wait_when.visible = waiting
        self.pp_news_row.visible = not waiting  # the waitlist sends no email: no news tick there
        if waiting:
            wins = self._windows()
            if self.window not in [k for k, _ in wins]:
                self.window = "any"
            self.wait_when_h.text = T("waitWhen")
            self.window_panel.items = [{"label": T(label), "value": key, "on": key == self.window, "group": "win"} for key, label in wins]
            self.wait_note.text = T("waitNote")
        self.back_button.text = T("change")
        self.details_h.text = T("details")
        self.req_note.text = "* " + T("required")
        self.name_cap.text, self.email_cap.text, self.phone_cap.text = T("name"), T("email"), T("phone")
        self.notes_cap.text = "%s (%s)" % (T("notes"), T("optional"))
        self.notes_box.placeholder = T("notesPh")
        name = self.R.get("name") or ""
        ppt = self._pp()
        # one line instead of two required ticks (2026-11-19): a booking needs the guest informed, not a tick
        self.accept_label.text = (ppt.get("consent") or "").replace("{r}", name)
        self.privacy_link.text = (ppt.get("notice") or T("privacyLink")).replace("{r}", name)
        self.privacy_text.text = self.R.get("privacy_text") or ""
        self.pp_policy_link.text = ppt.get("policy") or ""
        self.pp_news_box.text = ppt.get("news") or ""  # optional and never pre-ticked (EU law)
        self.submit_button.text = T("waitJoin") if waiting else (T("submitReview") if p.review else T("submit"))

    def _pp(self):
        """PlanPlate's own consent texts (GuestNews.TEXT on the server) in the form's language."""
        texts: dict = self.D.get("pp") or {}
        return texts.get(i18n.lang()) or texts.get("en") or {}

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

    def _draw_waited(self):
        """After joining the waitlist: nothing is booked, the restaurant will be in touch."""
        res: dict = self.result
        self.tick.classes["wait"] = True
        self.tick_icon.classes["ic-check"] = False
        self.tick_icon.classes["ic-clock"] = True
        self.done_title.text = T("waitDoneTitle")
        self.f_date.text = pp.fmt_date(res["date"], "short")
        self.f_time.text = T(dict(WINDOWS).get(res.get("window") or "any", "waitAny"))
        self.f_party.text = str(res["party"])
        self.f_date_l.text, self.f_time_l.text, self.f_party_l.text = T("date"), T("time"), T("guests")
        self.done_text.text = T("waitDone", d=pp.fmt_date(res["date"]), p=res.get("_phone") or "")
        for part in (self.manage_link, self.copy_button, self.ics_button):
            part.visible = False
        self.again_button.visible = True
        self.again_button.text = T("waitAgain")

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
        self.pick_error.visible = False

    @handle("picker", "waitlist")
    def picker_waitlist(self, **event_args):
        """ "Join the waitlist" in the picker: the details card, without a time."""
        if self.picker.date:
            self.step = "wait"
            self.pick_error.visible = False
            self._draw()
            self.name_box.focus()

    def _window(self, value, **event_args):
        self.window = value or "any"
        self._draw_details()

    @handle("again_button", "click")
    def again_button_click(self, **event_args):
        self.step, self.result = "pick", {}
        for part in (self.manage_link, self.copy_button, self.ics_button):
            part.visible = True
        self.again_button.visible = False
        self._draw()
        state.focus(self.next_button)

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        if self.picker.time:
            self.step = "details"
            self._draw()
            self.name_box.focus()

    @handle("back_button", "click")
    def back_button_click(self, **event_args):
        self.step = "pick"
        self.error_label.visible = self.pick_error.visible = False
        self._draw()
        state.focus(self.next_button)

    @handle("privacy_link", "click")
    def privacy_link_click(self, **event_args):
        self.privacy_text.visible = not self.privacy_text.visible

    @handle("pp_policy_link", "click")
    def pp_policy_link_click(self, **event_args):
        legal.open("privacy")

    @handle("submit_button", "click")
    def submit_button_click(self, **event_args):
        name, email, phone = (self.name_box.text or "").strip(), (self.email_box.text or "").strip(), (self.phone_box.text or "").strip()
        problem = None
        missing = [(box, label) for box, label, v in ((self.name_box, T("name"), name), (self.email_box, T("email"), email),
                                                     (self.phone_box, T("phone"), phone)) if not v]
        for box in (self.name_box, self.email_box, self.phone_box):
            state.set_control_attr(box, "aria-invalid", "true" if any(b is box for b, _ in missing) else None)
        if missing:
            problem = T("fillIn", f=", ".join(label for _, label in missing))
            missing[0][0].focus()
        if problem:
            self.error_label.visible, self.error_label.text = True, problem
            return
        p = self.picker
        if self.step == "wait":
            self._join_waitlist(name, email, phone)
            return
        data = {"date": p.date, "time": p.time, "party": p.party, "name": name, "email": email, "phone": phone,
                "notes": self.notes_box.text or "", "consent": True, "pp_consent": True, "pp_news": bool(self.pp_news_box.checked),
                "website": self.website_box.text or "", "language": i18n.lang()}
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
            getattr(anvil.js.get_dom_node(self.done_title), "focus")()  # screen readers start at "Your table is booked"
            return
        err = (r or {}).get("error") or "Something went wrong."
        self.error_label.visible, self.error_label.text = True, err
        if "taken" in err or "available" in err:
            self.step = "pick"
            self.picker.setup(self.slug, self.D["days"], self.D.get("today"), self.R.get("max_party"), p.party, p.date)
            self._draw()
            self.pick_error.visible, self.pick_error.text = True, err  # the details card is hidden now: say it here

    def _join_waitlist(self, name, email, phone):
        p = self.picker
        data = {"date": p.date, "party": p.party, "window": self.window, "name": name, "email": email, "phone": phone,
                "notes": self.notes_box.text or "", "pp_consent": True, "website": self.website_box.text or "",
                "language": i18n.lang()}
        self.submit_button.enabled = False
        try:
            r = anvil.server.call("join_waitlist", self.slug, data)
        finally:
            self.submit_button.enabled = True
        if r and r.get("ok"):
            self.result, self.step = dict(r, _phone=phone), "waited"
            self.error_label.visible = False
            self._draw()
            window.scrollTo(0, 0)
            getattr(anvil.js.get_dom_node(self.done_title), "focus")()
            return
        self.error_label.visible, self.error_label.text = True, (r or {}).get("error") or "Something went wrong."

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        pp.copy(pp.manage_url(self.result["token"]), T("copied"))

    @handle("ics_button", "click")
    def ics_button_click(self, **event_args):
        window.PP.ics(self.result["reservation"], self.R, pp.manage_url(self.result["token"]))
