import datetime

from anvil import *
import anvil.server

from ._anvil_designer import EventEditorTemplate
from ... import pp


class EventEditor(EventEditorTemplate):
    """Plan or change an event. Closes with the Events page's new data (with "id" for a new event), or None."""

    def __init__(self, rid, data, event=None, **properties):
        super().__init__(**properties)
        self.rid, self.event = rid, event
        e: dict = event or {"title": "", "date": pp.add_days(data["today"], 7), "start": "19:00", "end": "23:00", "kind": "public", "guests": 0,
                      "host": "", "description": "", "notes": "", "photo": None, "blocks": False, "on_site": True}
        self.eyebrow.text = "Edit event" if event else "Plan an event"
        self.title_label.text = e["title"] if event else "What's happening?"
        self.name_box.text = e["title"]
        self.date_picker.date = datetime.date.fromisoformat(e["date"])
        self.start_box.text = e["start"]
        self.end_box.text = "00:00" if e["end"] == "24:00" else e["end"]
        self.kind = e["kind"]
        self.blocks_box.checked, self.site_box.checked = bool(e.get("blocks")), bool(e.get("on_site"))
        self.guests_box.text = str(e.get("guests") or "")
        self.host_box.text, self.desc_box.text, self.notes_box.text = e.get("host") or "", e.get("description") or "", e.get("notes") or ""
        self.photo_field.rid = rid
        self.photo_field.photo = e.get("photo")
        self.save_button.text = "Save" if event else "Save, then set up the room"
        self._kind()
        pp.time_input(self.start_box, self.end_box)

    def _kind(self):
        self.k_public.classes["on"] = self.kind == "public"
        self.k_private.classes["on"] = self.kind == "private"
        self.host_field.visible = self.kind == "private"

    def kind_click(self, event):
        self.kind = event.currentTarget.getAttribute("data-k")
        self.blocks_box.checked = self.kind == "private"
        self.site_box.checked = self.kind == "public"
        self._kind()

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        photo = self.photo_field.photo
        r = anvil.server.call("save_event", self.rid, {
            "id": self.event["id"] if self.event else None, "title": self.name_box.text or "",
            "date": self.date_picker.date.isoformat() if self.date_picker.date else "", "start": (self.start_box.text or "")[:5],
            "end": (self.end_box.text or "")[:5], "kind": self.kind, "blocks": bool(self.blocks_box.checked), "on_site": bool(self.site_box.checked),
            "guests": self.guests_box.text or 0, "host": self.host_box.text or "", "description": self.desc_box.text or "",
            "notes": self.notes_box.text or "", "photo": photo["key"] if photo else None})
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not save."
            return
        self.raise_event("x-close-alert", value=r)
