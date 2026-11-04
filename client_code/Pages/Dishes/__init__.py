from anvil import *
import anvil.server

from ._anvil_designer import DishesTemplate
from ... import pp, state


class Dishes(DishesTemplate):
    """#dishes/<rid>: the menu editor (sections, dishes, labels, sold out, order). The guest menu is #menu/<slug>."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.rid = args[0]
        self.D = anvil.server.call("get_menu_admin", self.rid)
        p = self.sections_panel
        p.add_event_handler("x-edit-section", self._edit_section)
        p.add_event_handler("x-delete-section", self._delete_section)
        p.add_event_handler("x-move", self._move)
        p.add_event_handler("x-edit-dish", self._edit_dish)
        p.add_event_handler("x-new-dish", self._new_dish)
        p.add_event_handler("x-toggle-dish", self._toggle_dish)
        self.files_panel.add_event_handler("x-delete-file", self._delete_file)
        self._draw()
        self._files(anvil.server.call("get_menu_files", self.rid))

    def _draw(self):
        D = self.D
        self.rnav.show(D["nav"])
        state.set_attr(self.public_link, "href", pp.menu_url(D["nav"]["restaurant"]["slug"]))
        n = len(D["sections"])
        self.sections_panel.items = [dict(s, _tags=D["tags"], _first=k == 0, _last=k == n - 1) for k, s in enumerate(D["sections"])]
        self.empty.visible = not D["sections"]

    def _apply(self, res, msg=None):
        if res:
            self.D = res
            self._draw()
            if msg:
                state.toast(msg, "ok")

    def _section_dialog(self, section=None):
        from ...Dialogs.SectionEditor import SectionEditor
        self._apply(alert(SectionEditor(self.rid, section), buttons=[], role="app-dialog", dismissible=True), "Section saved")

    @handle("new_section_button", "click")
    def new_section_button_click(self, **event_args):
        self._section_dialog()

    def _edit_section(self, section, **event_args):
        self._section_dialog(section)

    def _delete_section(self, section, **event_args):
        if confirm("Its %s go too." % state.plural(len(section["items"]), "dish", "dishes"), title="Delete “%s”?" % section["title"],
                   buttons=[("Keep it", False), ("Delete section", True)]):
            self._apply(state.call("delete_section", self.rid, section["id"]), "Section deleted")

    def _move(self, kind, row_id, step, **event_args):
        self._apply(state.call("move_menu_row", self.rid, kind, row_id, step))

    def _dish_dialog(self, dish, section_id):
        from ...Dialogs.DishEditor import DishEditor
        self._apply(alert(DishEditor(self.rid, self.D, dish, section_id), buttons=[], role="app-dialog", dismissible=True), "Menu saved")

    def _edit_dish(self, dish, section_id, **event_args):
        self._dish_dialog(dish, section_id)

    def _new_dish(self, section_id, **event_args):
        self._dish_dialog(None, section_id)

    # ---- menu files (PDFs or photos, per language)
    def _files(self, r):
        if r:
            self.files_panel.items = r["files"]

    @handle("file_loader", "change")
    def file_loader_change(self, file, **event_args):
        if file is None:
            return
        title = (self.file_title.text or "").strip() or (file.name or "Menu").rsplit(".", 1)[0][:60]
        r = state.call("add_menu_file", self.rid, file, title, self.file_lang.selected_value or "")
        self.file_loader.clear()
        if r:
            self.file_title.text = ""
            self._files(r)
            state.toast("Menu file added", "ok")

    def _delete_file(self, file, **event_args):
        if confirm("Guests won't see it any more.", title="Delete %s?" % file["title"], buttons=[("Keep it", False), ("Delete", True)]):
            self._files(state.call("delete_menu_file", self.rid, file["id"]))

    def _toggle_dish(self, dish, section_id, **event_args):
        data = {k: v for k, v in dish.items() if not k.startswith("_")}
        data.update(section_id=section_id, available=not dish["available"])
        self._apply(state.call("save_item", self.rid, data), "Marked sold out" if dish["available"] else "Back on the menu")
