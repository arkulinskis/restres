from anvil import *

from ._anvil_designer import RestaurantNavTemplate
from ... import pp, router, state


class RestaurantNav(RestaurantNavTemplate):
    """The restaurant sub-menu (see the help text in form_template.html)."""

    def __init__(self, **properties):
        self._nav = None
        self.init_components(**properties)

    def show(self, nav):
        """nav = {restaurant: {id, name, slug, role, pending}, restaurants: [{id, name}]} from the server."""
        self._nav = nav
        r = nav["restaurant"]
        role = r.get("role") or "owner"
        self.name_label.text = r["name"]
        self.role_badge.visible = role != "owner"
        self.role_badge.text = pp.ROLE.get(role, role)
        others = nav.get("restaurants") or []
        self.switcher.visible = len(others) > 1
        self.switcher.items = [(x["name"], x["id"]) for x in others]
        if len(others) > 1:
            self.switcher.selected_value = r["id"]
        state.set_attr(self.book_link, "href", pp.book_url(r["slug"]))
        self.tabs_panel.items = [{"href": router.href(page, r["id"]), "label": label, "icon": icon, "on": page == self.tab,
                                  "count": r.get("pending") if page == "reservations" else 0}
                                 for page, label, icon, need in pp.TABS if pp.can(role, need)]
        window_title = dict((p, label) for p, label, icon, need in pp.TABS).get(self.tab, "")
        from anvil.js import window
        window.document.title = "%s · %s · PlanPlate" % (window_title, r["name"])

    @handle("switcher", "change")
    def switcher_change(self, **event_args):
        router.go(self.tab, self.switcher.selected_value)
