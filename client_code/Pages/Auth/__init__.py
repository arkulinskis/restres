from anvil import *

from ._anvil_designer import AuthTemplate


class Auth(AuthTemplate):
    """#auth (sign in), #auth/signup, #auth/reset: the sign-in box on its own page (the landing hero has the same box)."""

    def __init__(self, args: tuple = (), **properties):
        super().__init__(**properties)
        self.box.set_mode(args[0] if args else "login")

    @handle("", "show")
    def form_show(self, **event_args):
        self.box.set_mode(self.box.mode, focus=True)
