from anvil import *
import anvil.server

from ._anvil_designer import NewRestaurantTemplate
from ... import pp


class NewRestaurant(NewRestaurantTemplate):
    """Create a restaurant (name, time zone, sample set-up), or duplicate one (copy_of = a dashboard restaurant).
    Closes with the new restaurant's id, or None."""

    def __init__(self, copy_of=None, **properties):
        super().__init__(**properties)
        self.copy_of = copy_of
        if copy_of:
            self.eyebrow.text = "Duplicate"
            self.title_label.text = "Copy " + copy_of["name"]
            self.intro.visible = True
            self.intro.text = ("The copy gets the same settings, opening hours, special days, tables and joins. "
                               "Reservations stay with the original.")
            self.name_caption.text = "Name of the new restaurant"
            self.name_box.text = copy_of["name"] + " (copy)"
            self.tz_part.visible = False
            self.sample_box.visible = False
            self.save_button.text = "Duplicate"
        else:
            self.dom_nodes["tz"].innerHTML = pp.tz_field_html("timezone", pp.browser_tz(), "nrTz")

    def _say(self, msg):
        self.message.visible = bool(msg)
        self.message.text = msg or ""

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("name_box", "pressed_enter")
    def name_box_pressed_enter(self, **event_args):
        self.save_button_click()

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        name = (self.name_box.text or "").strip()
        if not name:
            self._say("Please give it a name.")
            return
        self.save_button.enabled = False
        try:
            if self.copy_of:
                r = anvil.server.call("duplicate_restaurant", self.copy_of["id"], name)
            else:
                node = self.dom_nodes["tz"].querySelector("input[type=hidden]")
                tz = getattr(node, "value", "UTC") if node else "UTC"
                r = anvil.server.call("create_restaurant", name, tz, bool(self.sample_box.checked))
        finally:
            self.save_button.enabled = True
        if r and r.get("ok"):
            self.raise_event("x-close-alert", value=r["id"])
        else:
            self._say((r or {}).get("error") or "That didn't work.")

    @handle("", "show")
    def form_show(self, **event_args):
        self.name_box.focus()
