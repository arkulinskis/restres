# GalleryPage — Custom HTML form. HTML: forms/GalleryPage.html
# The restaurant's photos and gallery style (Media.get_gallery / save_photo / order_photos / delete_photo / save_gallery_style).
from ._anvil_designer import GalleryPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class GalleryPage(GalleryPageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_gallery", restaurant_id)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "gallery", self.data, self._on_event, rid=self.rid)

    def _on_event(self, event, p):
        if event == "save_photo":
            return anvil.server.call_s("save_photo", self.rid, p)
        if event == "order":
            return pp_ui.call("order_photos", self.rid, p.get("ids"))
        if event == "delete_photo":
            return pp_ui.call("delete_photo", self.rid, p["id"])
        if event == "save_style":
            return anvil.server.call_s("save_gallery_style", self.rid, p.get("style"))
