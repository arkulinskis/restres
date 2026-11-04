from anvil import *
import anvil.js

from ._anvil_designer import PaletteChipTemplate


class PaletteChip(PaletteChipTemplate):
    """A colour palette in the website builder. item = a Site.PALETTES entry + _on, _accent. Raises x-palette(key=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        self.classes["on"] = bool(p["_on"])
        accent = p["_accent"] if p["_on"] and p["_accent"] else p["accent"]
        for el, col in ((self.c1, p["bg"]), (self.c2, p["deep"]), (self.c3, accent), (self.c4, p["ink"])):
            anvil.js.get_dom_node(el).style.background = col

    def pal_click(self, event):
        self.parent.raise_event("x-palette", key=self.item["key"])
