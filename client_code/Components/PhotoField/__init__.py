from anvil import *

from ._anvil_designer import PhotoFieldTemplate
from ... import pp, state


class PhotoField(PhotoFieldTemplate):
    """A photo (or video) field: see the help text in form_template.html."""

    def __init__(self, **properties):
        self.rid, self._photo, self.label, self.kind = None, None, "Photo (optional)", "image"
        self.init_components(**properties)
        self._draw()

    @property
    def photo(self):
        return self._photo

    @photo.setter
    def photo(self, value):
        self._photo = value
        self._draw()

    def _draw(self):
        src = pp.thumb(self._photo)
        self.img.visible = bool(src)
        self.ph.visible = not src
        if src:
            state.set_attr(self.img, "src", src)
        self.label_label.text = self.label
        self.choose_button.text = "Change" if self._photo else "Choose"
        self.clear_button.visible = bool(self._photo)

    def _choose(self):
        from ...Dialogs.PhotoPicker import PhotoPicker
        p = alert(PhotoPicker(self.rid, self.kind, (self._photo or {}).get("key")), buttons=[], role="app-dialog", large=True, dismissible=True)
        if p:
            self.photo = p
            self.raise_event("change")

    def thumb_click(self, event):
        self._choose()

    @handle("choose_button", "click")
    def choose_button_click(self, **event_args):
        self._choose()

    @handle("clear_button", "click")
    def clear_button_click(self, **event_args):
        self.photo = None
        self.raise_event("change")
