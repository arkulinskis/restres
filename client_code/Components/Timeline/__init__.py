import json

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import TimelineTemplate


class Timeline(TimelineTemplate):
    """Wraps the JavaScript timeline engine (PP.timeline in theme/assets/pp-timeline.js)."""

    def __init__(self, **properties):
        self.init_components(**properties)
        self._handler = anvil.js.report_exceptions(self._on)

    def draw(self, day):
        window.PP.timeline(self.dom_nodes["host"], window.JSON.parse(json.dumps(day)), self._handler)

    def _on(self, kind, payload):
        if kind == "edit":
            self.raise_event("edit", id=payload["id"])
        else:
            self.raise_event("slot", time=payload["time"], table=payload["table"])
