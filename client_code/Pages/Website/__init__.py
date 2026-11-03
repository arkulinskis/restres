from anvil import *
import anvil.js
import anvil.media
import anvil.server
from anvil.js import window

from ._anvil_designer import WebsiteTemplate
from ... import pp, site_model, state


class Website(WebsiteTemplate):
    """#website/<rid>: the website builder. One form (sections in site_model.sections) generates the restaurant's site
    on the PlanPlate template (server_code/Site.py), hosted at /_/api/site/<path> or downloaded as a .zip, with a live
    computer/phone preview. Hours, menu, specials, events, photo of the day and gallery stay live."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.m = site_model.Model(anvil.server.call("get_site", self.rid))
        self.m.on_change = self._changed
        self.began, self.device, self.open = False, "desktop", {"look": True}
        self.sections_panel.add_event_handler("x-redraw", self._redraw_event)
        self.sections_panel.add_event_handler("x-toggle-open", self._open_event)
        self._resize = anvil.js.report_exceptions(lambda e: self._fit())
        self._draw()

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        D, s = self.m.D, self.m.D["site"]
        self.rnav.show(D["nav"])
        self.url_label.text = D["origin"].split("//")[-1] + "/_/api/site/" + s["path"]
        self.visits_label.visible = s["published"]
        self.visits_label.text = "%s this week · %d in all" % (state.plural(s["visits_week"], "visit"), s["views"])
        self.live_badge.text = "Live" if s["published"] else "Not published"
        self.live_badge.role = ["badge", "badge-good"] if s["published"] else ["badge"]
        self.open_link.visible = s["published"]
        state.set_attr(self.open_link, "href", s.get("url") or "#")
        self.publish_button.text = "Unpublish" if s["published"] else "Publish"
        self.publish_button.role = ["btn", "btn-sm", "btn-ghost"] if s["published"] else ["btn", "btn-sm", "btn-primary"]
        started = s["started"] or self.began
        self.welcome.visible = not started
        self.builder.visible = started
        self._dirty_ui()
        if started:
            self._sections()
            self.dev_desktop.classes["on"] = self.device == "desktop"
            self.dev_phone.classes["on"] = self.device == "phone"
            self._preview()

    def _sections(self):
        self.sections_panel.items = [dict(sec, model=self.m, rid=self.rid, open=bool(self.open.get(sec["id"]))) for sec in site_model.sections(self.m)]

    def _dirty_ui(self):
        self.save_button.enabled = self.m.dirty
        self.save_button.role = ["btn", "btn-sm", "btn-primary"] if self.m.dirty else ["btn", "btn-sm"]

    def _changed(self, path):
        self._dirty_ui()
        self.pv_status.text = "Preview (not saved)"
        self.preview_timer.interval = 0.9

    def _redraw_event(self, **event_args):
        self._sections()
        self._changed("")

    def _open_event(self, sid, is_open, **event_args):
        self.open[sid] = is_open

    # ---------------------------------------------------------------- preview
    @handle("preview_timer", "tick")
    def preview_timer_tick(self, **event_args):
        self.preview_timer.interval = 0
        self._preview()

    def _preview(self):
        self.pv_status.text = "Updating…"
        try:
            r = anvil.server.call_s("preview_site", self.rid, self.m.F)
        except Exception:
            self.pv_status.text = "Preview failed"
            return
        if r and r.get("html"):
            self.dom_nodes["frame"].srcdoc = r["html"]
        self.pv_status.text = "Preview (not saved)" if self.m.dirty else "Preview"
        self._fit()

    def _fit(self):
        box, fr = self.dom_nodes["pvbox"], self.dom_nodes["frame"]
        if not box.clientWidth:
            return
        phone = self.device == "phone"
        w = 390 if phone else 1280
        k = min(1, (box.clientHeight - 32) / 844.0, box.clientWidth / 420.0) if phone else box.clientWidth / float(w)
        fr.style.width = "%dpx" % w
        fr.style.height = "%dpx" % (844 if phone else box.clientHeight / k)
        fr.style.transform = ("translateX(-50%%) scale(%f)" % k) if phone else ("scale(%f)" % k)
        fr.style.transformOrigin = "50% 0" if phone else "0 0"
        box.classList.toggle("phone", phone)

    def device_click(self, event):
        self.device = event.currentTarget.getAttribute("data-dev")
        self.dev_desktop.classes["on"] = self.device == "desktop"
        self.dev_phone.classes["on"] = self.device == "phone"
        self._fit()

    @handle("", "show")
    def form_show(self, **event_args):
        window.addEventListener("resize", self._resize)
        self._fit()

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.removeEventListener("resize", self._resize)

    # ---------------------------------------------------------------- start, save, publish, download
    def begin_click(self, event):
        self.began = True
        self._draw()

    def example_click(self, event):
        if self.m.D["site"]["started"] and not confirm("Your own texts on the website form are replaced by the example. Your restaurant's details stay.",
                                                       title="Load the Dilettante example?", buttons=[("Keep mine", False), ("Load it", True)]):
            return
        r = state.call("load_site_example", self.rid)
        if r:
            self.m.load(r)
            self.began = True
            self._draw()
            state.toast("Example loaded. Change anything, then save.", "ok")

    def _save(self, extra=None):
        data = dict(self.m.F, **(extra or {}))
        r = state.call("save_site", self.rid, data)
        if not r:
            return False
        self.m.load(r)
        self.began = True
        self._draw()
        if extra and "published" in extra:
            state.toast("Your website is live" if extra["published"] else "Your website is offline", "ok")
        else:
            state.toast("Saved. Your website is updated." if self.m.D["site"]["published"] else "Saved", "ok")
        return True

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        self._save()

    @handle("publish_button", "click")
    def publish_button_click(self, **event_args):
        self._save({"published": not self.m.D["site"]["published"]})

    @handle("download_button", "click")
    def download_button_click(self, **event_args):
        media = anvil.server.call("download_site", self.rid)
        if media:
            anvil.media.download(media)
