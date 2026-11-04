from anvil import *

from ._anvil_designer import CodeBlockTemplate
from ... import pp, state


class CodeBlock(CodeBlockTemplate):
    """A snippet to copy (Share page). item = {title, text, code, open?}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.open_link.visible = bool(self.item.get("open"))
        if self.item.get("open"):
            state.set_attr(self.open_link, "href", self.item["open"])

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        pp.copy(self.item["code"], self.item["title"])
