from anvil import *
import anvil.js

from ._anvil_designer import SiteFieldTemplate
from ... import router, site_model, state

EMPTY = {"reviews": {"name": "", "source": "", "rating": 5, "text": ""}, "highlights": {"title": "", "text": ""}}


class SiteField(SiteFieldTemplate):
    """One field of the website builder. item = {spec, model, rid}; spec["type"] picks what shows:
    text | area | check | show | photo | info | path | palette | accent | language | hero | list.
    It writes into the model (site_model.Model.set); "x-redraw" asks the page to redraw the sections."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.spec, self.m = self.item["spec"], self.item["model"]
        sp, m, t = self.spec, self.m, self.spec["type"]
        for c in (self.prefix_box, self.text_box, self.area_box, self.check_box, self.show_row, self.photo_field, self.info_box, self.pals_box,
                  self.accent_row, self.drop, self.chips_panel, self.list_box):
            c.visible = False
        self.cap.visible = bool(sp.get("label")) and t in ("text", "area", "path", "palette", "language")
        self.cap.text = sp.get("label") or ""
        if sp.get("label"):  # the caption above isn't a <label>: give the field its name directly
            for c in (self.prefix_text, self.text_box, self.area_box, self.drop):
                state.set_control_attr(c, "aria-label", sp["label"])
        state.set_attr(self.accent_in, "aria-label", "Your accent colour")
        self.hint.visible = bool(sp.get("hint"))
        self.hint.text = sp.get("hint") or ""
        if t == "text":
            self.text_box.visible = True
            self.text_box.text = m.get(sp["path"], "") or ""
            self.text_box.placeholder = sp.get("ph") or ""
        elif t == "area":
            self.area_box.visible = True
            self.area_box.text = m.get(sp["path"], "") or ""
            self.area_box.placeholder = sp.get("ph") or ""
            self.area_box.height = str(sp.get("h") or 90)
        elif t == "check":
            self.check_box.visible = True
            self.check_box.text = sp["label"]
            self.check_box.checked = bool(m.get(sp["path"]))
        elif t == "show":
            self.show_row.visible = True
            self.show_box.text = "Show %s on the website" % sp["label"]
            self.show_box.checked = bool(m.get("content.sections." + sp["key"]))
        elif t == "photo":
            self.photo_field.visible = True
            self.photo_field.rid = self.item["rid"]
            self.photo_field.label = sp["label"]
            self.photo_field.kind = sp.get("kind") or "image"
            self.photo_field.photo = m.photo(m.get(sp["path"]))
        elif t == "info":
            self.info_box.visible = True
            self.info_label.text = sp["text"]
            self.go_link.visible = bool(sp.get("go"))
            if sp.get("go"):
                anvil.js.get_dom_node(self.go_link).textContent = sp["go_label"] + " →"
                state.set_attr(self.go_link, "href", router.href(sp["go"], self.item["rid"]))
        elif t == "path":
            self.prefix_box.visible = True
            self.prefix_label.text = sp["prefix"]
            self.prefix_text.text = m.F["path"]
        elif t == "palette":
            self.pals_box.visible = True
            self.pals_panel.items = [dict(p, _on=p["key"] == m.F["palette"], _accent=m.F["accent"]) for p in m.D["palettes"]]
            self.pals_panel.add_event_handler("x-palette", self._palette)
        elif t == "accent":
            self.accent_row.visible = True
            self.accent_box.checked = bool(m.F["accent"])
            node = anvil.js.get_dom_node(self.accent_in)
            setattr(node, "value", m.F["accent"] or m.palette()["accent"])
            setattr(node, "disabled", not m.F["accent"])
        elif t == "language":
            self.drop.visible = True
            self.drop.items = [(site_model.LANG_NAMES.get(l, l), l) for l in m.D["languages"]]
            self.drop.selected_value = m.F["language"]
            state.set_control_attr(self.drop, "aria-label", sp.get("label") or "Language")  # after .items: the select is rebuilt
        elif t == "hero":
            self.chips_panel.visible = True
            kind = m.get("content.hero.kind") or "photo"
            self.chips_panel.items = [{"label": label, "value": v, "on": v == kind} for v, label in (("photo", "Photo"), ("video", "Video"), ("youtube", "YouTube"))]
            self.chips_panel.add_event_handler("x-chip", self._hero)
        elif t == "list":
            self.list_box.visible = True
            self.add_button.text = "Add a review" if sp["list"] == "reviews" else "Add a highlight"
            self.list_panel.add_event_handler("x-remove", self._remove)
            self.list_panel.add_event_handler("x-changed", self._list_changed)
            self._list()

    # ---------------------------------------------------------------- writing back
    @handle("text_box", "change")
    def text_box_change(self, **event_args):
        self.m.set(self.spec["path"], self.text_box.text or "")

    @handle("area_box", "change")
    def area_box_change(self, **event_args):
        self.m.set(self.spec["path"], self.area_box.text or "")

    @handle("check_box", "change")
    def check_box_change(self, **event_args):
        self.m.set(self.spec["path"], bool(self.check_box.checked))

    @handle("show_box", "change")
    def show_box_change(self, **event_args):
        self.m.set("content.sections." + self.spec["key"], bool(self.show_box.checked))
        self.parent.raise_event("x-redraw")

    @handle("photo_field", "change")
    def photo_field_change(self, **event_args):
        p = self.photo_field.photo
        self.m.add_photo(p)
        self.m.set(self.spec["path"], p["key"] if p else "")
        self.parent.raise_event("x-redraw")

    @handle("prefix_text", "change")
    def prefix_text_change(self, **event_args):
        self.m.F["path"] = self.prefix_text.text or ""
        self.m.set("path", self.prefix_text.text or "")

    @handle("drop", "change")
    def drop_change(self, **event_args):
        self.m.set("language", self.drop.selected_value)

    def _palette(self, key, **event_args):
        self.m.set("palette", key)
        self.parent.raise_event("x-redraw")

    @handle("accent_box", "change")
    def accent_box_change(self, **event_args):
        node = anvil.js.get_dom_node(self.accent_in)
        setattr(node, "disabled", not self.accent_box.checked)
        self.m.set("accent", getattr(node, "value") if self.accent_box.checked else "")
        self.parent.raise_event("x-redraw")

    def accent_input(self, event):
        if self.accent_box.checked:
            self.m.set("accent", event.currentTarget.value)

    def _hero(self, value, **event_args):
        self.m.set("content.hero.kind", value)
        self.parent.raise_event("x-redraw")

    # ---------------------------------------------------------------- reviews / highlights
    def _list(self):
        name = self.spec["list"]
        rows = self.m.get("content." + name) or []
        self.list_panel.items = [{"kind": name, "i": i, "row": r, "model": self.m} for i, r in enumerate(rows)]
        self.add_button.visible = len(rows) < 8

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        name = self.spec["list"]
        rows = list(self.m.get("content." + name) or [])
        rows.append(dict(EMPTY[name]))
        self.m.set("content." + name, rows)
        self.parent.raise_event("x-redraw")

    def _remove(self, i, **event_args):
        name = self.spec["list"]
        rows = list(self.m.get("content." + name) or [])
        rows.pop(i)
        self.m.set("content." + name, rows)
        self.parent.raise_event("x-redraw")

    def _list_changed(self, **event_args):
        self.m.set("content." + self.spec["list"], self.m.get("content." + self.spec["list"]))
