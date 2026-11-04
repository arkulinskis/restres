from anvil import *

from ._anvil_designer import GroupRowTemplate


class GroupRow(GroupRowTemplate):
    """Tables pushed together in an event's room. item = {i, label, seats}. Raises x-seats(index=, seats=), x-ungroup(index=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.seats_box.text = str(self.item["seats"])

    @handle("seats_box", "change")
    def seats_box_change(self, **event_args):
        try:
            seats = max(1, int(self.seats_box.text or 1))
        except ValueError:
            return
        self.parent.raise_event("x-seats", index=self.item["i"], seats=seats)

    @handle("split_button", "click")
    def split_button_click(self, **event_args):
        self.parent.raise_event("x-ungroup", index=self.item["i"])
