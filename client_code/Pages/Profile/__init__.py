from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import ProfileTemplate
from ... import auth, router, state


class Profile(ProfileTemplate):
    """#profile: your name, light/dark, a password reset link, your plan (when billing is on), Privacy & Terms, feedback, sign out."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self._show_me()
        self._show_theme()
        self._show_plan()

    def _show_plan(self):
        p = anvil.server.call("get_plan")
        self.plan_card.visible = bool(p.get("on"))
        why = p.get("why")
        self.plan_line.text = {
            "included": "Everything is included with your account.",
            "free": "You're on a free plan: everything is included.",
            "subscription": "PlanPlate, %s. Everything included." % (p.get("price") or "monthly") +
                            (" Stripe couldn't take the last payment: check your card." if p.get("status") == "past_due" else ""),
            "error": "Your plan can't be checked right now. Everything keeps working.",
        }.get(why, "No subscription yet. PlanPlate is %s, everything included." % (p.get("price") or "a flat monthly price"))
        self.plan_subscribe.visible = not p.get("active")
        self.plan_manage.visible = why == "subscription"

    @handle("plan_subscribe", "click")
    def plan_subscribe_click(self, **event_args):
        r = state.call("start_checkout")
        if r and r.get("url"):
            window.location.href = r["url"]

    @handle("plan_manage", "click")
    def plan_manage_click(self, **event_args):
        r = state.call("billing_portal")
        if r and r.get("url"):
            window.location.href = r["url"]

    def _show_me(self):
        me = state.me()
        self.initials.text = state.initials(me.get("name"))
        self.name_title.text = me.get("name") or ""
        joined = state.month_year(me.get("joined"))
        self.email_line.text = (me.get("email") or "") + (" · member since " + joined if joined else "")
        self.name_box.text = me.get("name") or ""
        self.admin_link.visible = bool(me.get("is_admin"))

    def _show_theme(self):
        t = state.theme()
        for name, el in (("auto", self.theme_auto), ("light", self.theme_light), ("dark", self.theme_dark)):
            el.classes["on"] = name == t

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-pick"))
        self._show_theme()

    @handle("name_box", "pressed_enter")
    def name_box_pressed_enter(self, **event_args):
        self.save_button_click()

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        name = (self.name_box.text or "").strip()
        if len(name) < 2:
            state.toast("Please tell us your name.", "error")
            return
        r = state.call("update_profile", name)
        if r:
            state.set_me(r["me"])
            self._show_me()
            state.toast("Saved", "ok")

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        r = auth.reset(state.me()["email"])
        state.toast(r["message"], "ok")

    def feedback_click(self, event):
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        state.toast("Signed out. See you soon!")
        router.go("landing")
