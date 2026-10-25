# pp_ui — client Module. Glue between the Python forms and the HTML components in forms/*.html.
import json

import anvil.js
import anvil.server
from anvil.js import window

APP_NAME = "PlanPlate"


def mount(form, name, data, on_event=None):
    """Draw component `name` inside `form` and route its events to on_event(event, payload).

    Data goes to JS as a JSON string, so pass only JSON-friendly values (the server already turns
    dates into ISO strings). Whatever on_event returns (a dict, or None) resolves the component's
    Promise. Returns the component's JS API object.
    """
    selector = '[data-pp-root="%s"]' % name
    node = anvil.js.get_dom_node(form)
    # A form whose HTML is a single element *is* that element, so check the node itself first.
    root = node if node.matches(selector) else node.querySelector(selector)

    def emit(event, payload_json):
        payload = json.loads(payload_json) if payload_json else {}
        if event == "go":  # every portal page can navigate (sub-nav tabs, restaurant switcher)
            from anvil import get_open_form
            get_open_form().go(payload.get("page", "dashboard"), restaurant_id=payload.get("restaurant_id"))
            return None
        if on_event is None:
            return None
        return on_event(event, payload)

    return window.PP.mount(name, root, json.dumps(data), emit)


def call(name, *args, **kwargs):
    """anvil.server.call that turns errors into {"ok": False, "error": ...} for the components."""
    try:
        return anvil.server.call(name, *args, **kwargs)
    except anvil.server.PermissionDenied as e:
        return {"ok": False, "error": str(e) or "You don't have access to that."}
    except anvil.server.SessionExpiredError:
        return {"ok": False, "error": "Your session expired. Reload the page and sign in again."}


def toast(message, error=False):
    window.PP.toast(message, error)


def scroll_top():
    window.scrollTo(0, 0)


def browser_timezone():
    try:
        return window.Intl.DateTimeFormat().resolvedOptions().timeZone or "UTC"
    except Exception:
        return "UTC"


def set_title(text):
    window.document.title = text
