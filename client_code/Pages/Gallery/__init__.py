import json

from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import GalleryTemplate
from ... import pp, router, state


def _svg(body):
    return '<svg viewBox="0 0 64 40" fill="currentColor">%s</svg>' % body


# The layouts of <planplate-showcase> (theme/assets/pp-showcase.js): key, name, one line, a small drawing.
LAYOUTS = [
    ("mosaic", "Mosaic", "Rows that fit every photo whole",
     _svg('<rect x="2" y="3" width="24" height="15" rx="2"/><rect x="28" y="3" width="13" height="15" rx="2"/><rect x="43" y="3" width="19" height="15" rx="2"/>'
          '<rect x="2" y="21" width="15" height="16" rx="2"/><rect x="19" y="21" width="27" height="16" rx="2"/><rect x="48" y="21" width="14" height="16" rx="2"/>')),
    ("masonry", "Masonry", "Columns, each photo its own height",
     _svg('<rect x="2" y="2" width="18" height="20" rx="2"/><rect x="2" y="24" width="18" height="14" rx="2"/><rect x="23" y="2" width="18" height="12" rx="2"/>'
          '<rect x="23" y="16" width="18" height="22" rx="2"/><rect x="44" y="2" width="18" height="24" rx="2"/><rect x="44" y="28" width="18" height="10" rx="2"/>')),
    ("spotlight", "Spotlight", "One big photo, the rest in a strip",
     _svg('<rect x="2" y="2" width="60" height="27" rx="2"/><rect x="2" y="31" width="10" height="7" rx="1.5"/><rect x="14" y="31" width="10" height="7" rx="1.5"/>'
          '<rect x="26" y="31" width="10" height="7" rx="1.5"/><rect x="38" y="31" width="10" height="7" rx="1.5"/><rect x="50" y="31" width="12" height="7" rx="1.5"/>')),
    ("slideshow", "Slideshow", "Cinematic, with a slow zoom",
     _svg('<rect x="2" y="5" width="60" height="30" rx="2"/><circle cx="26" cy="31" r="1.6" fill="#fff"/><rect x="29" y="29.4" width="7" height="3.2" rx="1.6" fill="#fff"/>'
          '<circle cx="39" cy="31" r="1.6" fill="#fff"/>')),
    ("carousel", "Carousel", "A row guests swipe through",
     _svg('<rect x="-6" y="5" width="14" height="30" rx="2" opacity=".45"/><rect x="11" y="5" width="20" height="30" rx="2"/><rect x="34" y="5" width="20" height="30" rx="2"/>'
          '<rect x="57" y="5" width="14" height="30" rx="2" opacity=".45"/>')),
    ("editorial", "Editorial", "A magazine spread with captions",
     _svg('<rect x="2" y="2" width="38" height="26" rx="2"/><rect x="43" y="2" width="19" height="26" rx="2"/><rect x="2" y="31" width="14" height="2" rx="1"/>'
          '<rect x="43" y="31" width="12" height="2" rx="1"/><rect x="2" y="35" width="24" height="2" rx="1" opacity=".5"/>')),
    ("grid", "Grid", "Even squares, calm and tidy",
     _svg('<rect x="2" y="2" width="18" height="17" rx="2"/><rect x="23" y="2" width="18" height="17" rx="2"/><rect x="44" y="2" width="18" height="17" rx="2"/>'
          '<rect x="2" y="21" width="18" height="17" rx="2"/><rect x="23" y="21" width="18" height="17" rx="2"/><rect x="44" y="21" width="18" height="17" rx="2"/>')),
    ("polaroid", "Polaroids", "Prints scattered on a table",
     _svg('<g transform="rotate(-6 14 20)"><rect x="4" y="7" width="20" height="24" rx="1" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="6" y="9" width="16" height="15"/></g>'
          '<g transform="rotate(4 32 20)"><rect x="22" y="6" width="20" height="24" rx="1" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="24" y="8" width="16" height="15"/></g>'
          '<g transform="rotate(-3 51 20)"><rect x="41" y="8" width="20" height="24" rx="1" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="43" y="10" width="16" height="15"/></g>')),
]
STAGE = ("spotlight", "slideshow")
LIMITED = ("mosaic", "masonry", "grid", "editorial", "polaroid")
OPTIONS = [  # key, label, choices, shown for which layouts (None = all)
    ("tone", "Background", [("page", "Same as my site"), ("light", "Light"), ("dark", "Dark"), ("custom", "My colour")], None),
    ("size", "Photo size", [("sm", "Small"), ("md", "Medium"), ("lg", "Large"), ("xl", "Extra large")],
     ("mosaic", "masonry", "grid", "polaroid", "carousel")),
    ("gap", "Space between", [("none", "None"), ("tight", "Tight"), ("airy", "Airy")], ("mosaic", "masonry", "grid", "editorial", "polaroid", "carousel")),
    ("corners", "Corners", [("square", "Square"), ("soft", "Soft"), ("round", "Round")], None),
    ("frame", "Photo frame", [("none", "None"), ("shadow", "Shadow"), ("matte", "White mat")], ("mosaic", "masonry", "grid", "editorial", "carousel")),
    ("captions", "Captions", [("off", "Off"), ("hover", "Over the photo"), ("below", "Below")], ("mosaic", "masonry", "grid", "carousel", "spotlight", "slideshow")),
    ("hover", "When the mouse is over a photo", [("zoom", "Zoom"), ("lift", "Lift"), ("none", "Still")], ("mosaic", "masonry", "grid", "editorial", "carousel")),
    ("motion", "When photos scroll into view", [("rise", "Rise"), ("fade", "Fade"), ("zoom", "Zoom"), ("none", "Still")], LIMITED),
    ("show", "How many to show", [("all", "All"), ("6", "6 + See all"), ("9", "9 + See all"), ("12", "12 + See all")], LIMITED),
    ("autoplay", "Plays by itself", [("on", "On"), ("off", "Off")], STAGE),
    ("lightbox", "Tap a photo to see it full screen", [("on", "On"), ("off", "Off")], None),
]
RECOMMENDED = {  # "Back to the recommended look" for each layout
    "mosaic": {"tone": "page", "size": "md", "gap": "tight", "corners": "soft", "frame": "none", "captions": "hover", "hover": "zoom", "motion": "rise", "show": "all"},
    "masonry": {"tone": "page", "size": "md", "gap": "tight", "corners": "soft", "frame": "none", "captions": "hover", "hover": "lift", "motion": "rise", "show": "all"},
    "spotlight": {"tone": "dark", "corners": "soft", "captions": "hover", "autoplay": "on"},
    "slideshow": {"tone": "page", "corners": "square", "captions": "hover", "autoplay": "on"},
    "carousel": {"tone": "page", "size": "md", "gap": "tight", "corners": "soft", "frame": "none", "captions": "hover", "hover": "zoom"},
    "editorial": {"tone": "light", "gap": "airy", "corners": "square", "frame": "none", "hover": "zoom", "motion": "rise", "show": "all"},
    "grid": {"tone": "page", "size": "md", "gap": "tight", "corners": "soft", "frame": "none", "captions": "hover", "hover": "zoom", "motion": "fade", "show": "all"},
    "polaroid": {"tone": "custom", "background": "#6b4f36", "size": "md", "gap": "airy", "motion": "rise", "show": "all"},
}
LOOK_KEYS = ("layout", "tone", "gap", "corners", "frame", "captions", "hover", "show", "lightbox", "autoplay", "size", "motion", "accent",
             "background", "heading")


