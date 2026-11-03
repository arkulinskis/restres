from anvil import *

from ._anvil_designer import MenuDishTemplate


class MenuDish(MenuDishTemplate):
    """A dish on the guest menu. item = {name, description, price, tags}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.tags_label.visible = bool(self.item.get("tags"))
        self.tags_label.text = " · ".join(self.item.get("tags") or [])
        self.desc_label.visible = bool(self.item.get("description"))
        self.desc_label.text = self.item.get("description") or ""
