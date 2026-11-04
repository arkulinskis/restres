from anvil import *
import anvil.server

from ._anvil_designer import PhotoPickerTemplate
from ... import pp, state

STORAGE = {"cloudinary": "Stored on Cloudinary", "planplate": "Stored in PlanPlate"}


class PhotoPicker(PhotoPickerTemplate):
    """Choose one of the restaurant's photos (or videos), or upload a new one from the phone or computer.
    kind = "image" | "video" | "any". Closes with the photo view {key, url, thumb_url, ...}, or None."""

    def __init__(self, rid, kind="image", current=None, title=None, meta=None, **properties):
        super().__init__(**properties)
        self.rid, self.kind, self.current, self.meta = rid, kind, current, meta or {}
        video = kind == "video"
        self.eyebrow.text = "Video" if video else "Photo"
        self.title_label.text = title or ("Choose a video" if video else "Choose a photo")
        self.upload_button.text = "Upload a video" if video else "Upload a photo"
        self.photos_panel.add_event_handler("x-pick", self._pick)
        try:
            r = anvil.server.call("get_media", rid)
        except Exception:
            r = {"photos": []}
        self.storage_label.text = STORAGE.get(r.get("storage"), "")
        self.storage_label.visible = bool(self.storage_label.text)
        self._list = r.get("photos") or []
        self._draw()

    def _draw(self):
        mine = [p for p in self._list if self.kind == "any" or (p.get("kind") or "image") == self.kind]
        self.photos_panel.items = [dict(p, _on=p["key"] == self.current) for p in mine]
        self.empty_label.visible = not mine
        self.empty_label.text = ("No videos yet. Upload one: an MP4 from your phone works." if self.kind == "video"
                                 else "No photos yet. Upload one from your phone or computer.")

    def _pick(self, photo, **event_args):
        self.raise_event("x-close-alert", value={k: v for k, v in photo.items() if not k.startswith("_")})

    @handle("upload_button", "click")
    def upload_button_click(self, **event_args):
        accept = "video/mp4,video/webm,video/quicktime" if self.kind == "video" else "image/*"
        self.status_label.text = "Uploading…"
        res = pp.upload(self.rid, accept, False, self.meta)
        self.status_label.text = ""
        if not res:
            return
        if res[0]["ok"]:
            self.raise_event("x-close-alert", value=res[0]["photo"])
        else:
            state.toast(res[0]["error"], "error")

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