class Gallery(GalleryTemplate):
    """#gallery/<rid>: the restaurant's photos (upload many at once, drag to order, caption, in or out of the gallery) and
    the gallery's look: a layout card + options, with a live preview (computer or phone) of the real <planplate-showcase>
    (theme/assets/pp-showcase.js). The code for other websites is on the Elements page."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.device = state.store_get("galDevice", "desktop")
        self.D = anvil.server.call("get_gallery", self.rid)
        for p in (self.gallery_panel, self.others_panel):
            p.add_event_handler("x-move", self._move)
            p.add_event_handler("x-show", self._show)
            p.add_event_handler("x-delete", self._delete)
            p.add_event_handler("x-caption", self._caption)
        self.layouts_panel.add_event_handler("x-style", self._style_event)
        self.options_panel.add_event_handler("x-style", self._style_event)
        state.set_attr(self.elements_link, "href", router.href("elements", self.rid))
        window.PP.sortable(self.dom_nodes["ggrid"], {"item": "[data-sort-id]", "handle": ".pp-drag",
                                                     "onEnd": anvil.js.report_exceptions(self._sorted)})
        self._draw()

    def _in(self):
        return [p for p in self.D["photos"] if p.get("in_gallery") and p.get("kind") == "image"]

    def _draw(self):
        D = self.D
        self.rnav.show(D["nav"])
        self.storage_badge.text = {"cloudflare": "Stored on Cloudflare", "cloudinary": "Stored on Cloudinary"}.get(D["storage"], "Stored by PlanPlate")
        g = self._in()
        o = [p for p in D["photos"] if p not in g]
        self.count_label.text = state.plural(len(g), "photo") + " · in this order"
        self.gallery_panel.items = [dict(p, _gallery=True, _first=i == 0, _last=i == len(g) - 1, _n=i + 1) for i, p in enumerate(g)]
        self.gallery_empty.visible = not g
        self.others_part.visible = bool(o)
        self.others_panel.items = [dict(p, _gallery=False) for p in o]
        self._draw_look()
        self._preview(reload=True)

    def _draw_look(self):
        s = self.D["style"]
        lay = s.get("layout") or "mosaic"
        self.layouts_panel.items = [{"key": k, "name": n, "desc": d, "svg": svg, "on": k == lay} for k, n, d, svg in LAYOUTS]
        self.options_panel.items = [{"key": k, "label": label, "choices": ch, "value": s.get(k)}
                                    for k, label, ch, only in OPTIONS if only is None or lay in only]
        setattr(anvil.js.get_dom_node(self.accent_in), "value", s.get("accent") or "#c9a56a")
        setattr(anvil.js.get_dom_node(self.background_in), "value", s.get("background") or "#1d1b18")
        self.bg_field.visible = s.get("tone") == "custom"
        self.heading_box.text = s.get("heading") or ""
        for name in ("desktop", "phone"):
            getattr(self, "dev_" + name).classes["on"] = self.device == name
        self.preview_box.classes["phone"] = self.device == "phone"

    def _look(self):
        s = self.D["style"]
        return json.dumps({k: s.get(k) for k in LOOK_KEYS})

    def _preview(self, reload=False):
        """The real gallery, as guests will see it. A look change only redraws it (no new download)."""
        box = self.dom_nodes["preview"]
        if not self._in():
            box.innerHTML = '<div class="ui-empty">The preview appears when the gallery has photos.</div>'
            return
        el = box.querySelector("planplate-showcase")
        if el is None or reload:
            box.innerHTML = ""
            el = window.document.createElement("planplate-showcase")
            el.setAttribute("origin", window.location.origin)
            el.setAttribute("fresh", "")
            el.setAttribute("look", self._look())
            el.setAttribute("restaurant", self.D["slug"])
            box.appendChild(el)
            window.PP.loadScript("_/theme/pp-showcase.js")
        else:
            el.setAttribute("look", self._look())

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

    def _sorted(self, ids):
        """A photo was dragged (or moved with the arrow keys on its grip) to a new place."""
        self._photos(state.call("order_photos", self.rid, [str(i) for i in ids]), "Order saved")

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
            for p in self.D["photos"]:
                if p["id"] == photo["id"]:
                    p["caption"] = caption
            self._preview(reload=True)
            state.toast("Caption saved", "ok")

    def _delete(self, photo, **event_args):
        what = "video" if photo.get("kind") == "video" else "photo"
        if confirm("It disappears from the gallery, your website, and any special or event that uses it.", title="Delete this %s?" % what,
                   buttons=[("Keep it", False), ("Delete", True)]):
            self._photos(state.call("delete_photo", self.rid, photo["id"]), "Deleted")

    # ---------------------------------------------------------------- the look
    def _save_style(self, changes):
        self.D["style"].update(changes)
        self._draw_look()
        self._preview()
        r = anvil.server.call_s("save_gallery_style", self.rid, changes)
        if r and r.get("style"):
            self.D["style"] = r["style"]

    def _style_event(self, key, value, **event_args):
        changes = {key: value}
        if key == "layout" and value != self.D["style"].get("layout"):
            changes.update(RECOMMENDED.get(value, {}))  # a new layout starts from the look that suits it
        self._save_style(changes)

    def color_change(self, event):
        self._save_style({event.currentTarget.getAttribute("data-k"): event.currentTarget.value})

    @handle("heading_box", "lost_focus")
    def heading_box_lost_focus(self, **event_args):
        if (self.heading_box.text or "") != (self.D["style"].get("heading") or ""):
            self._save_style({"heading": self.heading_box.text or ""})

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        self._save_style(dict(RECOMMENDED.get(self.D["style"].get("layout") or "mosaic", {}), lightbox="on"))
        state.toast("Recommended look", "ok")

    def device_click(self, event):
        self.device = event.currentTarget.getAttribute("data-d")
        state.store_set("galDevice", self.device)
        self._draw_look()
