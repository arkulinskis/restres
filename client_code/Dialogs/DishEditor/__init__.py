from anvil import *
import anvil.server

from ._anvil_designer import DishEditorTemplate


class DishEditor(DishEditorTemplate):
    """Add or change a dish. Closes with the menu editor's new data, or None."""

    def __init__(self, rid, data, dish=None, section_id=None, **properties):
        super().__init__(**properties)
        self.rid, self.dish, self.tags = rid, dish, data["tags"]
        d: dict = dish or {"name": "", "price": "", "description": "", "tags": [], "available": True}
        self.eyebrow.text = "Edit dish" if dish else "New dish"
        self.title_label.text = d["name"] if dish else "Add a dish"
        self.name_box.text, self.price_box.text, self.desc_box.text = d["name"], d.get("price") or "", d.get("description") or ""
        self.section_drop.items = [(s["title"], s["id"]) for s in data["sections"]]
        self.section_drop.selected_value = section_id
        self.picked = list(d.get("tags") or [])
        self.available_box.checked = bool(d.get("available", True))
        self.delete_button.visible = dish is not None
        self.tags_panel.add_event_handler("x-chip", self._tag)
        self._tags()

    def _tags(self):
        self.tags_panel.items = [{"label": "%s · %s" % (k, v), "value": k, "on": k in self.picked} for k, v in self.tags.items()]

    def _tag(self, value, **event_args):
        self.picked = [t for t in self.picked if t != value] if value in self.picked else self.picked + [value]
        self._tags()

    def _done(self, r):
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not save."
            return
        self.raise_event("x-close-alert", value=r)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        self._done(anvil.server.call("save_item", self.rid, {
            "id": (self.dish or {}).get("id"), "section_id": self.section_drop.selected_value, "name": self.name_box.text or "",
            "price": self.price_box.text or "", "description": self.desc_box.text or "", "tags": self.picked,
            "available": bool(self.available_box.checked)}))

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("It leaves the menu straight away.", title="Delete %s?" % (self.dish or {}).get("name", ""), buttons=[("Keep it", False), ("Delete", True)]):
            self._done(anvil.server.call("delete_item", self.rid, (self.dish or {}).get("id")))
