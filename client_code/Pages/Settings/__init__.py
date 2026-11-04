from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import SettingsTemplate
from ... import pp, router, state

TEXT = ["name", "description", "address", "phone", "email", "website", "form_note", "notify_email", "msg_confirmed", "msg_pending", "msg_declined"]
RULES = [("duration_min", "Table time", "How long each booking holds its table. You can change it per booking.", "min"),
         ("slot_min", "Time slots", "Spacing of the times guests can pick.", "min"),
         ("last_booking_min", "Last booking", "How long before closing the last table can be booked.", "min"),
         ("lead_min", "Minimum notice", "How far ahead a guest must book.", "min"),
         ("window_days", "Booking window", "How many days ahead guests can book.", "days"),
         ("max_party", "Largest party online", "Bigger groups are asked to contact you.", "guests")]
APPROVAL = [("auto_threshold", "Auto-confirm until", "Once this share of seats is taken at a time, new bookings wait for approval. "
             "100% confirms everything that fits; 0% sends every booking to you.", "% full"),
            ("max_auto_party", "Large parties", "Parties bigger than this always wait for approval.", "guests")]


class Settings(SettingsTemplate):
    """#settings/<rid>: the restaurant's details, booking rules, approvals, the booking form's texts, emails, languages,
    the team (owner only) and deleting it (owner only). Sharing and QR codes are on #share."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        state.set_control_attr(self.over_drop, "aria-label", "When the limit is reached")
        state.set_control_attr(self.invite_email, "aria-label", "Colleague's email")
        state.set_control_attr(self.invite_role, "aria-label", "Their role")
        self.rid = args[0]
        self.D = anvil.server.call("get_settings", self.rid)
        self.team_panel.add_event_handler("x-role", self._role)
        self.team_panel.add_event_handler("x-remove", self._remove)
        self._fill()

    def _box(self, key):
        return getattr(self, key + "_box") if key not in ("notify_email",) else self.notify_box

    def _fill(self):
        D, s = self.D, self.D["settings"]
        self.rnav.show(D["nav"])
        for k in TEXT:
            box = self._box({"form_note": "form_note", "notify_email": "notify_email"}.get(k, k))
            box.text = s.get(k) or ""
        self.slug_box.text = s["slug"]
        self.legacy_box.text = s.get("legacy_id") or ""
        self.slug_hint.text = pp.book_url(s["slug"])
        self.dom_nodes["tz"].innerHTML = pp.tz_field_html("timezone", s["timezone"], "st_timezone")
        self.accepting_box.checked = s["accepting"]
        self.rules_panel.items = [{"key": k, "title": t, "desc": d, "unit": u, "value": s[k]} for k, t, d, u in RULES]
        self.approval_panel.items = [{"key": k, "title": t, "desc": d, "unit": u, "value": s[k]} for k, t, d, u in APPROVAL]
        self.over_drop.selected_value = s["over_capacity"]
        self.privacy_box.text = s.get("privacy_text") or ""
        self.privacy_box.placeholder = s["default_privacy"]
        self.emails_box.checked = s["emails_on"]
        self.notify_box.placeholder = s["owner_email"]
        self.notify_hint.text = "The moment a booking needs approval, an alert goes here. Leave empty to use the owner's address (%s)." % s["owner_email"]
        self.language_drop.selected_value = s["language"]
        for l in ("en", "fr", "lv"):
            getattr(self, "lang_" + l).checked = l in s["languages"]
        notes = s.get("form_notes") or {}
        for l in ("en", "fr", "lv"):
            getattr(self, "note_%s_box" % l).text = notes.get(l) or ""
            getattr(self, "note_%s_field" % l).visible = l != s["language"]
        owner = D.get("role") == "owner"
        self.team_lead.text = ("Give managers and staff their own sign-in. Managers can change everything except the team; staff see and "
                               "manage reservations and the guest book only.") if owner else "Only the owner can change the team."
        self.team_panel.items = [dict(m, _owner_view=owner) for m in D.get("team") or []]
        self.invite_row.visible = self.invite_hint.visible = owner
        self.danger.visible = self.toc_danger.visible = owner
        self.delete_button.text = "Delete " + s["name"]

    def toc_click(self, event):
        window.PP.scrollToId(event.currentTarget.getAttribute("data-to"))

    # ---------------------------------------------------------------- save
    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        v = {k: self._box(k).text or "" for k in TEXT}
        v.update(slug=self.slug_box.text or "", legacy_id=(self.legacy_box.text or "").strip(), accepting=self.accepting_box.checked, over_capacity=self.over_drop.selected_value,
                 privacy_text=self.privacy_box.text or "", emails_on=self.emails_box.checked, language=self.language_drop.selected_value,
                 languages=[l for l in ("en", "fr", "lv") if getattr(self, "lang_" + l).checked],
                 form_notes={l: getattr(self, "note_%s_box" % l).text or "" for l in ("en", "fr", "lv")
                             if l != self.language_drop.selected_value})
        node = self.dom_nodes["tz"].querySelector("input[type=hidden]")
        v["timezone"] = getattr(node, "value", None) or self.D["settings"]["timezone"]
        for row in list(self.rules_panel.items) + list(self.approval_panel.items):
            v[row["key"]] = row["value"]
        r = state.call("save_settings", self.rid, v)
        if r:
            self.D["settings"], self.D["nav"] = r["settings"], r["nav"]
            self._fill()
            state.toast("Settings saved", "ok")

    @handle("revert_button", "click")
    def revert_button_click(self, **event_args):
        self._fill()

    # ---------------------------------------------------------------- team
    def _team(self, r, msg):
        if r:
            self.D["team"] = r["team"]
            self._fill()
            state.toast(msg, "ok")

    @handle("invite_button", "click")
    def invite_button_click(self, **event_args):
        r = state.call("invite_member", self.rid, self.invite_email.text or "", self.invite_role.selected_value)
        if r:
            self.invite_email.text = ""
        self._team(r, "Invitation sent")

    def _role(self, member, role, **event_args):
        self._team(state.call("set_member_role", self.rid, member["id"], role), "Role changed")

    def _remove(self, member, **event_args):
        if confirm("They lose access to this restaurant straight away.", title="Remove %s?" % (member.get("name") or member["email"]),
                   buttons=[("Keep them", False), ("Remove", True)]):
            self._team(state.call("remove_member", self.rid, member["id"]), "Removed")

    # ---------------------------------------------------------------- delete
    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        name = self.D["settings"]["name"]
        box = TextBox(placeholder=name)
        if not alert(box, title="Type “%s” to delete it" % name, buttons=[("Cancel", False), ("Delete for good", True)], role="app-dialog"):
            return
        r = state.call("delete_restaurant", self.rid, box.text or "")
        if r:
            state.toast("%s was deleted." % name, "ok")
            router.go("dashboard")
