# AuthPage — Custom HTML form. HTML: forms/AuthPage.html
from ._anvil_designer import AuthPageTemplate
from anvil import *
import anvil.server
import anvil.users

from .. import pp_ui


def _google_step_done():
    """After login_with_google() gave None: did the person finish the Google window (they just have no account yet)?"""
    try:
        import anvil.google.auth
        return bool(anvil.google.auth.get_user_email())
    except Exception:
        return True  # can't tell: go on to sign-up, which asks Google again if needed


class AuthPage(AuthPageTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "auth", {}, self._on_event)

    def _on_event(self, event, p):
        name = None
        try:
            if event == "login":
                anvil.users.login_with_email(p["email"].strip(), p["password"], remember=True)
            elif event == "signup":
                name = p.get("name", "").strip()
                anvil.users.signup_with_email(p["email"].strip(), p["password"], remember=True)
                if anvil.users.get_user() is None:
                    return {"ok": True, "mode": "login",
                            "message": "Account created. Check your email for a confirmation link, then sign in."}
            elif event == "google":
                # Continue with Google: sign in, or create the account on the first visit.
                if anvil.users.login_with_google(remember=True) is None:
                    if not _google_step_done() or anvil.users.signup_with_google(remember=True) is None:
                        return {"ok": False, "error": "Google sign-in was cancelled."}
                    name = (p.get("name") or "").strip()
            elif event == "reset":
                try:
                    anvil.users.send_password_reset_email(p["email"].strip())
                except anvil.users.AuthenticationFailed:
                    pass  # same reply either way, so nobody can probe which emails have accounts
                return {"ok": True, "message": "If that email has an account, a reset link is on its way."}
            else:
                return None
        except anvil.users.UserExists:
            return {"ok": False, "error": "An account with that email already exists. Try signing in."}
        except anvil.users.EmailNotConfirmed:
            return {"ok": False, "error": "Please confirm your email first. Check your inbox for the link."}
        except anvil.users.AccountIsNotEnabled:
            return {"ok": False, "error": "This account is disabled."}
        except anvil.users.TooManyPasswordFailures:
            return {"ok": False, "error": "Too many wrong attempts. Wait a while, or reset your password."}
        except anvil.users.PasswordNotAcceptable as e:
            return {"ok": False, "error": str(e) or "Please choose a stronger password."}
        except anvil.users.AuthenticationFailed:
            return {"ok": False, "error": "That email and password don't match."}
        if name:
            anvil.server.call("update_me", name)
        get_open_form().signed_in()
        return {"ok": True}
