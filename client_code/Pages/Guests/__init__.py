from anvil import *
import anvil.server

from ._anvil_designer import GuestsTemplate
from ... import state


class Guests(GuestsTemplate):
    """#guests/<rid>: the guest book. Regulars, no-shows, notes and tags, and each guest's visits (Dialogs.GuestCard)."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.guests_panel.add_event_handler("x-open", self._open)
        self.sort_drop.selected_value = "recent"
        self._load()

    def _load(self):
        self.D = anvil.server.call("get_guests", self.rid, self.search_box.text or "", self.sort_drop.selected_value)
        self.rnav.show(self.D["nav"])
        st = self.D["stats"]
        self.summary_label.text = "%s · %d regulars (3+ visits) · %d with a no-show" % (state.plural(self.D["total"], "guest"),
                                                                                       st["regulars"], st["no_show_guests"])
        self.guests_panel.items = self.D["guests"]
        self.list_card.visible = bool(self.D["guests"])
        self.empty.visible = not self.D["guests"]

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self._load()

    @handle("search_box", "lost_focus")
    def search_box_lost_focus(self, **event_args):
        self._load()

    @handle("sort_drop", "change")
    def sort_drop_change(self, **event_args):
        self._load()

    def _open(self, guest, **event_args):
        from ...Dialogs.GuestCard import GuestCard
        if alert(GuestCard(self.rid, guest["key"]), buttons=[], role="app-dialog", large=True, dismissible=True):
            self._load()
