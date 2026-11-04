from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import HoursTemplate
from ... import pp, state

COLORS = ["#7d8b6a", "#3d5a80", "#9c7a43", "#8a5a6a", "#5b7f86", "#a0714f", "#6b6f8a"]
SPECIAL = "#b5523b"


class Hours(HoursTemplate):
    """#hours/<rid>: opening-hour periods (the shorter one wins where they overlap), special days, and a month calendar
    showing what applies on each day."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_hours", self.rid)
        self.periods_panel.add_event_handler("x-edit", self._edit_period)
        self.periods_panel.add_event_handler("x-delete", self._delete_period)
        self.specials_panel.add_event_handler("x-edit", self._edit_special)
        self.specials_panel.add_event_handler("x-delete", self._delete_special)
        self.days_panel.add_event_handler("x-day", self._day)
        self._draw()

    def color(self, pid):
        ids = [p["id"] for p in self.D["periods"]]
        return COLORS[ids.index(pid) % len(COLORS)] if pid in ids else "transparent"

    def _draw(self):
        D = self.D
        self.rnav.show(D["nav"])
        self.periods_panel.items = [dict(p, _color=self.color(p["id"])) for p in D["periods"]]
        self.periods_empty.visible = not D["periods"]
        self.specials_panel.items = D["specials"]
        self.specials_card.visible = bool(D["specials"])
        self.specials_empty.visible = not D["specials"]
        self.past_label.visible = bool(D.get("past_specials"))
        self.past_label.text = state.plural(D.get("past_specials") or 0, "older special day") + " not shown."
        y, m = D["month"].split("-")
        self.month_label.text = "%s %s" % (pp.MONTHS[int(m) - 1], y)
        lead = pp.weekday(D["month"] + "-01")
        cells: list = [{"blank": True} for _ in range(lead)]
        for c in D["calendar"]:
            cells.append(dict(c, _color=SPECIAL if c["kind"] == "special" else self.color(c.get("period_id")),
                              _today=c["date"] == D["today"], _past=c["date"] < D["today"]))
        self.days_panel.items = cells
        legend = "".join('<span style="--c:%s"><i></i>%s</span>' % (self.color(p["id"]), window.PP.esc(p["name"])) for p in D["periods"])
        self.dom_nodes["legend"].innerHTML = legend + '<span style="--c:%s"><i></i>Special day</span>' % SPECIAL

    def _apply(self, res, msg=None):
        if res:
            self.D = res
            self._draw()
            if msg:
                state.toast(msg, "ok")

    # ---------------------------------------------------------------- month
    def _month(self, n):
        y, m = [int(x) for x in self.D["month"].split("-")]
        m += n
        if m < 1:
            y, m = y - 1, 12
        elif m > 12:
            y, m = y + 1, 1
        self._apply(state.call("get_hours", self.rid, "%04d-%02d" % (y, m)))

    @handle("prev_month", "click")
    def prev_month_click(self, **event_args):
        self._month(-1)

    @handle("next_month", "click")
    def next_month_click(self, **event_args):
        self._month(1)

    # ---------------------------------------------------------------- periods
    def _period_editor(self, period=None):
        from ...Dialogs.PeriodEditor import PeriodEditor
        res = alert(PeriodEditor(self.rid, self.D, period), buttons=[], role="app-dialog", large=True, dismissible=True)
        self._apply(res, "Hours saved" if res else None)

    @handle("new_period_button", "click")
    def new_period_button_click(self, **event_args):
        self._period_editor()

    def _edit_period(self, period, **event_args):
        self._period_editor(period)

    def _delete_period(self, period, **event_args):
        if confirm("Dates it covered fall back to your other periods, or are closed if none apply.",
                   title="Delete “%s”?" % period["name"], buttons=[("Keep it", False), ("Delete period", True)]):
            self._apply(state.call("delete_period", self.rid, period["id"], self.D["month"]), "Period deleted")

    # ---------------------------------------------------------------- special days
    def _special_editor(self, special=None, date=None):
        from ...Dialogs.SpecialEditor import SpecialEditor
        res = alert(SpecialEditor(self.rid, self.D, special, date), buttons=[], role="app-dialog", dismissible=True)
        self._apply(res, "Special day saved" if res else None)

    @handle("new_special_button", "click")
    def new_special_button_click(self, **event_args):
        self._special_editor()

    def _edit_special(self, special, **event_args):
        self._special_editor(special)

    def _delete_special(self, special, **event_args):
        self._apply(state.call("delete_special", self.rid, special["id"], self.D["month"]), "Special day removed")

    def _day(self, date, **event_args):
        hit = [s for s in self.D["specials"] if s["date"] == date]
        self._special_editor(hit[0] if hit else None, date)
