# BookPage — Custom HTML form. HTML: forms/BookPage.html. The public booking form (#book/<slug>).
from ._anvil_designer import BookPageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class BookPage(BookPageTemplate):
    def __init__(self, slug=None, **properties):
        super().__init__(**properties)
        self.slug = slug
        self.data = anvil.server.call("get_booking_form", slug)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "book", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "slots":
            return anvil.server.call_s("get_slots", self.slug, p.get("date"), p.get("party"))
        if event == "book":
            return anvil.server.call("book", self.slug, p)
