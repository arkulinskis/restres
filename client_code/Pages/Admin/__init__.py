import time

from anvil import *
import anvil.media

from ._anvil_designer import AdminTemplate
from ... import pp, state

TABS = ["overview", "feedback", "users", "demo", "import", "news"]


class Admin(AdminTemplate):
    """#admin/<tab>: overview numbers, the old feedback inbox, users (admin / active switches) and the demo data.
    Each tab is its own address, so the browser's back button works."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.tab = args[0] if args and args[0] in TABS else "overview"
        self._filter = "new"
        parts = {"overview": self.overview_part, "feedback": self.feedback_part,
                 "users": self.users_part, "demo": self.demo_part, "import": self.import_part, "news": self.news_part}
        tabs = {"overview": self.tab_overview, "feedback": self.tab_feedback,
                "users": self.tab_users, "demo": self.tab_demo, "import": self.tab_import, "news": self.tab_news}
        for name in TABS:
            parts[name].visible = name == self.tab
            tabs[name].classes["on"] = name == self.tab
        self.feedback_panel.add_event_handler("x-changed", self._feedback_changed)
        getattr(self, "_" + self.tab)()

    # ---- overview
    def _overview(self):
        d = state.call("admin_overview")
        self.s_users.text, self.s_admins.text = str(d["users"]), str(d["admins"])
        self.s_admins_label.text = "admin" if d["admins"] == 1 else "admins"
        self.s_feedback.text, self.s_items.text = str(d["feedback_new"]), str(d["restaurants"])
        self.demo_line.text = "The demo restaurant (Maison Lumière) is %s. Manage it in the Demo data tab." % d["demo"]["state"]

    # ---- feedback
    def _feedback(self):
        d = state.call("list_feedback", None)
        self._fb = d
        items = [i for i in d["items"] if self._filter == "all" or i["status"] == self._filter]
        self.feedback_panel.items = items
        self.no_feedback.visible = not items
        labels = {"new": "New", "read": "Read", "done": "Done", "all": "All"}
        for key, el in (("new", self.f_new), ("read", self.f_read), ("done", self.f_done), ("all", self.f_all)):
            n = len(d["items"]) if key == "all" else d["counts"].get(key, 0)
            el.text = "%s (%d)" % (labels[key], n)
            el.role = ["seg", "on"] if key == self._filter else ["seg"]

    def _set_filter(self, value):
        self._filter = value
        self._feedback()

    @handle("f_new", "click")
    def f_new_click(self, **event_args):
        self._set_filter("new")

    @handle("f_read", "click")
    def f_read_click(self, **event_args):
        self._set_filter("read")

    @handle("f_done", "click")
    def f_done_click(self, **event_args):
        self._set_filter("done")

    @handle("f_all", "click")
    def f_all_click(self, **event_args):
        self._set_filter("all")

    def _feedback_changed(self, **event_args):
        self._feedback()

    # ---- users
    def _users(self, query=None):
        d = state.call("list_users", query or None)
        self.users_panel.items = d["users"]
        self.users_count.text = state.plural(d["total"], "person", "people")

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self._users(self.search_box.text)

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        self._users(self.search_box.text)

    # ---- PlanPlate's news list (GuestNews.py: guests who ticked the optional box)
    def _news(self):
        d = state.call("admin_news")
        self.n_yes.text, self.n_stopped.text = str(d["subscribed"]), str(d["stopped"])
        self.news_csv_button.enabled = d["subscribed"] > 0
        if d["recent"]:
            lines = ["Latest:"] + ["  %s · %s · %s · %s" % (x["name"] or "-", x["email"], x["restaurant"] or "-", state.short_date(x["since"] or ""))
                                   for x in d["recent"]]
            self.news_recent.text = "\n".join(lines)
        else:
            self.news_recent.text = "Nobody yet. The box appears on every booking form, unticked."

    @handle("news_csv_button", "click")
    def news_csv_button_click(self, **event_args):
        media = state.call("admin_news_csv")
        if media:
            anvil.media.download(media)

    # ---- demo data
    def _demo(self):
        d = state.call("admin_overview")["demo"]
        counts = ", ".join("%s %s" % (v, k) for k, v in d["counts"].items())
        self.demo_status.text = "Status: %s · %s" % (d["state"], counts)
        self.demo_load_button.text = "Reload demo data" if d["state"] == "loaded" else "Load demo data"

    @handle("demo_load_button", "click")
    def demo_load_button_click(self, **event_args):
        if confirm("Maison Lumière, the demo restaurant, is rebuilt with fresh bookings (the old demo is replaced). Real restaurants are never touched.", title="Load the demo data?",
                   buttons=[("Cancel", False), ("Load", True)], role="app-dialog"):
            if state.call("demo_load"):
                state.toast("Done", "ok")
                self._demo()

    @handle("demo_remove_button", "click")
    def demo_remove_button_click(self, **event_args):
        if confirm("Every demo row is deleted. Real data stays.", title="Remove the demo data?",
                   buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
            if state.call("demo_remove"):
                state.toast("Done", "ok")
                self._demo()

    # ---- the old PlanPlate (CSV import, OldImport.py)
    def _import(self):
        self._csv = []
        self._choices = {}
        self.dom_nodes["tz"].innerHTML = pp.tz_field_html("timezone", "Europe/Riga", "ad_timezone")

    @handle("import_loader", "change")
    def import_loader_change(self, files=None, **event_args):
        self._csv = list(files or self.import_loader.files or [])
        self.import_files.text = ", ".join(f.name or "file" for f in self._csv)
        self.import_report.visible = False
        r = state.call("old_import_preview", self._csv) if self._csv else None
        self.import_button.enabled = bool(r)
        self.import_preview.visible = bool(r)
        self.import_choices.clear()
        self._choices = {}
        if r:
            s = r["summary"]
            lines = ["In these files:"] + ["  %s: %d rows" % (k, n) for k, n in sorted(s["counts"].items())]
            if s.get("missing"):
                lines += ["", "Not in the restaurants file (download that table again to bring these in):"]
                lines += ["  %s: %d bookings, %d menu files, %d people" % (x["id"], x["bookings"], x["menus"], x["team"]) for x in s["missing"]]
            if r.get("unknown"):
                lines += ["", "Not old PlanPlate tables (left out): " + ", ".join(r["unknown"])]
            self.import_preview.text = "\n".join(lines)
            for x in s["restaurants"]:
                bits = [state.plural(x["bookings"], "booking", "bookings")]
                if x["last"]:
                    bits.append("latest %s" % x["last"])
                bits.append(state.plural(x["team"], "person", "people"))
                if x["exists"]:
                    bits.append("already here: will be updated")
                cb = CheckBox(text="%s  ·  %s" % (x["name"], ", ".join(bits)), checked=bool(x["suggested"] or x["exists"]))
                self.import_choices.add_component(cb)
                self._choices[x["id"]] = cb
        self.import_choose.visible = self.import_choices.visible = bool(self._choices)

    @handle("import_button", "click")
    def import_button_click(self, **event_args):
        only = [uid for uid, cb in self._choices.items() if cb.checked]
        if self._choices and not only:
            alert("Tick at least one restaurant to bring in.", title="Nothing chosen", role="app-dialog")
            return
        if not confirm("%s come over. Restaurants already imported get their hours, special days and tables replaced by the old "
                       "ones; bookings, photos and people are added, and bookings nobody has touched here yet take the old app's "
                       "latest status." % state.plural(len(only), "restaurant", "restaurants"),
                       title="Import from the old PlanPlate?", buttons=[("Cancel", False), ("Import", True)], role="app-dialog"):
            return
        node = self.dom_nodes["tz"].querySelector("input[type=hidden]")
        r = state.call("old_import", self._csv, getattr(node, "value", None) or "Europe/Riga", only if self._choices else None)
        if not r:
            return
        self.import_button.enabled = False
        self.import_report.visible = True
        self.import_report.text = "Importing… (this page can stay open; thousands of bookings take a few minutes)"
        s = None
        while True:  # the import runs as a background task on the server; read its progress every 2 seconds
            s = state.call_quiet("old_import_status", r["job"])
            if s and (not s.get("ok") or s.get("state") in ("done", "failed")):
                break
            if s:
                part = " %d of %d" % (s["done"], s["total"]) if s.get("step") == "Bookings" and s.get("total") else ""
                self.import_report.text = "Importing… %s%s" % (s.get("step") or "", part)
            time.sleep(2)
        self.import_button.enabled = True
        if not s.get("ok") or s.get("state") == "failed":
            self.import_report.text = "The import stopped: %s\nNothing is lost: fix it and import again (nothing is added twice)." % (
                s.get("error") or "unknown error")
            return
        rep = s["report"]
        lines = ["Done."] + ["  %s: %d" % (k, n) for k, n in sorted(rep["counts"].items())]
        lines += ["", "Restaurants:"] + ["  %s (old id %s)" % (x["name"], x["old_id"]) for x in rep["restaurants"]]
        if rep["warnings"]:
            lines += ["", "To look at:"] + ["  - " + w for w in rep["warnings"]]
        self.import_report.text = "\n".join(lines)
        state.toast("Imported", "ok")
