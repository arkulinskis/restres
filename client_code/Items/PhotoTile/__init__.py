from anvil import *

from ._anvil_designer import PhotoTileTemplate
from ... import pp, state


class PhotoTile(PhotoTileTemplate):
    """A photo in a picker or gallery grid. item = a photo view (+ _on). Raises x-pick(photo=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        src = pp.thumb(self.item)
        self.img.visible = bool(src)
        self.ph.visible = not src
        if src:
            state.set_attr(self.img, "src", src)
            state.set_attr(self.img, "alt", self.item.get("caption") or "")
        self.classes["on"] = bool(self.item.get("_on"))
        state.set_attr(self, "title", self.item.get("caption") or "")

    def tile_click(self, event):
        self.parent.raise_event("x-pick", photo=self.item)
