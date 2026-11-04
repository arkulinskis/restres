"""The app starts here (anvil.yaml: startup module). One server call to learn who is signed in (Anvil's loading
spinner shows meanwhile), the Privacy & Terms kit, then the page for the address in the browser bar.
Guest pages (#book, #r, #menu) skip the sign-in check: they are often embedded in a restaurant's website."""
import anvil.server
from anvil.js import window

from . import legal, pp, router, state

LEGAL_THEME = {"accent": "#9c7a43"}  # colours for the Privacy & Terms page (the brass of app.css)

legal.setup(LEGAL_THEME)
pp.setup()
_name, _args = router.parse(window.location.hash)
if _name not in router.PUBLIC:
    state.set_me(anvil.server.call("get_me"))
    if state.me():
        legal.refresh_soon()
router.start()
