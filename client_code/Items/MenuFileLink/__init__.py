from anvil import *

from ._anvil_designer import MenuFileLinkTemplate
from ... import state


class MenuFileLink(MenuFileLinkTemplate):
    """A menu file (PDF or photo) on the guest menu. item = {title, url, type}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.set_attr(self, "href", self.item["url"])
        self.kind_label.text = "PDF" if "pdf" in (self.item.get("type") or "") else "Photo"
