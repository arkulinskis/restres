from anvil import *
import anvil.server

from ._anvil_designer import SectionEditorTemplate


class SectionEditor(SectionEditorTemplate):
    """Add or rename a menu section. Closes with the menu editor's new data, or None."""

    def __init__(self, rid, section=None, **properties):
        super().__init__(**properties)
        self.rid, self.section = rid, section
        self.title_label.text = section["title"] if section else "Add a section"
        self.title_box.text = section["title"] if section else ""
        self.desc_box.text = (section or {}).get("description") or ""

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        r = anvil.server.call("save_section", self.rid, {"id": self.section["id"] if self.section else None,
                                                          "title": self.title_box.text or "", "description": self.desc_box.text or ""})
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not save."
            return
        self.raise_event("x-close-alert", value=r)
