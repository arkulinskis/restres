# TablesPage — Custom HTML form. HTML: forms/TablesPage.html
from ._anvil_designer import TablesPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class TablesPage(TablesPageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_tables", restaurant_id)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "tables", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "save_table":
            return pp_ui.call("save_table", self.rid, p)
        if event == "delete_table":
            return pp_ui.call("delete_table", self.rid, p["id"])
        if event == "save_positions":
            return anvil.server.call_s("save_positions", self.rid, p.get("positions"))
        if event == "save_join":
            return pp_ui.call("save_join", self.rid, p)
        if event == "delete_join":
            return pp_ui.call("delete_join", self.rid, p["id"])
