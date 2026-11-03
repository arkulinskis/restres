from anvil import *

from ._anvil_designer import EdSectionTemplate


class EdSection(EdSectionTemplate):
    """A menu section in the editor, with its dishes. Raises its events on the page's RepeatingPanel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s = self.item
        self.desc_label.visible = bool(s.get("description"))
        self.desc_label.text = s.get("description") or ""
        self.up_button.enabled = not s["_first"]
        self.down_button.enabled = not s["_last"]
        n = len(s["items"])
        self.dishes_panel.items = [dict(i, _tags=s["_tags"], _first=k == 0, _last=k == n - 1) for k, i in enumerate(s["items"])]
        self.dishes_panel.add_event_handler("x-edit-dish", self._edit_dish)
        self.dishes_panel.add_event_handler("x-toggle-dish", self._toggle_dish)
        self.dishes_panel.add_event_handler("x-move", self._move_dish)

    def _edit_dish(self, dish, **event_args):
        self.parent.raise_event("x-edit-dish", dish=dish, section_id=self.item["id"])

    def _toggle_dish(self, dish, **event_args):
        self.parent.raise_event("x-toggle-dish", dish=dish, section_id=self.item["id"])

    def _move_dish(self, row_id, step, **event_args):
        self.parent.raise_event("x-move", kind="item", row_id=row_id, step=step)

    @handle("up_button", "click")
    def up_button_click(self, **event_args):
        self.parent.raise_event("x-move", kind="section", row_id=self.item["id"], step=-1)

    @handle("down_button", "click")
    def down_button_click(self, **event_args):
        self.parent.raise_event("x-move", kind="section", row_id=self.item["id"], step=1)

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.parent.raise_event("x-edit-section", section=self.item)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete-section", section=self.item)

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        self.parent.raise_event("x-new-dish", section_id=self.item["id"])
