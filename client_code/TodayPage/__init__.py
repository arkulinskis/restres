# TodayPage — Custom HTML form. HTML: forms/TodayPage.html
# The restaurant's day at a glance (Board.get_today), with quick changes: today's hours, specials, photo of the day.
from ._anvil_designer import TodayPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class TodayPage(TodayPageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_today", restaurant_id)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "today", self.data, self._on_event, rid=self.rid)

    def _on_event(self, event, p):
        if event == "quick_hours":
            return pp_ui.call("quick_hours", self.rid, p.get("action"), p.get("hours"), p.get("label"))
        if event == "save_special":
            return pp_ui.call("save_dish_special", self.rid, p)
        if event == "toggle_special":
            return pp_ui.call("toggle_dish_special", self.rid, p["id"], bool(p.get("active")))
        if event == "delete_special":
            return pp_ui.call("delete_dish_special", self.rid, p["id"])
        if event == "post":
            return pp_ui.call("post_photo", self.rid, p)
        if event == "delete_post":
            return pp_ui.call("delete_post", self.rid, p["id"])
