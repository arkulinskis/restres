from anvil import *

from ... import pp
from ._anvil_designer import IntervalTemplate


class Interval(IntervalTemplate):
    """Opening and closing time (written back into item = {open, close}). Raises x-remove(item=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        pp.time_input(self.open_box, self.close_box)

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        self.parent.raise_event("x-remove", item=self.item)
