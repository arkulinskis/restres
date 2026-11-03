from anvil import *

from ._anvil_designer import StyleFieldTemplate


class StyleField(StyleFieldTemplate):
    """One gallery style choice. item = {key, label, choices: [(value, text)], value}. Raises x-style(key=, value=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.drop.items = [(text, value) for value, text in self.item["choices"]]
        self.drop.selected_value = self.item["value"]

    @handle("drop", "change")
    def drop_change(self, **event_args):
        self.parent.raise_event("x-style", key=self.item["key"], value=self.drop.selected_value)
