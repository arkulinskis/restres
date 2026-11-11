import copy

from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import EventsTemplate
from ... import pp, state

HELP = {"move": "Drag tables to where they go for this event.",
        "group": "Tap tables to push them together, then save them as one long table.",
        "out": "Tap tables to take them out of the room (for a dance floor, a buffet or a band)."}


class Events(EventsTemplate):
    """#events/<rid>: planned events (wine dinners, live music, private parties) and each one's room set-up. A private
    event can close online booking for its hours; a public one shows on the website. During an event, bookings use its
    room (Booking.units_at)."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_events", self.rid)
        self.sel, self.mode, self.picks, self.dirty = None, "move", [], False
        self.setup: dict = {"layout": {}, "groups": [], "removed": []}
        for p in (self.upcoming_panel, self.past_panel):
            p.add_event_handler("x-edit", self._edit)
            p.add_event_handler("x-delete", self._delete)
            p.add_event_handler("x-setup", self._start_setup)
        self.groups_panel.add_event_handler("x-ungroup", self._ungroup)
        self.groups_panel.add_event_handler("x-seats", self._group_seats)
        self._draw()

    # ---------------------------------------------------------------- helpers
    def _table(self, tid):
        for t in self.D["tables"]:
            if t["id"] == tid:
                return t
        return None

    def _event(self, eid):
        for e in self.D["upcoming"] + self.D["past"]:
            if e["id"] == eid:
                return e
        return None

    def _everyday(self, e):
        hour, wd = int(e["start"].split(":")[0]), pp.weekday(e["date"])
        return [{"tables": list(j["tables"]), "seats": j["seats"], "label": j.get("label") or ""} for j in self.D["joins"]
                if hour in j["hours"] and (not j["days"] or wd in j["days"])]

    def _group_of(self, tid):
        for i, g in enumerate(self.setup["groups"]):
            if tid in g["tables"]:
                return i
        return -1

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        D = self.D
        self.rnav.show(D["nav"])
        e = self._event(self.sel) if self.sel else None
        self.list_part.visible = e is None
        self.setup_part.visible = e is not None
        if e is None:
            self.upcoming_panel.items = [dict(x, _past=False) for x in D["upcoming"]]
            self.empty.visible = not D["upcoming"]
            self.past_box.visible = bool(D["past"])
            self.past_panel.items = [dict(x, _past=True) for x in D["past"]]
            anvil.js.get_dom_node(self.past_summary).textContent = "Past events (%d)" % len(D["past"])
            return
        self._draw_setup(e)

    def _draw_setup(self, e):
        S: dict = self.setup
        self.setup_when.text = "Room set-up · %s · %s–%s" % (pp.fmt_date(e["date"]), e["start"], e["end"])
        self.setup_title.text = e["title"]
        self.setup_meta.text = " · ".join(x for x in [("%d guests expected" % e["guests"]) if e.get("guests") else "",
                                                       "Private event" if e["kind"] == "private" else "Public event", e.get("host") or ""] if x)
        self.setup_notes.visible = bool(e.get("notes"))
        self.setup_notes.text = "Notes: " + (e.get("notes") or "")
        tables = [dict(t, x=S["layout"][t["id"]][0], y=S["layout"][t["id"]][1]) for t in self.D["tables"]]
        groups = [{"tables": g["tables"], "tag": "%s · %s" % (g.get("label") or "Together", g["seats"])} for g in S["groups"]]
        self.floor.draw({"tables": tables, "groups": groups, "out": S["removed"], "selected": self.picks, "draggable": self.mode == "move"})
        for name, el in (("move", self.m_move), ("group", self.m_group), ("out", self.m_out)):
            el.classes["on"] = self.mode == name
        self.mode_help.text = HELP[self.mode]
        picks = [self._table(i) for i in self.picks if self._table(i)]
        self.group_form.visible = self.mode == "group" and len(picks) >= 2
        self.group_names.text = " + ".join(t["name"] for t in picks)
        seats, units, used = 0, 0, set()
        for g in S["groups"]:
            live = [i for i in g["tables"] if i not in S["removed"] and self._table(i)]
            if len(live) >= 2:
                seats += int(g["seats"] or 0)
                units += 1
                used.update(live)
        for t in self.D["tables"]:
            if t["id"] not in used and t["id"] not in S["removed"]:
                seats += t["seats"]
                units += 1
        self.capacity_label.text = "During the event guests can be seated at %s with %d seats (%d on a normal day)." % (state.plural(units, "table"), seats, self.D["seats"])
        self.groups_panel.items = [{"i": i, "label": g.get("label") or " + ".join((self._table(t) or {}).get("name", "?") for t in g["tables"]),
                                    "seats": g["seats"]} for i, g in enumerate(S["groups"])]
        self.removed_label.visible = bool(S["removed"])
        self.removed_label.text = "Taken out: " + ", ".join((self._table(i) or {}).get("name", "?") for i in S["removed"])
        self.save_setup_button.enabled = self.dirty

    def _apply(self, res, msg=None):
        if res and res.get("ok") is not False:
            self.D = res
            self._draw()
            if msg:
                state.toast(msg, "ok")
            return True
        if res:
            state.toast(res.get("error") or "That didn't work.", "error")
        return False

    # ---------------------------------------------------------------- the list
    def _editor(self, event=None):
        from ...Dialogs.EventEditor import EventEditor
        res = alert(EventEditor(self.rid, self.D, event), buttons=[], role="app-dialog", large=True, dismissible=True)
        if res and self._apply(res, "Event saved") and event is None and res.get("id"):
            self._start_setup(self._event(res["id"]))

    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        self._editor()

    def _edit(self, event, **event_args):
        self._editor(event)

    def _delete(self, event, **event_args):
        text = "Its room set-up goes too. Bookings are not touched" + (", and online booking reopens for those hours." if event.get("blocks") else ".")
        if confirm(text, title="Delete “%s”?" % event["title"], buttons=[("Keep it", False), ("Delete event", True)]):
            self._apply(state.call("delete_event", self.rid, event["id"]), "Event deleted")

    # ---------------------------------------------------------------- the room set-up
    def _start_setup(self, event, **event_args):
        if event is None:
            return
        layout = {}
        for t in self.D["tables"]:
            p = (event.get("layout") or {}).get(t["id"])
            layout[t["id"]] = [p[0], p[1]] if p else [t["x"], t["y"]]
        groups = copy.deepcopy(event.get("groups") or []) if event.get("has_setup") else self._everyday(event)
        self.setup = {"layout": layout, "groups": groups, "removed": list(event.get("removed") or [])}
        self.sel, self.mode, self.picks, self.dirty = event["id"], "move", [], False
        self._draw()
        window.scrollTo(0, 0)

    @handle("back_button", "click")
    def back_button_click(self, **event_args):
        if self.dirty and not confirm("Your changes to the layout will be lost.", title="Leave without saving the room?",
                                      buttons=[("Stay", False), ("Leave", True)]):
            return
        self.sel = None
        self._draw()

    def mode_click(self, event):
        self.mode, self.picks = event.currentTarget.getAttribute("data-mode"), []
        self._draw()

    @handle("floor", "move")
    def floor_move(self, id, x, y, **event_args):
        self.setup["layout"][id] = [x, y]
        self.dirty = True
        self._draw()

    @handle("floor", "pick")
    def floor_pick(self, id, **event_args):
        S: dict = self.setup
        if self.mode == "group":
            if id in S["removed"]:
                return state.toast("That table is taken out. Put it back first.", "error")
            if self._group_of(id) >= 0:
                return state.toast("Already pushed together. Split that group first.", "error")
            self.picks = [p for p in self.picks if p != id] if id in self.picks else self.picks + [id]
            self.g_seats.text = str(sum((self._table(i) or {}).get("seats", 0) for i in self.picks))
        elif self.mode == "out":
            if id in S["removed"]:
                S["removed"] = [x for x in S["removed"] if x != id]
            else:
                g = self._group_of(id)
                if g >= 0:
                    S["groups"].pop(g)
                S["removed"].append(id)
            self.dirty = True
        self._draw()

    @handle("make_group_button", "click")
    def make_group_button_click(self, **event_args):
        try:
            seats = max(1, int(self.g_seats.text or 2))
        except ValueError:
            seats = 2
        self.setup["groups"].append({"tables": list(self.picks), "seats": seats, "label": self.g_label.text or ""})
        self.picks, self.dirty = [], True
        self.g_label.text = ""
        self._draw()

    def _ungroup(self, index, **event_args):
        self.setup["groups"].pop(index)
        self.dirty = True
        self._draw()

    def _group_seats(self, index, seats, **event_args):
        self.setup["groups"][index]["seats"] = seats
        self.dirty = True
        self.save_setup_button.enabled = True

    @handle("everyday_button", "click")
    def everyday_button_click(self, **event_args):
        e = self._event(self.sel)
        for t in self.D["tables"]:
            self.setup["layout"][t["id"]] = [t["x"], t["y"]]
        self.setup["groups"], self.setup["removed"], self.dirty = self._everyday(e), [], True
        self._draw()

    @handle("save_setup_button", "click")
    def save_setup_button_click(self, **event_args):
        res = state.call("save_event_setup", self.rid, self.sel, self.setup)
        if res:
            self.dirty = False
            sel = self.sel
            self._apply(res, "Room saved. Bookings during the event use this layout.")
            self.sel = sel
            self._draw()

    @handle("print_button", "click")
    def print_button_click(self, **event_args):
        pp.html_class("pp-print-setup", True)
        window.print()
        pp.html_class("pp-print-setup", False)

