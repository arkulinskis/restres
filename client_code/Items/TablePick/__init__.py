from anvil import *

from ._anvil_designer import TablePickTemplate


class TablePick(TablePickTemplate):
    """A table tick box in the booking editor. item = {id, label, on} (on is written back)."""

    def __init__(self, **properties):
        super().__init__(**properties)
