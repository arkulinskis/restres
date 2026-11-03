from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import GalleryTemplate
from ... import pp, state

CHOICES = {
    "theme": [("bento", "Bento (one big photo)"), ("classic", "Classic grid"), ("tilt", "Polaroids"), ("cinematic", "Cinematic (dark)"),
              ("editorial", "Editorial (black & white)")],
    "bg_style": [("solid", "Plain"), ("gradient", "Gradient"), ("spotlight", "Spotlight"), ("aurora", "Aurora"), ("grain", "Grain"),
                 ("paper", "Paper"), ("dotted", "Dots"), ("stripes", "Stripes"), ("vignette", "Vignette"), ("mesh", "Mesh")],
    "picture_style": [("none", "None"), ("frame", "Frame"), ("duotone", "Duotone"), ("glow", "Glow"), ("blob", "Soft shapes")],
    "size": [("xs", "Extra small"), ("sm", "Small"), ("md", "Medium"), ("lg", "Large"), ("xl", "Extra large")],
    "motion": [("none", "None"), ("fade", "Fade in"), ("rise", "Rise"), ("slide", "Slide"), ("zoom", "Zoom"), ("stagger", "One by one")],
    "mobile_layout": [("bleed", "Edge to edge"), ("inset", "With margins"), ("carousel", "Swipe"), ("stack", "One per row")],
}
LABELS = {"theme": "Look", "bg_style": "Background", "picture_style": "Photo effect", "size": "Photo size", "motion": "Animation",
          "mobile_layout": "On phones"}
ATTR = {"bg_style": "bg-style", "picture_style": "picture-style", "mobile_layout": "mobile-layout", "accent": "accent-color",
        "background": "background-color"}


