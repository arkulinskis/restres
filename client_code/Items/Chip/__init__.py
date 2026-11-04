from anvil import *

from ._anvil_designer import ChipTemplate


class Chip(ChipTemplate):
    """A pill button in a row of choices (hours, days, party sizes, times, tags).
    item = {label, value, on, disabled?, group?, title?}; a click raises x-chip(value=, group=) on the RepeatingPanel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        self.chip.text = i["label"]
        self.chip.role = ["chip", "on"] if i.get("on") else ["chip"]
        self.chip.enabled = not i.get("disabled")
        if i.get("title"):
            self.chip.tooltip = i["title"]

    @handle("chip", "click")
    def chip_click(self, **event_args):
        self.parent.raise_event("x-chip", value=self.item["value"], group=self.item.get("group"))
