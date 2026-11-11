import datetime

from anvil import *
import anvil.server

from ._anvil_designer import BookingEditorTemplate
from ... import pp, state


def _dur_text(m):
    return "%d h%s" % (m // 60, " %d min" % (m % 60) if m % 60 else "")


class BookingEditor(BookingEditorTemplate):
    """Add or change a booking (staff). res = a reservation view, or None for a new one; preset = values for a new one
    (time, tables, source, status, name). Closes with the day's new data (Portal.get_day), or None."""

    def __init__(self, rid, day, res=None, preset=None, **properties):
        super().__init__(**properties)
        self.rid, self.D, self.is_new = rid, day, res is None
        s = day["settings"]
        r: dict = res or dict({"name": "", "phone": "", "email": "", "date": day["date"], "time": "19:00", "duration": s["duration_min"],
                         "party": 2, "notes": "", "staff_note": "", "status": "confirmed", "source": "phone", "tables": []}, **(preset or {}))
        self.res = r
        walk_in = self.is_new and r.get("source") == "walk_in"
        self.title_label.text = ("Seat a walk-in" if walk_in else "Add a booking") if self.is_new else r["name"]
        self.status_badge.visible = not self.is_new
        self.status_badge.text = pp.STATUS.get(r["status"], r["status"])
        self.status_badge.role = ["badge", pp.STATUS_ROLE.get(r["status"], "badge")]
        # one tap to ring or write to the guest (the host stand's phone or tablet)
        phone, email = (r.get("phone") or "").strip(), (r.get("email") or "").strip()
        dial = ("+" if phone.startswith("+") else "") + "".join(ch for ch in phone if ch.isdigit())
        self.contact_box.visible = not self.is_new and bool(dial or email)
        self.call_link.visible = bool(dial)
        self.call_label.text = "Call " + phone
        state.set_attr(self.call_link, "href", "tel:" + dial)
        self.mail_link.visible = bool(email)
        self.mail_label.text = "Email " + email
        state.set_attr(self.mail_link, "href", "mailto:" + email)
        self.reason_label.visible = r["status"] == "pending" and bool(r.get("review_reason"))
        self.reason_label.text = r.get("review_reason") or ""
        g: dict = r.get("guest") or {}
        self.guest_box.visible = bool(g.get("visits") or g.get("no_shows") or g.get("note"))
        bits = []
        if g.get("vip"):
            bits.append("VIP")
        if g.get("visits"):
            bits.append(state.plural(g["visits"], "visit"))
        if g.get("no_shows"):
            bits.append(state.plural(g["no_shows"], "no-show"))
        bits += [t for t in g.get("tags") or [] if t != "VIP"]
        self.guest_label.text = " · ".join(bits) + ((". " + g["note"]) if g.get("note") else "")
        self.date_picker.date = datetime.date.fromisoformat(r["date"])
        self.time_box.text = r["time"]
        self.party_box.text = str(r["party"])
        durs = list(range(30, 301, 15))
        if r["duration"] not in durs:
            durs.append(r["duration"])
        self.duration_drop.items = [(_dur_text(m), m) for m in sorted(durs)]
        self.duration_drop.selected_value = r["duration"]
        manual = bool(r.get("tables"))
        self.table_mode.selected_value = "manual" if manual else "auto"
        self.manual_box.visible = manual
        self.tables_panel.items = [{"id": t["id"], "label": "%s · %s" % (t["name"], t["seats"]), "on": t["id"] in (r.get("tables") or [])}
                                   for t in day["tables"]]
        self.name_box.text, self.phone_box.text, self.email_box.text = r["name"], r.get("phone") or "", r.get("email") or ""
        self.source_drop.selected_value = r.get("source") or "phone"
        self.notes_box.text, self.staff_box.text = r.get("notes") or "", r.get("staff_note") or ""
        self.notify_box.text = "Email the guest %s (when there is an email address)" % ("a confirmation" if self.is_new else "about this change")
        self.notify_box.checked = self.is_new and r.get("source") != "walk_in"
        self.link_box.visible = not self.is_new
        if not self.is_new:
            self.link_label.text = pp.manage_url(r["token"])
        self.save_button.text = ("Seat them" if walk_in else "Add booking") if self.is_new else "Save changes"
        st = r["status"]
        old = not self.is_new
        self.approve_button.visible = old and st == "pending"
        self.decline_button.visible = old and st == "pending"
        self.seat_button.visible = old and st == "confirmed"
        self.done_button.visible = old and st == "seated"
        self.noshow_button.visible = old and st == "confirmed"
        self.cancel_res_button.visible = old and st == "confirmed"
        self.restore_button.visible = old and st in ("cancelled", "declined", "no_show", "done")
        hist: list = list(r.get("history") or [])
        self.hist_box.visible = bool(hist)
        self.hist_label.text = "\n".join("%s  %s" % (state.short_date(h["at"]) + " " + h["at"][11:16], h["what"]) for h in reversed(hist))
        self.consent_label.visible = bool(r.get("consent"))
        self.consent_label.text = "The guest agreed to the privacy notice on %s." % state.short_date(r.get("consent_at") or "")
        self._say(None)
        pp.time_input(self.time_box)
        self._options()

    # ---------------------------------------------------------------- live hints: is a table free?
    def _values(self):
        return {"date": self.date_picker.date.isoformat() if self.date_picker.date else self.D["date"], "time": (self.time_box.text or "")[:5],
                "party": self.party_box.text or "2", "duration": self.duration_drop.selected_value}

    def _options(self):
        v = self._values()
        try:
            o = anvil.server.call_s("get_options", self.rid, v["date"], v["time"], v["party"], v["duration"], None if self.is_new else self.res["id"])
        except Exception:
            o = None
        if not o or not o.get("ok"):
            self.options_label.text = (o or {}).get("error") or ""
            return
        best = o["units"][0] if o["units"] else None
        self.options_label.text = (("" if o["open"] else "Closed at this time. ") +
                                   ("Best fit: %s (%s)" % (best["label"], best["seats"]) if best else "No free table fits.") + " · %d%% booked" % o["pct"])

    @handle("date_picker", "change")
    def date_picker_change(self, **event_args):
        self._options()

    @handle("time_box", "lost_focus")
    def time_box_lost_focus(self, **event_args):
        self._options()

    @handle("party_box", "lost_focus")
    def party_box_lost_focus(self, **event_args):
        self._options()

    @handle("duration_drop", "change")
    def duration_drop_change(self, **event_args):
        self._options()

    @handle("table_mode", "change")
    def table_mode_change(self, **event_args):
        self.manual_box.visible = self.table_mode.selected_value == "manual"

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        pp.copy(pp.manage_url(self.res["token"]), "Guest link")

    # ---------------------------------------------------------------- save
    def _say(self, msg, conflict=False):
        self.msg_box.visible = bool(msg)
        self.message.text = msg or ""
        self.message.role = "msg-note" if conflict else "msg-error"
        self.force_button.visible = conflict

    def _save(self, force=False):
        v = self._values()
        if not (self.name_box.text or "").strip():
            self._say("Please add the guest's name.")
            return
        tables = "auto"
        if self.table_mode.selected_value == "manual":
            picked = [t["id"] for t in self.tables_panel.items if t.get("on")]
            tables = picked or "auto"
        email = (self.email_box.text or "").strip()
        payload = dict(v, id=None if self.is_new else self.res["id"], force=force, tables=tables,
                       notify=bool(self.notify_box.checked) and bool(email), name=self.name_box.text or "",
                       phone=self.phone_box.text or "", email=email, source=self.source_drop.selected_value,
                       notes=self.notes_box.text or "", staff_note=self.staff_box.text or "")
        if self.is_new and self.res.get("status") == "seated":
            payload["status"] = "seated"
        self.save_button.enabled = False
        try:
            r = anvil.server.call("save_reservation", self.rid, payload)
        finally:
            self.save_button.enabled = True
        if r and r.get("ok"):
            emailed = "guest" in (r.get("emailed") or [])
            state.toast(("Booking added" if self.is_new else "Saved") + (" · guest emailed" if emailed else ""), "ok")
            self.raise_event("x-close-alert", value=r["day"])
        else:
            self._say((r or {}).get("error") or "Could not save.", conflict=bool((r or {}).get("conflict")))

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        self._save(False)

    @handle("force_button", "click")
    def force_button_click(self, **event_args):
        self._save(True)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    # ---------------------------------------------------------------- status buttons
    def _status(self, status):
        from ...Pages.Reservations import change_status
        day = change_status(self.rid, self.res, status, self.D["date"])
        if day:
            self.raise_event("x-close-alert", value=day)

    @handle("approve_button", "click")
    def approve_button_click(self, **event_args):
        self._status("confirmed")

    @handle("decline_button", "click")
    def decline_button_click(self, **event_args):
        self._status("declined")

    @handle("seat_button", "click")
    def seat_button_click(self, **event_args):
        self._status("seated")

    @handle("done_button", "click")
    def done_button_click(self, **event_args):
        self._status("done")

    @handle("noshow_button", "click")
    def noshow_button_click(self, **event_args):
        self._status("no_show")

    @handle("cancel_res_button", "click")
    def cancel_res_button_click(self, **event_args):
        self._status("cancelled")

    @handle("restore_button", "click")
    def restore_button_click(self, **event_args):
        self._status("confirmed")
