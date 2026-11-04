import re

from anvil import *

from ._anvil_designer import AuthBoxTemplate
from ... import auth, legal, router, state

HEADINGS = {"login": ("Welcome back", "Sign in to manage your restaurants and reservations.", "Sign in"),
            "signup": ("Open your account", "Set up your restaurants, hours and tables in about 30 minutes.", "Create account"),
            "reset": ("Reset your password", "We'll email you a link to choose a new one.", "Send reset link")}
EMAIL = re.compile(r"^\S+@\S+\.\S+$")


class AuthBox(AuthBoxTemplate):
    """Sign in / create an account / reset the password (see the help text in form_template.html)."""

    def __init__(self, **properties):
        self.mode = "login"
        self.init_components(**properties)
        self.dom_nodes["consent"].innerHTML = legal.consent_field()
        self._draw()

    def set_mode(self, mode, focus=False):
        self.mode = mode if mode in HEADINGS else "login"
        self._draw()
        if focus:
            (self.name_box if self.mode == "signup" else self.email_box).focus()

    def _draw(self, message=None, is_error=False):
        mode = self.mode if self.mode in HEADINGS else "login"
        heading, sub, action = HEADINGS[mode]
        self.heading.text, self.sub.text, self.submit_button.text = heading, sub, action
        self.mode_tabs.visible = mode != "reset"
        self.tab_login.classes["on"] = mode == "login"
        self.tab_signup.classes["on"] = mode == "signup"
        self.name_field.visible = mode == "signup"
        self.password_field.visible = mode != "reset"
        self.consent_box.visible = mode == "signup"
        self.google_part.visible = mode != "reset"
        self.forgot_row.visible = mode == "login"
        self.back_row.visible = mode == "reset"
        self.password_box.placeholder = "At least 8 characters" if mode == "signup" else ""
        self._say(message, is_error)

    def _say(self, message, is_error=True):
        self.message.visible = bool(message)
        self.message.text = message or ""
        self.message.role = "msg-error" if is_error else "msg-note"

    def mode_click(self, event):
        event.preventDefault()
        self.mode = event.currentTarget.getAttribute("data-mode")
        if router.current() == "auth":
            router.replace("auth", "" if self.mode == "login" else self.mode)
        self._draw()

    @handle("show_button", "click")
    def show_button_click(self, **event_args):
        self.password_box.hide_text = not self.password_box.hide_text
        self.show_button.text = "Show" if self.password_box.hide_text else "Hide"

    @handle("name_box", "pressed_enter")
    def name_box_pressed_enter(self, **event_args):
        self.submit_button_click()

    @handle("email_box", "pressed_enter")
    def email_box_pressed_enter(self, **event_args):
        self.submit_button_click()

    @handle("password_box", "pressed_enter")
    def password_box_pressed_enter(self, **event_args):
        self.submit_button_click()

    @handle("submit_button", "click")
    def submit_button_click(self, **event_args):
        mode = self.mode
        name, email, password = (self.name_box.text or "").strip(), (self.email_box.text or "").strip(), self.password_box.text or ""
        problem = None
        if not EMAIL.match(email):
            problem = "Please enter a valid email address."
        elif mode == "signup" and len(password) < 8:
            problem = "Please choose a password of at least 8 characters."
        elif mode == "login" and not password:
            problem = "Please enter your password."
        elif mode == "signup" and len(name) < 2:
            problem = "Please tell us your name."
        if problem:
            self._say(problem)
            return
        if mode == "signup" and not legal.consent_ok(self.dom_nodes["consent"]):
            return  # the kit shows its own message next to the tick box
        self.submit_button.enabled = False
        try:
            if mode == "login":
                r = auth.sign_in(email, password)
            elif mode == "signup":
                r = auth.sign_up(name, email, password)
            else:
                r = auth.reset(email)
        finally:
            self.submit_button.enabled = True
        if not r["ok"]:
            self._say(r["error"])
        elif mode == "reset" or r.get("confirm"):
            self.mode = "login"
            self._draw(r["message"], False)
        else:
            state.toast("Welcome to PlanPlate!" if mode == "signup" else "Welcome back!", "ok")
            router.after_sign_in()

    @handle("google_button", "click")
    def google_button_click(self, **event_args):
        if self.mode == "signup" and not legal.consent_ok(self.dom_nodes["consent"]):
            return
        r = auth.google((self.name_box.text or "") if self.mode == "signup" else "")
        if not r["ok"]:
            self._say(r["error"])
            return
        state.toast("Welcome to PlanPlate!" if self.mode == "signup" else "Welcome back!", "ok")
        router.after_sign_in()
