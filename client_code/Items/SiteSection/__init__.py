from anvil import *
import anvil.js

from ._anvil_designer import SiteSectionTemplate


class SiteSection(SiteSectionTemplate):
    """A collapsible section of the website builder. item = a site_model section + model, rid, open."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s = self.item
        node = anvil.js.get_dom_node(self.box)
        if s.get("open"):
            node.setAttribute("open", "")
        self.classes["ok"] = bool(s["ok"])
        self.classes["off"] = not s["on"]
        self.title_label.text = s["title"]
        self.sum_label.text = s.get("sum") or ""
        self.fields_panel.items = [{"spec": f, "model": s["model"], "rid": s["rid"]} for f in s["fields"]]
        self.fields_panel.add_event_handler("x-redraw", self._redraw)

    def _redraw(self, **event_args):
        self.parent.raise_event("x-redraw")

    def toggle(self, event):
        self.parent.raise_event("x-toggle-open", sid=self.item["id"], is_open=bool(getattr(anvil.js.get_dom_node(self.box), "open")))
