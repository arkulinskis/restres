from anvil import *

from ._anvil_designer import RuleRowTemplate


class RuleRow(RuleRowTemplate):
    """A number setting with its explanation (Settings). item = {key, title, desc, unit, value}; value is written back."""

    def __init__(self, **properties):
        super().__init__(**properties)
