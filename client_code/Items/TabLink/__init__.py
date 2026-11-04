from anvil import *

from ._anvil_designer import TabLinkTemplate
from ... import state


class TabLink(TabLinkTemplate):
    """A tab of the restaurant sub-menu. item = {href, label, icon, on, count}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.set_attr(self, "href", self.item["href"])
        self.icon.classes.add("ic-" + self.item["icon"])
        self.classes["on"] = bool(self.item.get("on"))
        n = self.item.get("count") or 0
        self.count.visible = n > 0
        self.count.text = str(n)
