from anvil import *

from ._anvil_designer import CheckRowTemplate
from ... import router, state


class CheckRow(CheckRowTemplate):
    """A step of Today -> Getting set up. item = {label, done, page} + _rid."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        self.classes["done"] = c["done"]
        self.go_link.visible = not c["done"]
        page = {"menu": "dishes", "settings": "share"}.get(c.get("page"), c.get("page") or "settings")
        state.set_attr(self.go_link, "href", router.href(page, c["_rid"]))
