from anvil import *

from ._anvil_designer import EdDishTemplate


class EdDish(EdDishTemplate):
    """A dish in the menu editor. item = a dish + _tags, _first, _last."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        self.classes["off"] = not i["available"]
        self.tags_label.visible = bool(i.get("tags"))
        self.tags_label.text = " · ".join(i.get("tags") or [])
        self.off_badge.visible = not i["available"]
        self.desc_label.visible = bool(i.get("description"))
        self.desc_label.text = i.get("description") or ""
        self.toggle_button.text = "Back on" if not i["available"] else "Sold out"
        self.up_button.enabled = not i["_first"]
        self.down_button.enabled = not i["_last"]

    @handle("toggle_button", "click")
    def toggle_button_click(self, **event_args):
        self.parent.raise_event("x-toggle-dish", dish=self.item)

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.parent.raise_event("x-edit-dish", dish=self.item)

    @handle("up_button", "click")
    def up_button_click(self, **event_args):
        self.parent.raise_event("x-move", row_id=self.item["id"], step=-1)

    @handle("down_button", "click")
    def down_button_click(self, **event_args):
        self.parent.raise_event("x-move", row_id=self.item["id"], step=1)
