from anvil import *
from anvil.js import window

from ._anvil_designer import LandingTemplate


class Landing(LandingTemplate):
    """#landing: what PlanPlate is, for visitors. The hero fills the screen on any monitor (photo panel left, the
    sign-in box right); the sections below explain the product. Signed-in people go to #dashboard instead."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)

    def jump_click(self, event):
        window.PP.scrollToId(event.currentTarget.getAttribute("data-jump"))

    def mode_click(self, event):
        self.auth_box.set_mode(event.currentTarget.getAttribute("data-mode"))
        self.dom_nodes_box().scrollIntoView({"behavior": "smooth", "block": "center"})
        self.auth_box.set_mode(self.auth_box.mode, focus=True)

    def dom_nodes_box(self):
        from anvil.js import get_dom_node
        return get_dom_node(self.box_holder)

    def film_click(self, event):
        """Swap the cover for YouTube's privacy-enhanced player only when it's pressed."""
        frame = window.document.createElement("iframe")
        for k, v in (("src", "https://www.youtube-nocookie.com/embed/4KcdhVtqgNQ?autoplay=1&rel=0&playsinline=1"),
                     ("title", "PlanPlate video"), ("allow", "autoplay; encrypted-media; picture-in-picture; fullscreen"),
                     ("allowfullscreen", ""), ("referrerpolicy", "strict-origin-when-cross-origin")):
            frame.setAttribute(k, v)
        cover = event.currentTarget
        cover.parentNode.replaceChild(frame, cover)
