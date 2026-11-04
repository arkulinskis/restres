from anvil import *

from ._anvil_designer import TeamRowTemplate
from ... import pp


class TeamRow(TeamRowTemplate):
    """A team member (Settings -> Team). item = {id, email, name, role, joined, _owner_view}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        m = self.item
        self.name_label.text = m.get("name") or m["email"]
        self.email_label.visible = bool(m.get("name"))
        self.email_label.text = m["email"]
        self.invited_badge.visible = not m.get("joined")
        can_edit = bool(m.get("_owner_view")) and m["role"] != "owner"
        self.role_drop.visible = self.remove_button.visible = can_edit
        self.role_badge.visible = not can_edit
        self.role_badge.text = pp.ROLE.get(m["role"], m["role"])
        if can_edit:
            self.role_drop.selected_value = m["role"]

    @handle("role_drop", "change")
    def role_drop_change(self, **event_args):
        self.parent.raise_event("x-role", member=self.item, role=self.role_drop.selected_value)

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        self.parent.raise_event("x-remove", member=self.item)
