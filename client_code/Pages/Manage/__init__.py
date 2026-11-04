from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import ManageTemplate
from ... import i18n, pp, state

T = i18n.T
LIVE = ("pending", "confirmed")
BADGE = {"pending": "badge-warn", "confirmed": "badge-good", "declined": "badge-bad", "cancelled": "badge", "seated": "badge-brand",
         "done": "badge", "no_show": "badge-bad"}


class Manage(ManageTemplate):
    """#r/<token>: a guest's own reservation. No account: the token in the link is the key. See it, change the date,
    time, party or details, cancel it, or add it to a calendar."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.token = args[0] if args else ""
        self.D = anvil.server.call("get_reservation", self.token)
        self.mode = "view"
        r = self.D.get("reservation") or {}
        i18n.set_lang(r.get("language") or "en")
        self.langs_panel.add_event_handler("x-chip", self._lang)
        self._draw()

    def _draw(self):
        D, ok = self.D, bool(self.D.get("ok"))
        R, r = D.get("restaurant") or {}, D.get("reservation") or {}
        langs = R.get("languages") or []
        self.langs_panel.visible = ok and len(langs) > 1
        self.langs_panel.items = [{"label": l.upper(), "value": l, "on": l == i18n.lang(), "title": i18n.NAMES.get(l, l)} for l in langs]
        self.masthead.visible = ok
        self.name_label.text = R.get("name") or ""
        self.addr_label.text = R.get("address") or ""
        self.problem_card.visible = not ok
        if not ok:
            self.problem_title.text, self.problem_text.text = T("badLink"), D.get("error") or ""
        self.view_part.visible = ok and self.mode == "view"
        self.change_part.visible = ok and self.mode == "change"
        self.tel_link.visible = ok and bool(R.get("phone"))
        self.tel_label.text = R.get("phone") or ""
        state.set_attr(self.tel_link, "href", "tel:" + (R.get("phone") or ""))
        self.mail_link.visible = ok and bool(R.get("email"))
        self.mail_label.text = R.get("email") or ""
        state.set_attr(self.mail_link, "href", "mailto:" + (R.get("email") or ""))
        if not ok:
            return
        window.document.title = T("yourRes") + " · " + R.get("name", "")
        st = r["status"]
        live = st in LIVE
        self.status_card.classes["gone"] = st in ("cancelled", "declined", "no_show")
        self.status_badge.text = T("bd_" + st)
        self.status_badge.role = ["badge", BADGE.get(st, "badge")]
        self.your_label.text, self.lead_label.text = T("yourRes"), T("st_" + st)
        self.f_date.text, self.f_time.text, self.f_party.text = pp.fmt_date(r["date"], "short"), r["time"], str(r["party"])
        self.f_date_l.text, self.f_time_l.text, self.f_party_l.text = T("date"), T("time"), T("guests")
        self.who_label.text = r["name"] + ("  ·  “%s”" % r["notes"] if r.get("notes") else "")
        self.change_button.visible = bool(D.get("can_change"))
        self.change_button.text = T("changeRes")
        self.ics_button.visible = live
        self.ics_button.text = T("calendar")
        self.cancel_button.visible = bool(D.get("can_cancel"))
        self.cancel_button.text = T("cancelRes")
        self.again_link.visible = not live
        self.again_label.text = T("bookAgain")
        state.set_attr(self.again_link, "href", pp.book_url(R.get("slug") or ""))
        self.nochange_label.visible = live and not D.get("can_change") and bool(R.get("phone"))
        self.nochange_label.text = T("noChange")
        if self.mode == "change":
            g = D.get("guest") or {}
            self.details_h.text = T("details")
            self.name_cap.text, self.email_cap.text, self.phone_cap.text, self.notes_cap.text = T("name"), T("email"), T("phone"), T("notes")
            self.back_button.text, self.save_button.text = T("back"), T("saveChanges")
            if not self.name_box.text:
                self.name_box.text, self.email_box.text = r["name"], g.get("email") or ""
                self.phone_box.text, self.notes_box.text = g.get("phone") or "", r.get("notes") or ""

    def _lang(self, value, **event_args):
        i18n.set_lang(value)
        if self.mode == "change":
            self.picker.redraw()
        self._draw()

    @handle("change_button", "click")
    def change_button_click(self, **event_args):
        r, R = self.D["reservation"], self.D["restaurant"]
        self.mode = "change"
        self.name_box.text = ""
        self.picker.setup(R["slug"], self.D["days"], None, R.get("max_party"), r["party"], r["date"], r["time"], self.token)
        self._draw()

    @handle("back_button", "click")
    def back_button_click(self, **event_args):
        self.mode = "view"
        self._draw()

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        p = self.picker
        if not p.time:
            self.error_label.visible, self.error_label.text = True, T("pickDate")
            return
        data = {"date": p.date, "time": p.time, "party": p.party, "name": self.name_box.text or "", "email": self.email_box.text or "",
                "phone": self.phone_box.text or "", "notes": self.notes_box.text or ""}
        r = anvil.server.call("change_reservation", self.token, data)
        if r and r.get("ok"):
            self.D, self.mode = r, "view"
            self.error_label.visible = False
            state.toast(T("saved"), "ok")
            self._draw()
            window.scrollTo(0, 0)
        else:
            self.error_label.visible, self.error_label.text = True, (r or {}).get("error") or "Something went wrong."

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        if not confirm(T("cancelText"), title=T("cancelQ"), buttons=[(T("keep"), False), (T("yesCancel"), True)]):
            return
        r = anvil.server.call("cancel_reservation", self.token)
        if r and r.get("ok"):
            self.D = r
            state.toast(T("cancelled"), "ok")
            self._draw()
        else:
            state.toast((r or {}).get("error") or "Could not cancel.", "error")

    @handle("ics_button", "click")
    def ics_button_click(self, **event_args):
        window.PP.ics(self.D["reservation"], self.D["restaurant"], window.location.href)
