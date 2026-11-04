import datetime

from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import SlotPickerTemplate
from ... import i18n, pp

T = i18n.T


class SlotPicker(SlotPickerTemplate):
    """Guests, date and time for a booking (see the help text in form_template.html)."""

    def __init__(self, **properties):
        self.slug, self.token, self.days, self.today, self.max_party = "", None, [], None, 8
        self.party, self.date, self.time, self.review = 2, None, None, False
        self.month = ""
        self.slots: dict = {}
        self.error = ""
        self.init_components(**properties)
        self.party_panel.add_event_handler("x-chip", self._party)
        self.times_panel.add_event_handler("x-chip", self._time)
        self.days_panel.add_event_handler("x-day", self._day)

    def setup(self, slug, days, today=None, max_party=8, party=2, date=None, time=None, token=None):
        """days = [{date, open}] from the server; token = the guest's own booking (left out of the availability)."""
        self.slug, self.days, self.today, self.max_party, self.token = slug, days, today, max_party or 8, token
        self.open = {d["date"]: d["open"] for d in days}
        self.party, self.time = party or 2, time
        self.date = date if date in self.open else None
        if not self.date:
            first = [d["date"] for d in days if d["open"]]
            self.date = first[0] if first else None
        self.month = (self.date or (days[0]["date"] if days else today) or pp.today_iso())[:7]
        self._load()

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        self.guests_h.text, self.date_h.text = T("guests"), T("date")
        self.time_h.text = T("time") + (" · " + pp.fmt_date(self.date) if self.date else "")
        top = min(self.max_party, 8)
        self.party_panel.items = [{"label": str(i), "value": i, "on": self.party == i} for i in range(1, top + 1)]
        self.more_drop.visible = self.max_party > 8
        if self.max_party > 8:
            self.more_drop.items = [(T("more"), 0)] + [(str(i), i) for i in range(9, self.max_party + 1)]
            self.more_drop.selected_value = self.party if self.party > 8 else 0
        self._draw_month()
        self._draw_times()

    def _draw_month(self):
        y, m = [int(x) for x in self.month.split("-")]
        first = datetime.date(y, m, 1)
        self.month_label.text = window.PP.parseDate(self.month + "-01").toLocaleDateString(i18n.LOCALES[i18n.lang()], {"month": "long", "year": "numeric"})
        loc = i18n.LOCALES[i18n.lang()]
        self.wd_panel.items = [{"head": window.PP.parseDate("2024-01-0%d" % (i + 1)).toLocaleDateString(loc, {"weekday": "short"})[:2]} for i in range(7)]
        cells: list = [{"blank": True} for _ in range(first.weekday())]
        d = first
        while d.month == m:
            iso = d.isoformat()
            cells.append({"date": iso, "day": d.day, "open": self.open.get(iso) is True, "on": iso == self.date, "today": iso == self.today})
            d += datetime.timedelta(days=1)
        self.days_panel.items = cells
        dates = [x["date"] for x in self.days]
        self.prev_button.enabled = bool(dates) and self.month > dates[0][:7]
        self.next_button.enabled = bool(dates) and self.month < dates[-1][:7]

    def _draw_times(self):
        r: dict = self.slots
        self.times_panel.items = []
        self.review_note.visible = self.walk_note.visible = False
        msg = ""
        if not self.date:
            msg = T("pickDate")
        elif self.error:
            msg = str(self.error)
        elif not r:
            msg = T("loading")
        elif r.get("closed"):
            msg = T("closedDay") + ((" · " + r["label"]) if r.get("label") else "")
        else:
            any_open = any(s["state"] == "open" for s in r["slots"])
            walk = any(s["state"] == "walk_in" for s in r["slots"])
            rev = any(s.get("review") and s["state"] == "open" for s in r["slots"])
            if not any_open:
                msg = T("noTimes", n=self.party)
            items: list = []
            slots: list = list(r.get("slots") or [])
            for s in slots:
                if s["state"] == "open":
                    items.append({"label": s["time"] + (" •" if s.get("review") else ""), "value": s["time"], "on": self.time == s["time"]})
                elif s["state"] == "walk_in" and any_open:
                    items.append({"label": "%s · %s" % (s["time"], T("walkIn")), "value": None, "disabled": True, "title": T("walkNote")})
            self.times_panel.items = items
            self.review_note.visible, self.review_note.text = rev, "• " + T("reviewNote")
            self.walk_note.visible, self.walk_note.text = walk, T("walkNote")
        self.times_msg.visible = bool(msg)
        self.times_msg.text = msg

    def _load(self):
        self.slots, self.error = {}, ""
        self._draw()
        if not self.date:
            return
        try:
            r: dict = anvil.server.call("get_slots", self.slug, self.date, self.party, self.token)
        except Exception as e:
            r = {"ok": False, "error": str(e)}
        if not r or r.get("ok") is False:
            self.error = str((r or {}).get("error") or "Could not load times.")
        else:
            self.slots = r
            slots: list = list(r.get("slots") or [])
            still = [s for s in slots if s["time"] == self.time and s["state"] == "open"]
            self.time = self.time if still else None
            self.review = bool(still and still[0].get("review"))
        self._draw()
        self.raise_event("change")

    # ---------------------------------------------------------------- choices
    def _party(self, value, **event_args):
        self.party, self.time = value, None
        self._load()

    @handle("more_drop", "change")
    def more_drop_change(self, **event_args):
        if self.more_drop.selected_value:
            self._party(self.more_drop.selected_value)

    def _day(self, date, **event_args):
        self.date, self.time = date, None
        self._load()

    def _time(self, value, **event_args):
        if value:
            self.time = value
            self.review = any(s["time"] == value and s.get("review") for s in list(self.slots.get("slots") or []))
            self._draw_times()
            self.raise_event("change")

    def _shift(self, n):
        y, m = [int(x) for x in self.month.split("-")]
        m += n
        if m < 1:
            y, m = y - 1, 12
        elif m > 12:
            y, m = y + 1, 1
        self.month = "%04d-%02d" % (y, m)
        self._draw_month()

    @handle("prev_button", "click")
    def prev_button_click(self, **event_args):
        self._shift(-1)

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        self._shift(1)

    def redraw(self):
        """After a language change."""
        self._draw()
