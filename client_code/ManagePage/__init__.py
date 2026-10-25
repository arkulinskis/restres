# ManagePage — Custom HTML form. HTML: forms/ManagePage.html. A guest's reservation page (#r/<token>).
from ._anvil_designer import ManagePageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class ManagePage(ManagePageTemplate):
    def __init__(self, token=None, **properties):
        super().__init__(**properties)
        self.token = token
        self.data = anvil.server.call("get_reservation", token)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "manage", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "slots":
            slug = self.data.get("restaurant", {}).get("slug")
            return anvil.server.call_s("get_slots", slug, p.get("date"), p.get("party"), self.token)
        if event == "change":
            return anvil.server.call("change_reservation", self.token, p)
        if event == "cancel":
            return anvil.server.call("cancel_reservation", self.token)
