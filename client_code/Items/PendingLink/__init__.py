from anvil import *

from ._anvil_designer import PendingLinkTemplate
from ... import router, state


class PendingLink(PendingLinkTemplate):
    """'Maison Lumière · 2' on the dashboard's approvals banner: opens that restaurant's reservations."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.label.text = "%s · %d" % (self.item["name"], self.item["pending"])
        state.set_attr(self, "href", router.href("reservations", self.item["id"]))
