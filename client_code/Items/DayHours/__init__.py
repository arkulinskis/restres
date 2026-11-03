from anvil import *

from ._anvil_designer import DayHoursTemplate
from ... import pp


def next_shift(ivs):
    """The hours a new shift gets: one long day becomes lunch + dinner; otherwise a 3-hour shift an hour after the last."""
    if not ivs:
        return [{"open": "12:00", "close": "22:00"}]
    last = ivs[-1]
    if last["open"] < "15:00" and (last["close"] > "18:00" or last["close"] == "00:00"):
        return ivs[:-1] + [{"open": last["open"], "close": "15:00"}, {"open": "18:00", "close": last["close"]}]
    s0 = 1380 if last["close"] == "00:00" else min(pp.to_min(last["close"]) + 60, 1380)
    e0 = min(s0 + 180, 1440)
    return ivs + [{"open": pp.hm(s0), "close": "00:00" if e0 >= 1440 else pp.hm(e0)}]


class DayHours(DayHoursTemplate):
    """One weekday in the period editor: open or closed, and its opening hours (one or more shifts).
    item = {day, ivs: [{open, close}]}; the intervals are edited in place."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.open_box.text = pp.DAYS[self.item["day"]]
        self.ivs_panel.add_event_handler("x-remove", self._remove)
        self._draw()

    def _draw(self):
        ivs = self.item["ivs"]
        self.open_box.checked = bool(ivs)
        self.ivs_panel.items = ivs
        self.closed_label.visible = not ivs
        self.add_button.visible = bool(ivs)

    def set_ivs(self, ivs):
        self.item["ivs"] = [dict(iv) for iv in ivs]
        self._draw()

    @handle("open_box", "change")
    def open_box_change(self, **event_args):
        self.set_ivs([{"open": "12:00", "close": "22:00"}] if self.open_box.checked else [])

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        self.set_ivs(next_shift(self.item["ivs"]))

    def _remove(self, item, **event_args):
        self.set_ivs([iv for iv in self.item["ivs"] if iv is not item])
