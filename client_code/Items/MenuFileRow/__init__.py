from anvil import *

from ._anvil_designer import MenuFileRowTemplate
from ... import state

LANGS = {"en": "English", "fr": "Français", "lv": "Latviešu", "": "Every language"}


class MenuFileRow(MenuFileRowTemplate):
    """A menu file in the menu editor. item = Legacy._file_view. Raises x-delete-file(file=)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        f = self.item
        self.meta_label.text = "%s · %s · %s" % ("PDF" if "pdf" in f["type"] else "Photo", LANGS.get(f["language"], f["language"]), f["name"])
        state.set_attr(self.open_link, "href", f["url"])

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete-file", file=self.item)
