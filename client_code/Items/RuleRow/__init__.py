from anvil import *

from ._anvil_designer import RuleRowTemplate
from ... import state


class RuleRow(RuleRowTemplate):
    """A number setting with its explanation (Settings). item = {key, title, desc, unit, value}; value is written back."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.set_control_attr(self.value_box, "aria-label", "%s (%s)" % (self.item.get("title") or "", self.item.get("unit") or ""))
