from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import DashboardTemplate
from ... import pp, router, state


class Dashboard(DashboardTemplate):
    """#dashboard: every restaurant the person runs (or works at), today's numbers and the approvals waiting."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.cards_panel.add_event_handler("x-duplicate", self._duplicate)
        self.paid = bool(args) and args[0] == "paid"  # back from Stripe's payment page
        self._load()
        if self.paid:
            state.toast("Thank you! Your subscription is on." if self.plan.get("active") else
                        "Thanks! Stripe is still confirming the payment: refresh in a minute.", "ok")

    def _load(self):
        data = anvil.server.call("get_dashboard")
        if getattr(self, "paid", False):
            data["plan"] = anvil.server.call("get_plan", True)
        me = data.get("me") or {}
        self.plan = data.get("plan") or {}
        self.plan_box.visible = bool(self.plan.get("on")) and not self.plan.get("active")
        self.plan_text.text = ("%s, everything included: any number of restaurants, your whole team and every feature. "
                               "Cancel any time." % (self.plan.get("price") or "One flat monthly price"))
        lst = data["restaurants"]
        self.date_label.text = pp.fmt_date(pp.today_iso())
        hour = window.Date().getHours()
        first = (me.get("display_name") or "").split(" ")[0]
        self.hello_label.text = ("Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening") + (", " + first if first else "")
        pending = sum(r["pending"] for r in lst)
        self.alert_box.visible = pending > 0
        self.alert_label.text = "%s waiting for your approval." % state.plural(pending, "booking")
        self.pending_panel.items = [r for r in lst if r["pending"]]
        self.list_part.visible = bool(lst)
        self.empty_part.visible = not lst
        self.new_button.visible = bool(lst)
        self.count_label.text = str(len(lst))
        self.cards_panel.items = lst
        if me.get("alerts") and state.me():
            state.me()["alerts"] = me["alerts"]  # the demo restaurant may have just appeared: update the header bell
            shell = getattr(self, "layout", None)
            if shell is not None and hasattr(shell, "show_alerts"):
                shell.show_alerts(me["alerts"])

    def _new(self):
        from ...Dialogs.NewRestaurant import NewRestaurant
        rid = alert(NewRestaurant(), buttons=[], role="app-dialog", dismissible=True)
        if rid:
            router.go("today", rid)

    @handle("subscribe_button", "click")
    def subscribe_button_click(self, **event_args):
        r = state.call("start_checkout")
        if r and r.get("url"):
            window.location.href = r["url"]

    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        self._new()

    @handle("first_button", "click")
    def first_button_click(self, **event_args):
        self._new()

    def new_click(self, event):
        self._new()

    def _duplicate(self, restaurant, **event_args):
        from ...Dialogs.NewRestaurant import NewRestaurant
        rid = alert(NewRestaurant(copy_of=restaurant), buttons=[], role="app-dialog", dismissible=True)
        if rid:
            state.toast("Copied. Bookings stay with the original.", "ok")
            self._load()
