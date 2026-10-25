# SettingsPage — Custom HTML form. HTML: forms/SettingsPage.html
from ._anvil_designer import SettingsPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class SettingsPage(SettingsPageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_settings", restaurant_id)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "settings", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "save":
            return pp_ui.call("save_settings", self.rid, p)
        if event == "invite":
            return pp_ui.call("invite_member", self.rid, p.get("email"), p.get("role"))
        if event == "set_role":
            return pp_ui.call("set_member_role", self.rid, p["id"], p["role"])
        if event == "remove_member":
            return pp_ui.call("remove_member", self.rid, p["id"])
        if event == "delete":
            res = pp_ui.call("delete_restaurant", self.rid, p.get("confirm_name"))
            if res.get("ok"):
                pp_ui.toast("Restaurant deleted")
                get_open_form().go("dashboard")
            return res
