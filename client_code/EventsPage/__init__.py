# EventsPage — Custom HTML form. HTML: forms/EventsPage.html
# Planned events and the room set-up for each (Board.get_events / save_event / save_event_setup / delete_event).
from ._anvil_designer import EventsPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class EventsPage(EventsPageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_events", restaurant_id)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "events", self.data, self._on_event, rid=self.rid)

    def _on_event(self, event, p):
        if event == "save_event":
            return pp_ui.call("save_event", self.rid, p)
        if event == "delete_event":
            return pp_ui.call("delete_event", self.rid, p["id"])
        if event == "save_setup":
            return pp_ui.call("save_event_setup", self.rid, p["id"], p)
