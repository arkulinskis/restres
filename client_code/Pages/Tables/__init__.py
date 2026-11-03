from anvil import *
import anvil.server

from ._anvil_designer import TablesTemplate
from ... import pp, state


class Tables(TablesTemplate):
    """#tables/<rid>: the drag-and-drop floor plan. Pick a weekday and an hour to see the layout then; click a table to
    edit it; join tables for chosen hours and days (and split them again)."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_tables", self.rid)
        self.day = self.D["today_weekday"]
        oh = self.D["open_hours"]
        self.hour = self.D["now_hour"] if self.D["now_hour"] in oh else (19 if 19 in oh else (oh[0] if oh else 19))
        self.mode, self.sel, self.picks = "arrange", None, []
        self.j_hours, self.j_days = [], []
        for panel in (self.days_panel, self.hours_panel, self.j_hours_panel, self.j_days_panel):
            panel.add_event_handler("x-chip", self._chip)
        self.joins_panel.add_event_handler("x-save-join", self._save_join_event)
        self.joins_panel.add_event_handler("x-delete-join", self._delete_join_event)
        self._draw()

    # ---------------------------------------------------------------- helpers
    def _table(self, tid):
        for t in self.D["tables"]:
            if t["id"] == tid:
                return t
        return None

    def _active_joins(self):
        used, out = {}, []
        for j in self.D["joins"]:
            live = [i for i in j["tables"] if (self._table(i) or {}).get("active")]
            if len(live) < 2 or self.hour not in j["hours"] or (j["days"] and self.day not in j["days"]):
                continue
            if any(i in used for i in live):
                continue
            for i in live:
                used[i] = j
            out.append(j)
        return out, used

    def _apply(self, res, ok_msg=None):
        if not res:
            return False
        self.D = res
        if self.sel and not self._table(self.sel):
            self.sel = None
        self._draw()
        if ok_msg:
            state.toast(ok_msg, "ok")
        return True

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        D = self.D
        self.rnav.show(D["nav"])
        self.days_panel.items = [{"label": d, "value": i, "on": i == self.day, "group": "day"} for i, d in enumerate(pp.DAYS3)]
        self.hours_panel.items = [{"label": "%02d:00" % h, "value": h, "on": h == self.hour, "group": "hour"} for h in D["open_hours"]]
        joins, of = self._active_joins()
        sel = [self.sel] if self.mode == "arrange" and self.sel else (self.picks if self.mode == "join" else [])
        self.floor.draw({"tables": D["tables"], "draggable": self.mode == "arrange", "selected": sel,
                         "groups": [{"tables": j["tables"], "tag": "Joined · %d" % j["seats"]} for j in joins]})
        t = self._table(self.sel) if self.sel else None
        self.summary_part.visible = self.mode == "arrange" and t is None
        self.table_part.visible = self.mode == "arrange" and t is not None
        self.join_part.visible = self.mode == "join"
        if self.mode == "arrange" and t is None:
            units = len([x for x in D["tables"] if x["active"] and x["id"] not in of]) + len(joins)
            self.sum_title.text = "%s · %d seats" % (state.plural(len(D["tables"]), "table"), D["seats"])
            self.sum_text.text = ("Drag tables to arrange the room. Click one to edit it. On %s at %02d:00 guests can book %d separate tables."
                                  % (pp.DAYS[self.day], self.hour, units))
            self.join_mode_button.enabled = len(D["tables"]) >= 2
        elif t is not None:
            self.t_name.text, self.t_seats.text, self.t_min.text = t["name"], str(t["seats"]), str(t["min_party"])
            self.t_shape.selected_value, self.t_area.text, self.t_active.checked = t["shape"], t.get("area") or "", t["active"]
            j = of.get(t["id"])
            self.join_note.visible = j is not None
            if j:
                others = ", ".join((self._table(i) or {}).get("name", "") for i in j["tables"] if i != t["id"])
                self.join_note_label.text = "Joined with %s on %s at %02d:00." % (others, pp.DAYS[self.day], self.hour)
        self._draw_joins()
        if self.mode == "join":
            picks = [self._table(i) for i in self.picks if self._table(i)]
            self.j_title.text = " + ".join(p["name"] for p in picks) if picks else "Pick tables"
            self.j_form.visible = len(picks) >= 2
            self._join_chips()

    def _join_chips(self):
        if self.mode == "join":
            self.j_hours_panel.items = [{"label": "%02d:00" % h, "value": h, "on": h in self.j_hours, "group": "jh"} for h in self.D["open_hours"]]
            self.j_days_panel.items = [{"label": d, "value": i, "on": i in self.j_days, "group": "jd"} for i, d in enumerate(pp.DAYS3)]

    def _draw_joins(self):
        D = self.D
        hours = D["open_hours"]
        self.joins_panel.items = [dict(j, _names=" + ".join((self._table(i) or {}).get("name", "?") for i in j["tables"]),
                                       _hours=sorted(set(hours) | set(j["hours"]))) for j in D["joins"]]
        self.joins_empty.visible = not D["joins"]

    # ---------------------------------------------------------------- the day / hour pickers and the join form's chips
    def _chip(self, value, group, **event_args):
        if group == "day":
            self.day = value
        elif group == "hour":
            self.hour = value
        elif group == "jh":
            self.j_hours = [h for h in self.j_hours if h != value] if value in self.j_hours else self.j_hours + [value]
            return self._join_chips()
        elif group == "jd":
            self.j_days = [d for d in self.j_days if d != value] if value in self.j_days else self.j_days + [value]
            return self._join_chips()
        self._draw()

    # ---------------------------------------------------------------- the floor
    @handle("floor", "pick")
    def floor_pick(self, id, **event_args):
        if self.mode == "join":
            self.picks = [p for p in self.picks if p != id] if id in self.picks else self.picks + [id]
            self.j_seats.text = str(sum((self._table(i) or {}).get("seats", 0) for i in self.picks))
        else:
            self.sel = None if self.sel == id else id
        self._draw()

    @handle("floor", "move")
    def floor_move(self, id, x, y, **event_args):
        t = self._table(id)
        if t:
            t["x"], t["y"] = x, y
        anvil.server.call_s("save_positions", self.rid, [{"id": id, "x": x, "y": y}])
        self._draw()

    # ---------------------------------------------------------------- tables
    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        res = state.call("save_table", self.rid, {"name": "", "seats": 4})
        if self._apply(res, "Table added"):
            self.sel = res.get("new_id") or self.D["tables"][-1]["id"]
            self._draw()

    @handle("add_more_button", "click")
    def add_more_button_click(self, **event_args):
        self.add_button_click()

    @handle("deselect_button", "click")
    def deselect_button_click(self, **event_args):
        self.sel = None
        self._draw()

    @handle("save_table_button", "click")
    def save_table_button_click(self, **event_args):
        self._apply(state.call("save_table", self.rid, {"id": self.sel, "name": self.t_name.text, "seats": self.t_seats.text,
                                                        "shape": self.t_shape.selected_value, "min_party": self.t_min.text,
                                                        "area": self.t_area.text, "active": self.t_active.checked}), "Table saved")

    @handle("delete_table_button", "click")
    def delete_table_button_click(self, **event_args):
        t = self._table(self.sel)
        if t and confirm("It is removed from the floor plan and from any joins. Existing bookings keep their record.",
                         title="Delete %s?" % t["name"], buttons=[("Keep it", False), ("Delete table", True)]):
            self.sel = None
            self._apply(state.call("delete_table", self.rid, t["id"]), "Table deleted")

    def _split(self, all_day):
        joins, of = self._active_joins()
        j = of.get(self.sel)
        if j:
            hours = [] if all_day else [h for h in j["hours"] if h != self.hour]
            self._apply(state.call("save_join", self.rid, dict(j, hours=hours)))

    @handle("split_hour_button", "click")
    def split_hour_button_click(self, **event_args):
        self._split(False)

    @handle("split_all_button", "click")
    def split_all_button_click(self, **event_args):
        self._split(True)

    # ---------------------------------------------------------------- joins
    def _join_mode(self, picks):
        self.mode, self.sel, self.picks = "join", None, picks
        self.j_hours, self.j_days = list(self.D["open_hours"]), list(range(7))
        self.j_seats.text = str(sum((self._table(i) or {}).get("seats", 0) for i in picks))
        self._draw()

    @handle("join_mode_button", "click")
    def join_mode_button_click(self, **event_args):
        self._join_mode([])

    @handle("join_from_button", "click")
    def join_from_button_click(self, **event_args):
        self._join_mode([self.sel])

    @handle("join_done_button", "click")
    def join_done_button_click(self, **event_args):
        self.mode, self.picks = "arrange", []
        self._draw()

    @handle("join_button", "click")
    def join_button_click(self, **event_args):
        days = [] if len(self.j_days) == 7 else sorted(self.j_days)
        res = state.call("save_join", self.rid, {"tables": self.picks, "seats": self.j_seats.text, "hours": sorted(self.j_hours), "days": days})
        if self._apply(res, "Tables joined"):
            self.mode, self.picks = "arrange", []
            self._draw()

    def _save_join_event(self, join, **event_args):
        self._apply(state.call("save_join", self.rid, join))

    def _delete_join_event(self, join_id, **event_args):
        self._apply(state.call("delete_join", self.rid, join_id), "Tables split")
