from anvil import *
import anvil.server

from ._anvil_designer import TodayTemplate
from ... import pp, router, state


class Today(TodayTemplate):
    """#today/<rid>: the daily check-in, made for a phone. Open now?, today's bookings and who's next, the week ahead,
    quick changes to today's hours, specials, photo of the day, upcoming events, website visits, a set-up checklist."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_today", self.rid)
        self.specials_panel.add_event_handler("x-edit", self._edit_special)
        self.specials_panel.add_event_handler("x-toggle", self._toggle_special)
        self.arrivals_panel.add_event_handler("x-status", self._arrival_status)
        self._draw()

    def _arrival_status(self, res, status, **event_args):
        """One tap in Who's coming: Seat a guest who arrived, or Finish a table that left."""
        r = state.call("set_status", self.rid, res["id"], status)
        if r:
            state.toast("Seated" if status == "seated" else "Finished", "ok")
            self.D = anvil.server.call("get_today", self.rid)
            self._draw()
            shell = getattr(self, "layout", None)
            if shell is not None and hasattr(shell, "refresh_alerts"):
                shell.refresh_alerts()

    def _draw(self):
        D, rid = self.D, self.rid
        self.rnav.show(D["nav"])
        st, m = D["status"], D["can_manage"]
        self.when_label.text = "%s · %s" % (pp.fmt_date(D["today"]), D["now"])
        self.dot.classes.update({"open": st["state"] == "open", "soon": st["state"] == "later", "closed": st["state"] == "closed"})
        self.state_label.text = st["text"]
        self.hours_label.text = "Today: %s · %s" % (pp.hours_text(st["hours"]), st["label"])
        self.hours_acts.visible = m
        self.regular_button.visible = st.get("kind") == "special"
        self.close_button.visible = bool(st["hours"])
        s = D["stats"]
        self.n_bookings.text, self.n_covers.text, self.n_in.text, self.n_pending.text = str(s["bookings"]), str(s["covers"]), str(s["in_now"]), str(s["pending"])
        self.stat_pending.classes["warn"] = bool(s["pending"])
        for link in (self.stat_bookings, self.stat_covers, self.stat_pending, self.all_link):
            state.set_attr(link, "href", router.href("reservations", rid))
        self.arrivals_panel.items = D["arrivals"]
        self.no_arrivals.visible = not D["arrivals"]
        self.more_arrivals.visible = bool(D.get("more_arrivals"))
        self.more_arrivals.text = "and %d more" % (D.get("more_arrivals") or 0)
        top = max([w["covers"] for w in D["week"]] + [1])
        self.week_panel.items = [dict(w, _today=i == 0, _max=top) for i, w in enumerate(D["week"])]
        # photo of the day
        p = D["posts"][0] if D["posts"] else None
        fresh = bool(p and p["date"] == D["today"])
        self.pod_box.visible = fresh
        self.pod_hint.visible = not fresh
        if fresh and p:
            self.pod_img.visible = bool(pp.thumb(p.get("photo")))
            state.set_attr(self.pod_img, "src", pp.thumb(p.get("photo")))
            self.pod_meta.text = "Posted today" + (" by " + p["by"] if p.get("by") else "")
            self.pod_text.text = p.get("text") or ""
        # specials, events, website, checklist
        self.new_special_button.visible = m
        self.specials_panel.items = [dict(x, _today=D["today"], _manage=m) for x in D["specials"]]
        self.no_specials.visible = not D["specials"]
        self.events_panel.items = D["events"]
        self.no_events.visible = not D["events"]
        self.events_link.visible = m
        state.set_attr(self.events_link, "href", router.href("events", rid))
        site = D["site"]
        self.site_box.visible = m
        self.site_badge.text = "Live" if site["published"] else "Not published"
        self.site_badge.role = ["badge", "badge-good"] if site["published"] else ["badge"]
        self.site_text.text = ("%s in the last 7 days · %s" % (state.plural(site["visits_week"], "visit"), site["url"]) if site["published"]
                               else "Build a website from your PlanPlate details: photos, menu, hours, specials and events, all kept up to date for you.")
        self.site_open.visible = bool(site["published"])
        state.set_attr(self.site_open, "href", site.get("url") or "#")
        state.set_attr(self.site_edit, "href", router.href("website", rid))
        left = [c for c in D["checklist"] if not c["done"]]
        self.check_box.visible = m and bool(left)
        self.check_count.text = "%d of %d" % (len(D["checklist"]) - len(left), len(D["checklist"]))
        self.check_panel.items = [dict(c, _rid=rid) for c in D["checklist"]]

    def _apply(self, res, msg=None):
        if res:
            self.D = res
            self._draw()
            if msg:
                state.toast(msg, "ok")

    # ---------------------------------------------------------------- today's hours
    @handle("hours_button", "click")
    def hours_button_click(self, **event_args):
        from ...Dialogs.QuickHours import QuickHours
        self._apply(alert(QuickHours(self.rid, self.D), buttons=[], role="app-dialog", dismissible=True), "Today's hours changed")

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        if confirm("Online booking stops for today and your website says “Closed today”. Bookings already made stay; you may want to call those guests.",
                   title="Close for the rest of today?", buttons=[("Stay open", False), ("Close today", True)]):
            self._apply(state.call("quick_hours", self.rid, "close"), "Closed for today")

    @handle("regular_button", "click")
    def regular_button_click(self, **event_args):
        self._apply(state.call("quick_hours", self.rid, "regular"), "Back to regular hours")

    # ---------------------------------------------------------------- specials
    def _special(self, special=None):
        from ...Dialogs.SpecialDish import SpecialDish
        self._apply(alert(SpecialDish(self.rid, self.D, special), buttons=[], role="app-dialog", dismissible=True), "Special saved")

    @handle("new_special_button", "click")
    def new_special_button_click(self, **event_args):
        self._special()

    def _edit_special(self, special, **event_args):
        self._special(special)

    def _toggle_special(self, special, active, **event_args):
        self._apply(state.call("toggle_dish_special", self.rid, special["id"], active),
                    "Showing on your website" if active else "Hidden from your website")

    # ---------------------------------------------------------------- photo of the day
    @handle("post_button", "click")
    def post_button_click(self, **event_args):
        from ...Dialogs.PostPhoto import PostPhoto
        self._apply(alert(PostPhoto(self.rid), buttons=[], role="app-dialog", dismissible=True), "Posted. It's on your website now.")

    @handle("pod_delete", "click")
    def pod_delete_click(self, **event_args):
        if confirm("It comes off your website.", title="Remove today's photo?", buttons=[("Keep it", False), ("Remove", True)]):
            self._apply(state.call("delete_post", self.rid, self.D["posts"][0]["id"]))
