from anvil import *

from ._anvil_designer import SiteListRowTemplate


class SiteListRow(SiteListRowTemplate):
    """A review or a highlight in the website builder. item = {kind, i, row, model}; edits go straight into row."""

    def __init__(self, **properties):
        super().__init__(**properties)
        review = self.item["kind"] == "reviews"
        r = self.item["row"]
        self.review_top.visible = self.rating_drop.visible = review
        self.title_box.visible = not review
        self.text_box.placeholder = "What they said" if review else ""
        if review:
            self.name_box.text, self.source_box.text = r.get("name") or "", r.get("source") or ""
            self.rating_drop.selected_value = int(r.get("rating") or 5)
        else:
            self.title_box.text = r.get("title") or ""
        self.text_box.text = r.get("text") or ""

    def _put(self, key, value):
        self.item["row"][key] = value
        self.parent.raise_event("x-changed")

    @handle("name_box", "change")
    def name_box_change(self, **event_args):
        self._put("name", self.name_box.text or "")

    @handle("source_box", "change")
    def source_box_change(self, **event_args):
        self._put("source", self.source_box.text or "")

    @handle("rating_drop", "change")
    def rating_drop_change(self, **event_args):
        self._put("rating", self.rating_drop.selected_value)

    @handle("title_box", "change")
    def title_box_change(self, **event_args):
        self._put("title", self.title_box.text or "")

    @handle("text_box", "change")
    def text_box_change(self, **event_args):
        self._put("text", self.text_box.text or "")

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        self.parent.raise_event("x-remove", i=self.item["i"])
