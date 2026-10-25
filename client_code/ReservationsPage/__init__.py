# ReservationsPage — Custom HTML form. HTML: forms/ReservationsPage.html
from ._anvil_designer import ReservationsPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class ReservationsPage(ReservationsPageTemplate):
    def __init__(self, restaurant_id=None, day=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_day", restaurant_id, day)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "reservations", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "day":
            return anvil.server.call("get_day", self.rid, p.get("date"))
        if event == "options":
            return pp_ui.call("get_options", self.rid, p.get("date"), p.get("time"), p.get("party"), p.get("duration"), p.get("id"))
        if event == "save":
            res = pp_ui.call("save_reservation", self.rid, p)
            if res.get("ok"):
                get_open_form().refresh_alerts()
            return res
        if event == "status":
            res = pp_ui.call("set_status", self.rid, p["id"], p["status"], p.get("day"))
            if res.get("ok"):
                get_open_form().refresh_alerts(res.get("alerts"))
            return res
