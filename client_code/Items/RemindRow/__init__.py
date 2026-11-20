from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import RemindRowTemplate
from ... import pp, state

CHANNEL = {"whatsapp": "WhatsApp", "sms": "SMS", "email": "Email", "copy": "copied"}


def reminded_text(rem):
    """ "Reminded 18:02 · WhatsApp" (the time in this device's clock)."""
    if not rem:
        return ""
    at = anvil.js.new(window.Date, rem.get("at") or "")
    hhmm = "%02d:%02d" % (at.getHours(), at.getMinutes()) if rem.get("at") else ""
    return ("Reminded %s · %s" % (hhmm, CHANNEL.get(rem.get("channel"), rem.get("channel") or ""))).replace("  ", " ")


class RemindRow(RemindRowTemplate):
    """One booking in the reminder list (Dialogs/Reminders). item = Remind.item() + _rid.
    WhatsApp / SMS / Email open the restaurant's own app with the message written (wa.me, sms:, mailto: links from the
    server); Copy puts the message on the clipboard. Any of them marks the booking reminded (mark_reminded, quietly in
    the background) and raises x-sent(item=, reminded=) on the RepeatingPanel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        i = self.item
        self.time_label.text = i["time"]
        self.name_label.text = "%s · %s" % (i["name"], state.plural(i["party"], "guest"))
        self.msg_label.text = i["message"]
        self.msg_label.tooltip = i["message"]
        for link, key in ((self.wa_link, "wa"), (self.sms_link, "sms"), (self.mail_link, "mail")):
            link.visible = bool(i.get(key))
            state.set_attr(link, "href", i.get(key) or "#")
        state.set_attr(self.wa_link, "aria-label", "WhatsApp %s" % i["name"])
        state.set_attr(self.sms_link, "aria-label", "SMS %s" % i["name"])
        state.set_attr(self.mail_link, "aria-label", "Email %s" % i["name"])
        state.set_control_attr(self.copy_button, "aria-label", "Copy the message for %s" % i["name"])
        self._draw()

    def _draw(self):
        i = self.item
        if i.get("coming"):
            self.state_badge.visible, self.state_badge.text, self.state_badge.role = True, "✓ Coming", ["badge", "badge-good"]
        elif i.get("reminded"):
            self.state_badge.visible, self.state_badge.text, self.state_badge.role = True, reminded_text(i["reminded"]), ["badge"]
        else:
            self.state_badge.visible = False
        self.classes["done"] = bool(i.get("reminded") or i.get("coming"))

    def _mark(self, channel):
        """Shown at once on this row; the server notes it in the booking's history (no spinner: the link is opening)."""
        i = self.item
        i["reminded"] = {"at": anvil.js.new(window.Date).toISOString(), "channel": channel}
        self._draw()
        try:
            r = state.call_quiet("mark_reminded", i["_rid"], i["id"], channel)
        except Exception:
            r = None
        if r and r.get("ok"):
            i["reminded"] = r["reminded"]
            self._draw()
        if self.parent is not None:
            self.parent.raise_event("x-sent", item=i, reminded=i["reminded"])

    def wa_click(self, event):
        self._mark("whatsapp")

    def sms_click(self, event):
        self._mark("sms")

    def mail_click(self, event):
        self._mark("email")

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        pp.copy(self.item["message"], "Message copied")
        self._mark("copy")
