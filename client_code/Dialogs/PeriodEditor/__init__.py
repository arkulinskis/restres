import datetime

from anvil import *
import anvil.server

from ._anvil_designer import PeriodEditorTemplate


def _bad(ivs):
    return any(iv["close"] != "00:00" and iv["close"] <= iv["open"] for iv in ivs)


class PeriodEditor(PeriodEditorTemplate):
    """Add or change an opening-hours period: a name, optional dates, and each weekday's hours (split shifts allowed).
    Closes with the Hours page's new data, or None."""

    def __init__(self, rid, data, period=None, **properties):
        super().__init__(**properties)
        self.rid, self.D, self.period = rid, data, period
        is_new = period is None
        first = data["periods"][0]["week"] if data["periods"] else {}
        p: dict = period or {"name": "" if data["periods"] else "Regular hours", "start": None, "end": None, "week": first}
        self.eyebrow.text = "New period" if is_new else "Edit period"
        self.title_label.text = "Add opening hours" if is_new else p["name"]
        self.name_box.text = p["name"]
        self.start_picker.date = datetime.date.fromisoformat(p["start"]) if p.get("start") else None
        self.end_picker.date = datetime.date.fromisoformat(p["end"]) if p.get("end") else None
        self.days_panel.items = [{"day": i, "ivs": [{"open": a, "close": b} for a, b in (p["week"].get(str(i)) or [])]} for i in range(7)]

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        rows: list = list(self.days_panel.get_components())
        mon = [dict(iv) for iv in list(self.days_panel.items)[0]["ivs"]]
        for row in rows[1:]:
            getattr(row, "set_ivs")(mon)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        week = {str(d["day"]): [[iv["open"][:5], iv["close"][:5]] for iv in d["ivs"]] for d in self.days_panel.items}
        if any(_bad(d["ivs"]) for d in self.days_panel.items):
            self.message.visible, self.message.text = True, "Each closing time must be after its opening time."
            return
        data = {"id": self.period["id"] if self.period else None, "name": self.name_box.text or "",
                "start": self.start_picker.date.isoformat() if self.start_picker.date else None,
                "end": self.end_picker.date.isoformat() if self.end_picker.date else None, "week": week}
        r = anvil.server.call("save_period", self.rid, data, self.D["month"])
        if r and r.get("ok") is False:
            self.message.visible, self.message.text = True, r.get("error") or "Could not save."
            return
        self.raise_event("x-close-alert", value=r)
