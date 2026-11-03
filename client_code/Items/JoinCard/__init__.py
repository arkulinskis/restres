from anvil import *

from ._anvil_designer import JoinCardTemplate
from ... import pp, state


class JoinCard(JoinCardTemplate):
    """A join in Tables & layout: its hours and days are chips (click to split or join an hour / a day).
    item = a join + _names, _hours. Raises x-save-join(join=) and x-delete-join(join_id=) on the RepeatingPanel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        j = self.item
        self.name_label.text = j.get("label") or j["_names"]
        self.seats_badge.text = "%d seats" % j["seats"]
        self.hours_panel.items = [{"label": "%02d:00" % h, "value": h, "on": h in j["hours"]} for h in j["_hours"]]
        self.days_panel.items = [{"label": d, "value": i, "on": not j["days"] or i in j["days"]} for i, d in enumerate(pp.DAYS3)]
        self.hours_panel.add_event_handler("x-chip", self._hour)
        self.days_panel.add_event_handler("x-chip", self._day)

    def _save(self, **changes):
        join = {k: v for k, v in self.item.items() if not k.startswith("_")}
        join.update(changes)
        self.parent.raise_event("x-save-join", join=join)

    def _hour(self, value, **event_args):
        hours = self.item["hours"]
        hours = [h for h in hours if h != value] if value in hours else hours + [value]
        if not hours and not confirm("With no hours left, the join is removed and the tables are booked separately.",
                                     title="Split these tables all day?", buttons=[("Keep them", False), ("Split them", True)]):
            return
        self._save(hours=sorted(hours))

    def _day(self, value, **event_args):
        days = list(self.item["days"]) or list(range(7))
        days = [d for d in days if d != value] if value in days else days + [value]
        if not days:
            state.toast("Keep at least one day, or split the tables for good.", "error")
            return
        self._save(days=[] if len(days) == 7 else sorted(days))

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("They will always be booked separately.", title="Split these tables for good?",
                   buttons=[("Keep them", False), ("Split them", True)]):
            self.parent.raise_event("x-delete-join", join_id=self.item["id"])
