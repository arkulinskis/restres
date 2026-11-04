from anvil import *

from ._anvil_designer import MenuSectionTemplate


class MenuSection(MenuSectionTemplate):
    """A section of the guest menu (#menu). item = {title, description, items}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.desc_label.visible = bool(self.item.get("description"))
        self.desc_label.text = self.item.get("description") or ""
        self.dishes_panel.items = [i for i in self.item["items"] if i.get("available", True) is not False]
