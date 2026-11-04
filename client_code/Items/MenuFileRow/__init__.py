from anvil import *

from ._anvil_designer import MenuFileRowTemplate
from ... import state

LANGS = {"en": "English", "fr": "Français", "lv": "Latviešu", "": "Every language"}


class MenuFileRow(MenuFileRowTemplate):
    """A menu file in the menu editor. item = Legacy._file_view. Raises x-delete-file(file=), x-upload-file(file=, media=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        f = self.item
        missing = bool(f.get("missing"))
        kind = "Waiting for its file (imported from the old PlanPlate)" if missing else ("PDF" if "pdf" in f["type"] else "Photo")
        self.meta_label.text = " · ".join(x for x in (kind, LANGS.get(f["language"], f["language"]), f["name"]) if x)
        state.set_attr(self.open_link, "href", f["url"])
        self.open_link.visible = not missing
        self.upload_loader.visible = missing

    @handle("upload_loader", "change")
    def upload_loader_change(self, file, **event_args):
        if file is not None:
            self.parent.raise_event("x-upload-file", file=self.item, media=file)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete-file", file=self.item)
