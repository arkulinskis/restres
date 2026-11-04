import json

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import FloorPlanTemplate


class FloorPlan(FloorPlanTemplate):
    """Wraps the JavaScript floor-plan engine (PP.floor in theme/assets/pp-floor.js)."""

    def __init__(self, **properties):
        self.init_components(**properties)
        self._handler = anvil.js.report_exceptions(self._on)

    def draw(self, plan):
        window.PP.floor(self.dom_nodes["host"], window.JSON.parse(json.dumps(plan)), self._handler)

    def _on(self, kind, payload):
        if kind == "pick":
            self.raise_event("pick", id=payload["id"])
        else:
            self.raise_event("move", id=payload["id"], x=float(payload["x"]), y=float(payload["y"]))
