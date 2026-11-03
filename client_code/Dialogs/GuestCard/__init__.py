from anvil import *
import anvil.server

from ._anvil_designer import GuestCardTemplate
from ... import state


class GuestCard(GuestCardTemplate):
    """One guest: their numbers, tags and the team's notes, and every booking (newest first).
    Closes with True when something was saved."""

    def __init__(self, rid, key, **properties):
        super().__init__(**properties)
        self.rid, self.key = rid, key
        self.history_panel.add_event_handler("x-edit", lambda **e: None)  # read-only here
        self._show(anvil.server.call("get_guest", rid, key))

    def _show(self, r):
        if not r or not r.get("ok"):
            self.title_label.text = (r or {}).get("error") or "Guest not found"
            return
        g = r["guest"]
        self.g, self.all_tags, self.can_edit = g, r["tags"], r["can_edit"]
        self.title_label.text = g["name"] + (" ★" if g.get("vip") else "")
        self.contact_label.text = " · ".join(x for x in [g.get("email"), g.get("phone")] if x)
        self.n_visits.text, self.n_covers.text = str(g["visits"]), str(g["covers"])
        self.n_noshow.text, self.n_cancel.text = str(g["no_shows"]), str(g["cancelled"])
        self.tags = list(g.get("tags") or [])
        self.note_box.text = g.get("note") or ""
        self.note_box.enabled = self.can_edit
        self.save_button.visible = self.can_edit
        self.readonly_label.visible = not self.can_edit
        self.tags_panel.add_event_handler("x-chip", self._tag)
        self._tags()
        self.history_panel.items = [dict(x, _show_date=True) for x in r["history"]]

    def _tags(self):
        self.tags_panel.items = [{"label": t, "value": t, "on": t in self.tags, "disabled": not self.can_edit} for t in self.all_tags]

    def _tag(self, value, **event_args):
        self.tags = [t for t in self.tags if t != value] if value in self.tags else self.tags + [value]
        self._tags()

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=False)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        r = state.call("save_guest", self.rid, self.key, {"note": self.note_box.text or "", "tags": self.tags})
        if r:
            state.toast("Saved", "ok")
            self.raise_event("x-close-alert", value=True)
