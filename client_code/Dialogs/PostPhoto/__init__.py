from anvil import *
import anvil.server

from ._anvil_designer import PostPhotoTemplate
from ... import pp, state


class PostPhoto(PostPhotoTemplate):
    """Photo of the day: take or pick a photo (shrunk on the phone, then uploaded), add a line, post. It shows at the
    top of the website for 3 days. Closes with the Today page's new data, or None."""

    def __init__(self, rid, **properties):
        super().__init__(**properties)
        self.rid, self.photo = rid, None
        self.shot_img.visible = False

    @handle("shot_button", "click")
    def shot_button_click(self, **event_args):
        self.status_label.text = "Uploading…"
        res = pp.upload(self.rid, "image/*", False)
        self.status_label.text = ""
        if not res:
            return
        if not res[0]["ok"]:
            state.toast(res[0]["error"], "error")
            return
        self.photo = res[0]["photo"]
        self.shot_img.visible = True
        state.set_attr(self.shot_img, "src", pp.thumb(self.photo))
        self.shot_button.text = "Use another photo"

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        r = anvil.server.call("post_photo", self.rid, {"photo": self.photo["key"] if self.photo else None, "text": self.text_box.text or "",
                                                       "add_to_gallery": bool(self.gallery_box.checked)})
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not post."
            return
        self.raise_event("x-close-alert", value=r)
