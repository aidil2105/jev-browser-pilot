"""What the loop needs from whatever it is driving.

The loop never imports a browser, a desktop driver or a test double: it talks to a
`Surface`. That is what makes the same policy, safety rails, tracing and
verification apply to a real Chrome, a real desktop window, a recorded trace, or a
scripted sequence in a unit test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from jev_pilot.perception import Snapshot


class Surface:
    name = "surface"

    def observe(self) -> Snapshot:  # pragma: no cover - interface
        raise NotImplementedError

    def url(self) -> Optional[str]:  # pragma: no cover - interface
        return None

    def probe(self, selector: str) -> Optional[bool]:  # pragma: no cover - interface
        """Existence check for `selector:` postconditions. None means unsupported."""
        return None

    def act(self, option_id: str) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface
        return None

    def describe(self) -> str:
        return self.name


@dataclass
class ScriptedSurface(Surface):
    """A surface that replays prepared snapshots and records the actions taken.

    Used by `jev-pilot selftest`, by the unit tests, and by anyone who wants to see
    the whole loop run end to end with no browser and no credentials.
    """

    snapshots: List[Snapshot] = field(default_factory=list)
    name = "scripted"
    actions: List[str] = field(default_factory=list)
    default_selector_present: bool = True

    def observe(self) -> Snapshot:
        if not self.snapshots:
            return Snapshot(url=None, title=None, text="", elements=[], matched_total=0)
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]

    def url(self) -> Optional[str]:
        return self.snapshots[0].url if self.snapshots else None

    def probe(self, selector: str) -> Optional[bool]:
        return self.default_selector_present

    def act(self, option_id: str) -> Dict[str, Any]:
        self.actions.append(str(option_id))
        return {"clicked": True, "option_id": str(option_id), "engine": "scripted"}

    def describe(self) -> str:
        return f"scripted({len(self.snapshots)} snapshot(s) left)"
