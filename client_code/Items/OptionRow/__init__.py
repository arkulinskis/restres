from anvil import *

from ._anvil_designer import OptionRowTemplate


class OptionRow(OptionRowTemplate):
    """One gallery option as a row of chips (Gallery page). item = {key, label, choices: [(value, text)], value}.
    A chip click raises x-style(key=, value=) on the page's RepeatingPanel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        self.label.text = i["label"]
        self.chips.items = [{"label": text, "value": value, "on": value == i["value"], "group": i["key"]} for value, text in i["choices"]]
        self.chips.add_event_handler("x-chip", self._pick)

    def _pick(self, value, group, **event_args):
        self.parent.raise_event("x-style", key=group, value=value)
