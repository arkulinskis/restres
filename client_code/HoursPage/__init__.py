# HoursPage — Custom HTML form. HTML: forms/HoursPage.html
from ._anvil_designer import HoursPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class HoursPage(HoursPageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_hours", restaurant_id)
        self.month = self.data["month"]
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "hours", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "month":
            self.month = p.get("month")
            return pp_ui.call("get_hours", self.rid, self.month)
        if event == "save_period":
            return pp_ui.call("save_period", self.rid, p, self.month)
        if event == "delete_period":
            return pp_ui.call("delete_period", self.rid, p["id"], self.month)
        if event == "save_special":
            return pp_ui.call("save_special", self.rid, p, self.month)
        if event == "delete_special":
            return pp_ui.call("delete_special", self.rid, p["id"], self.month)
