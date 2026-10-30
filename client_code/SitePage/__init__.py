# SitePage — Custom HTML form. HTML: forms/SitePage.html
# The website builder (Site.get_site / save_site / preview_site / load_site_example / download_site).
from ._anvil_designer import SitePageTemplate
from anvil import *
import anvil.server

from .. import pp_ui


class SitePage(SitePageTemplate):
    def __init__(self, restaurant_id=None, **properties):
        super().__init__(**properties)
        self.rid = restaurant_id
        self.data = anvil.server.call("get_site", restaurant_id)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        pp_ui.mount(self, "website", self.data, self._on_event, rid=self.rid)

    def _on_event(self, event, p):
        if event == "save":
            return pp_ui.call("save_site", self.rid, p)
        if event == "preview":
            try:
                return anvil.server.call_s("preview_site", self.rid, p)  # no spinner: it runs as the owner types
            except Exception as e:
                return {"ok": False, "error": str(e)}
        if event == "example":
            return pp_ui.call("load_site_example", self.rid)
        if event == "download":
            pp_ui.download(anvil.server.call("download_site", self.rid))
            return {"ok": True}
