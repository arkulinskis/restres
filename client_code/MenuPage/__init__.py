# MenuPage — Custom HTML form. HTML: forms/MenuPage.html. The public menu (#menu/<slug>).
from ._anvil_designer import MenuPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class MenuPage(MenuPageTemplate):
    def __init__(self, slug=None, **properties):
        super().__init__(**properties)
        self.data = anvil.server.call("get_menu", slug)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "menu", self.data)
