from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import ShareTemplate
from ... import pp


class Share(ShareTemplate):
    """#share/<rid>: QR codes (booking, menu, website) with print-size PNGs and printable table cards, plus every way to
    put the booking form on a website (link, Reserve button, own button, iframe, live menu and hours widgets, JSON)."""

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
        origin = self.D.get("origin") or pp.app_url().rstrip("/")
        slug, name = s["slug"], s["name"]
        js = "</" + "script>"
        self.codes_panel.items = [
            {"title": "Booking link", "text": "Share it anywhere: social media, Google Business Profile, email signatures.", "code": self.book, "open": self.book},
            {"title": "“Reserve a table” button", "text": "Paste this where the button should appear on your website. It opens the booking form in a window over your page.",
             "code": '<script src="%s/_/api/embed.js?r=%s">%s' % (origin, slug, js)},
            {"title": "Use your own button or link", "text": "Give any element the attribute data-planplate-open and include the script once.",
             "code": '<a href="#" data-planplate-open>Book a table</a>\n<script src="%s/_/api/embed.js?r=%s">%s' % (origin, slug, js)},
            {"title": "Embed the form in a page", "text": "The whole booking form inside your page.",
             "code": '<iframe src="%s" title="Reserve a table at %s" style="width:100%%;max-width:560px;height:860px;border:0"></iframe>' % (self.book, name)},
            {"title": "Live menu on your website", "text": "Always shows the menu as it is in PlanPlate.",
             "code": '<div data-planplate-menu></div>\n<script src="%s/_/api/menu.js?r=%s">%s' % (origin, slug, js)},
            {"title": "Live opening hours on your website", "text": "Follows your periods and special days.",
             "code": '<div data-planplate-hours></div>\n<script src="%s/_/api/hours.js?r=%s">%s' % (origin, slug, js)},
            {"title": "For developers", "text": "The same data as JSON.",
             "code": "%s/_/api/menu?r=%s\n%s/_/api/hours?r=%s" % (origin, slug, origin, slug)},
        ]

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
