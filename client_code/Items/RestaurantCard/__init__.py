from anvil import *

from ._anvil_designer import RestaurantCardTemplate
from ... import pp, router, state


class RestaurantCard(RestaurantCardTemplate):
    """A restaurant on the dashboard. item = a get_dashboard() restaurant."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.addr_label.text = r.get("address") or "/" + r["slug"]
        if r["pending"]:
            self.state_badge.visible, self.state_badge.text, self.state_badge.role = True, "%d to approve" % r["pending"], ["badge", "badge-warn"]
        elif not r["accepting"]:
            self.state_badge.visible, self.state_badge.text = True, "Online booking off"
        staff = r.get("role") == "staff"
        self.role_badge.visible = r.get("role") not in (None, "owner")
        self.role_badge.text = pp.ROLE.get(r.get("role"), "")
        self.bookings_label.text, self.covers_label.text, self.seats_label.text = str(r["bookings"]), str(r["covers"]), str(r["seats"])
        state.set_attr(self.open_link, "href", router.href("today", r["id"]))
        state.set_attr(self.bookings_link, "href", router.href("reservations", r["id"]))
        state.set_attr(self.site_link, "href", router.href("website", r["id"]))
        self.site_link.visible = not staff
        self.dup_button.visible = not staff

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        pp.copy(pp.book_url(self.item["slug"]), "Booking link")

    @handle("dup_button", "click")
    def dup_button_click(self, **event_args):
        self.parent.raise_event("x-duplicate", restaurant=self.item)
