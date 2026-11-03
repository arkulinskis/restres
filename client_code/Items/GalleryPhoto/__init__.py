from anvil import *

from ._anvil_designer import GalleryPhotoTemplate
from ... import pp, state


class GalleryPhoto(GalleryPhotoTemplate):
    """A photo or video on the Gallery page. item = a photo view + _gallery (+ _first, _last, _n in the gallery)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        gallery = bool(p.get("_gallery"))
        self.classes["hidden-ph"] = not gallery
        src = pp.thumb(p)
        self.img.visible = bool(src)
        if src:
            state.set_attr(self.img, "src", src)
        self.video_badge.visible = p.get("kind") == "video"
        self.caption_box.text = p.get("caption") or ""
        self.left_button.visible = self.right_button.visible = self.n_label.visible = gallery
        if gallery:
            self.left_button.enabled = not p["_first"]
            self.right_button.enabled = not p["_last"]
            self.n_label.text = str(p["_n"])
        self.show_button.visible = p.get("kind") == "image"
        self.show_button.text = "Hide from the gallery" if gallery else "Add to the gallery"
        self.show_button.role = ["btn", "btn-ghost", "btn-icon", "ic-eye" if gallery else "ic-eyeoff"]

    @handle("caption_box", "change")
    def caption_box_change(self, **event_args):
        self.parent.raise_event("x-caption", photo=self.item, caption=self.caption_box.text or "")

    @handle("left_button", "click")
    def left_button_click(self, **event_args):
        self.parent.raise_event("x-move", photo=self.item, step=-1)

    @handle("right_button", "click")
    def right_button_click(self, **event_args):
        self.parent.raise_event("x-move", photo=self.item, step=1)

    @handle("show_button", "click")
    def show_button_click(self, **event_args):
        self.parent.raise_event("x-show", photo=self.item)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete", photo=self.item)
