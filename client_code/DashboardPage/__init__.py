# DashboardPage — Custom HTML form. HTML: forms/DashboardPage.html
from ._anvil_designer import DashboardPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class DashboardPage(DashboardPageTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.data = anvil.server.call("get_dashboard")
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "dashboard", self.data, self._on_event)
        get_open_form().refresh_alerts(self.data["me"]["alerts"])

    def _on_event(self, event, p):
        if event == "open":
            get_open_form().go(p.get("page", "today"), restaurant_id=p["id"])
        elif event == "create":
            res = pp_ui.call("create_restaurant", p.get("name"), p.get("timezone") or pp_ui.browser_timezone(), bool(p.get("sample")))
            if res.get("ok"):
                get_open_form().go("hours", restaurant_id=res["id"])
            return res
        elif event == "duplicate":
            res = pp_ui.call("duplicate_restaurant", p["id"], p.get("name"))
            if res.get("ok"):
                pp_ui.toast("Restaurant copied")
                get_open_form().go("settings", restaurant_id=res["id"])
            return res
