from anvil import *

from ._anvil_designer import LayoutCardTemplate


class LayoutCard(LayoutCardTemplate):
    """A gallery layout to pick (Gallery page): a small drawing of it, its name and one line. item = {key, name, desc,
    svg, on}. A click raises x-style(key="layout", value=item key) on the RepeatingPanel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        self.dom_nodes["pic"].innerHTML = i["svg"]
        self.name_label.text, self.desc_label.text = i["name"], i["desc"]
        btn = self.dom_nodes["btn"]
        btn.classList.toggle("on", bool(i.get("on")))
        btn.setAttribute("aria-pressed", "true" if i.get("on") else "false")

    def click(self, event):
        self.parent.raise_event("x-style", key="layout", value=self.item["key"])
