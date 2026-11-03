import datetime

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ShellTemplate
from ... import auth, router, state

THEMES = ["auto", "light", "dark"]


class Shell(ShellTemplate):
    """The frame around every page: header (Restaurants, the approvals bell and the account menu for members; Sign in /
    Get started for visitors), the footer, and the phone tab bar. Guest pages (#book, #r, #menu) hide all of it
    (class no-chrome) and show one quiet footer line instead: they are embedded in restaurants' websites.

    Anvil keeps ONE Shell while pages come and go (open_form only swaps the "content" slot when the layout matches),
    so everything that depends on who is signed in or which page is open is drawn in refresh(), which router.show()
    calls after every page change. Never only in __init__."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.copyright_label.text = "© %d PlanPlate · Arkvital" % datetime.date.today().year
        self._outside = anvil.js.report_exceptions(self._close_menu_outside)
        self._keys = anvil.js.report_exceptions(self._key)
        self.alerts_panel.add_event_handler("x-open-alert", self._open_alert)
        self.refresh("")

    def refresh(self, page):
        me = state.me()
        public = page in router.PUBLIC
        self.classes.update({"signed-in": bool(me) and not public, "signed-out": not me, "no-chrome": public,
                             "page-landing": page == "landing"})
        self.member_actions.visible = bool(me)
        self.guest_actions.visible = not me and page not in ("auth", "landing")
        self.tabbar.visible = bool(me) and not public
        self.menu.visible = False
        self.alerts_menu.visible = False
        state.set_attr(self.brand, "href", "#dashboard" if me else "#landing")
        active = "dashboard" if page in router.RESTAURANT else page
        links = [{"page": p, "label": label, "icon": icon, "on": p == active} for p, label, icon in router.NAV] if me else []
        self.nav_panel.items = links
        self.tab_panel.items = links
        self.tab_profile.classes["on"] = page == "profile"
        if me:
            self.avatar_button.text = state.initials(me.get("name"))
            self.menu_name.text = me.get("name") or ""
            self.menu_email.text = me.get("email") or ""
            self.admin_link.visible = bool(me.get("is_admin"))
            self.show_alerts(me.get("alerts"))
        self._show_theme()

    # ---- the approvals bell (polled every minute; pages call refresh_alerts after approving)
    def show_alerts(self, alerts):
        alerts = dict(alerts or {})
        items: list = list(alerts.get("items") or [])
        n = int(str(alerts.get("pending") or 0))
        self.bell_count.visible = n > 0
        self.bell_count.text = str(n)
        self.bell_button.text = "Approvals (%d)" % n
        self.alerts_panel.items = items
        self.alerts_none.visible = not items
        more = n - len(items)
        self.alerts_more.visible = more > 0
        self.alerts_more.text = "and %d more" % more
        window.document.title = ("(%d) " % n if n else "") + window.document.title.lstrip("(0123456789) ")

    def refresh_alerts(self):
        a = state.call_quiet("get_alerts")
        if a is not None:
            me = state.me()
            if me:
                me["alerts"] = a
            self.show_alerts(a)

    @handle("poll_timer", "tick")
    def poll_timer_tick(self, **event_args):
        if state.me() and not window.document.hidden and router.current() not in router.PUBLIC:
            self.refresh_alerts()

    @handle("bell_button", "click")
    def bell_button_click(self, **event_args):
        self.menu.visible = False
        self.alerts_menu.visible = not self.alerts_menu.visible

    def _open_alert(self, item, **event_args):
        self.alerts_menu.visible = False
        router.go("reservations", item["restaurant_id"], item["date"])

    # ---- account menu
    @handle("avatar_button", "click")
    def avatar_button_click(self, **event_args):
        self.alerts_menu.visible = False
        self.menu.visible = not self.menu.visible

    def _close_menu_outside(self, event):
        if not event.target.closest(".anvil-role-avatar, .ui-menu .ui-seg, .pp-bell-wrap, .pp-alerts"):
            self.menu.visible = False
            self.alerts_menu.visible = False

    def _key(self, event):
        if event.key == "Escape":
            self.menu.visible = False
            self.alerts_menu.visible = False

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("click", self._outside, True)
        window.document.addEventListener("keydown", self._keys)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("click", self._outside, True)
        window.document.removeEventListener("keydown", self._keys)

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-set"))
        self._show_theme()

    def _show_theme(self):
        t = state.theme()
        for name, el in zip(THEMES, [self.theme_auto, self.theme_light, self.theme_dark]):
            el.classes["on"] = name == t

    def feedback_click(self, event):
        self.menu.visible = False
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        state.toast("Signed out. See you soon!")
        router.go("landing")
