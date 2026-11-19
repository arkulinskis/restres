from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import ShareTemplate
from ... import pp, router, state


class Share(ShareTemplate):
    """#share/<rid>: QR codes (booking, menu, website) with print-size PNGs, printable table cards and the plain links.
    Everything to paste into a website moved to the Elements page (2026-11-19)."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_share", self.rid)
        s = self.D["settings"]
        self.rnav.show(self.D["nav"])
        self.book, self.menu = pp.book_url(s["slug"]), pp.menu_url(s["slug"])
        self.site = self.D.get("site_url") or ""
        self.dom_nodes["qr_book"].innerHTML = pp.qr_svg(self.book, 170)
        self.dom_nodes["qr_menu"].innerHTML = pp.qr_svg(self.menu, 170)
        self.book_url_label.text, self.menu_url_label.text = self.book, self.menu
        self.site_qr_box.visible = bool(self.site)
        if self.site:
            self.dom_nodes["qr_site"].innerHTML = pp.qr_svg(self.site, 170)
            self.site_url_label.text = self.site
        state.set_attr(self.elements_link, "href", router.href("elements", self.rid))
        self.codes_panel.items = [
            {"title": "Booking link", "text": "Opens your booking form.", "code": self.book, "open": self.book},
            {"title": "Menu link", "text": "Opens your menu (the page the menu QR code shows).", "code": self.menu, "open": self.menu},
        ] + ([{"title": "Website link", "text": "Your PlanPlate website.", "code": self.site, "open": self.site}] if self.site else [])

    @handle("book_png", "click")
    def book_png_click(self, **event_args):
        pp.qr_png(self.book, "booking-qr.png", "Reserve a table")

    @handle("menu_png", "click")
    def menu_png_click(self, **event_args):
        pp.qr_png(self.menu, "menu-qr.png", "Menu")

    @handle("site_png", "click")
    def site_png_click(self, **event_args):
        pp.qr_png(self.site, "website-qr.png", self.D["settings"]["name"])

    @handle("card_button", "click")
    def card_button_click(self, **event_args):
        """Four identical table cards on one page, then the browser's print dialog."""
        s = self.D["settings"]
        esc = window.PP.esc
        card = ('<div class="pp-tcard"><div class="pp-tcard-name">%s</div><div class="pp-tcard-qrs">'
                '<div>%s<b>Menu</b><span>Scan to see today\'s menu</span></div><div>%s<b>Book a table</b><span>Your next visit, in 30 seconds</span></div>'
                '</div><div class="pp-tcard-foot">%s</div></div>') % (esc(s["name"]), pp.qr_svg(self.menu, 130), pp.qr_svg(self.book, 130),
                                                                     esc(s.get("address") or ""))
        self.dom_nodes["cards"].innerHTML = card * 4
        pp.html_class("pp-print-cards", True)
        window.print()
        pp.html_class("pp-print-cards", False)
