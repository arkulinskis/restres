# MenuEditPage — Custom HTML form. HTML: forms/MenuEditPage.html
from ._anvil_designer import MenuEditPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class MenuEditPage(MenuEditPageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_menu_admin", restaurant_id)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "menuedit", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "save_section":
            return pp_ui.call("save_section", self.rid, p)
        if event == "delete_section":
            return pp_ui.call("delete_section", self.rid, p["id"])
        if event == "save_item":
            return pp_ui.call("save_item", self.rid, p)
        if event == "delete_item":
            return pp_ui.call("delete_item", self.rid, p["id"])
        if event == "move":
            return pp_ui.call("move_menu_row", self.rid, p["kind"], p["id"], p["step"])