class Gallery(GalleryTemplate):
    """#gallery/<rid>: the restaurant's photos (upload many at once, order, caption, in or out of the gallery) and the
    gallery's look (the <planplate-gallery> component, theme/assets/planplate-gallery.js), with the code for any website."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_gallery", self.rid)
        for p in (self.gallery_panel, self.others_panel):
            p.add_event_handler("x-move", self._move)
            p.add_event_handler("x-show", self._show)
            p.add_event_handler("x-delete", self._delete)
            p.add_event_handler("x-caption", self._caption)
        self.style_panel.add_event_handler("x-style", self._style_event)
        self._draw()

    def _in(self):
        return [p for p in self.D["photos"] if p.get("in_gallery") and p.get("kind") == "image"]

    def _draw(self):
        D = self.D
        self.rnav.show(D["nav"])
        self.storage_badge.text = "Stored on Cloudinary" if D["storage"] == "cloudinary" else "Stored by PlanPlate"
        g = self._in()
        o = [p for p in D["photos"] if p not in g]
        self.count_label.text = state.plural(len(g), "photo") + " · in this order"
        self.gallery_panel.items = [dict(p, _gallery=True, _first=i == 0, _last=i == len(g) - 1, _n=i + 1) for i, p in enumerate(g)]
        self.gallery_empty.visible = not g
        self.others_part.visible = bool(o)
        self.others_panel.items = [dict(p, _gallery=False) for p in o]
        s = D["style"]
        self.style_panel.items = [{"key": k, "label": LABELS[k], "choices": CHOICES[k], "value": s.get(k)} for k in CHOICES]
        setattr(anvil.js.get_dom_node(self.accent_in), "value", s.get("accent") or "#9c7a43")
        setattr(anvil.js.get_dom_node(self.background_in), "value", s.get("background") or "#f6f3ee")
        self.heading_box.text = s.get("heading") or ""
        self.code_label.text = self._code()
        self._preview()

    def _code(self):
        s, D = self.D["style"], self.D
        return ('<script src="%s"></' % D["script_url"] + 'script>\n<planplate-gallery\n  feed-url="%s"\n  theme="%s" bg-style="%s" picture-style="%s"\n'
                '  size="%s" motion="%s" mobile-layout="%s"\n  accent-color="%s" background-color="%s">\n</planplate-gallery>') % (
            D["feed_url"], s["theme"], s["bg_style"], s["picture_style"], s["size"], s["motion"], s["mobile_layout"], s["accent"], s["background"])

    def _preview(self):
        box = self.dom_nodes["preview"]
        if not self._in():
            box.innerHTML = '<div class="ui-empty">The preview appears when the gallery has photos.</div>'
            return
        s, esc = self.D["style"], window.PP.esc
        feed = window.location.origin + "/_/api/gallery/" + self.D["slug"]
        box.innerHTML = ('<planplate-gallery cache-ttl="0" eager feed-url="%s" theme="%s" bg-style="%s" picture-style="%s" size="%s" motion="%s" '
                         'mobile-layout="%s" accent-color="%s" background-color="%s" hide-branding></planplate-gallery>') % (
            esc(feed), s["theme"], s["bg_style"], s["picture_style"], s["size"], s["motion"], s["mobile_layout"], esc(s["accent"]), esc(s["background"]))
        window.PP.loadScript("_/theme/planplate-gallery.js")

    # ---------------------------------------------------------------- uploads
    def _upload(self, accept, multiple, in_gallery):
        self.progress_label.visible = True
        self.progress_label.text = "Choose files…"

        def progress(i, n, name):
            self.progress_label.text = "Uploading %d of %d: %s" % (i, n, name)

        res = pp.upload(self.rid, accept, multiple, {"in_gallery": in_gallery}, progress)
        self.progress_label.visible = False
        ok = [r for r in res if r["ok"]]
        bad = [r for r in res if not r["ok"]]
        if res:
            self.D = anvil.server.call("get_gallery", self.rid)
            self._draw()
        if ok:
            state.toast(state.plural(len(ok), "file") + " added", "ok")
        for r in bad:
            state.toast("%s: %s" % (r["name"], r["error"]), "error")

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        self._upload("image/*", True, True)

    @handle("video_button", "click")
    def video_button_click(self, **event_args):
        self._upload("video/mp4,video/webm,video/quicktime", False, False)

    # ---------------------------------------------------------------- photo actions
    def _photos(self, r, msg=None):
        if r:
            if r.get("photos") is not None:
                self.D["photos"] = r["photos"]
            self._draw()
            if msg:
                state.toast(msg, "ok")

    def _move(self, photo, step, **event_args):
        g = self._in()
        ids = [p["id"] for p in g]
        i = ids.index(photo["id"])
        j = i + step
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            self._photos(state.call("order_photos", self.rid, ids))

    def _show(self, photo, **event_args):
        r = state.call("save_photo", self.rid, {"id": photo["id"], "in_gallery": not photo.get("in_gallery")})
        if r:
            for p in self.D["photos"]:
                if p["id"] == photo["id"]:
                    p["in_gallery"] = r["photo"]["in_gallery"]
            self._draw()
            state.toast("Added to the gallery" if r["photo"]["in_gallery"] else "Hidden from the gallery", "ok")

    def _caption(self, photo, caption, **event_args):
        if state.call("save_photo", self.rid, {"id": photo["id"], "caption": caption}):
            state.toast("Caption saved", "ok")

    def _delete(self, photo, **event_args):
        what = "video" if photo.get("kind") == "video" else "photo"
        if confirm("It disappears from the gallery, your website, and any special or event that uses it.", title="Delete this %s?" % what,
                   buttons=[("Keep it", False), ("Delete", True)]):
            self._photos(state.call("delete_photo", self.rid, photo["id"]), "Deleted")

    # ---------------------------------------------------------------- style
    def _save_style(self, key, value):
        self.D["style"][key] = value
        self.code_label.text = self._code()
        el = self.dom_nodes["preview"].querySelector("planplate-gallery")
        if el:
            el.setAttribute(ATTR.get(key, key), value)
        r = state.call("save_gallery_style", self.rid, {key: value})
        if r and r.get("style"):
            self.D["style"] = r["style"]

    def _style_event(self, key, value, **event_args):
        self._save_style(key, value)

    def color_change(self, event):
        self._save_style(event.currentTarget.getAttribute("data-k"), event.currentTarget.value)

    @handle("heading_box", "lost_focus")
    def heading_box_lost_focus(self, **event_args):
        if (self.heading_box.text or "") != (self.D["style"].get("heading") or ""):
            self._save_style("heading", self.heading_box.text or "")

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        pp.copy(self._code(), "Gallery code")
