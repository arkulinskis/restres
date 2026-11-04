from anvil import *

from ._anvil_designer import ChipTemplate
from ... import state


class Chip(ChipTemplate):
    """A pill button in a row of choices (hours, days, party sizes, times, tags).
    item = {label, value, on, disabled?, group?, title?, aria?}; a click raises x-chip(value=, group=) on the RepeatingPanel.
    Screen readers hear aria (or the label) and, when the item has "on", whether it's chosen (aria-pressed).
    After the click the keyboard focus stays on this choice even when the handler redraws the whole row."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        self.chip.text = i["label"]
        self.chip.role = ["chip", "on"] if i.get("on") else ["chip"]
        self.chip.enabled = not i.get("disabled")
        if i.get("title"):
            self.chip.tooltip = i["title"]
        self._key = "%s|%s" % (i.get("group") or "", i.get("value"))
        state.set_control_attr(self.chip, "data-key", self._key)
        if "on" in i:
            state.set_control_attr(self.chip, "aria-pressed", "true" if i.get("on") else "false")
        if i.get("aria"):
            state.set_control_attr(self.chip, "aria-label", i["aria"])

    @handle("chip", "click")
    def chip_click(self, **event_args):
        panel = self.parent
        panel.raise_event("x-chip", value=self.item["value"], group=self.item.get("group"))
        state.refocus(panel, self._key)
