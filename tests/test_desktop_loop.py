"""The desktop surface driven by a scripted driver, so the whole path is covered in CI.

No windows, no cua-driver, no credentials: `FakeCalculatorDriver` keeps a display value and
applies clicks the way a calculator does, and the surface talks to it exactly as it talks to the
real driver. That means the loop, the policy, the click routing by element token, the window text
and the postcondition are all exercised by the credential-free suite.
"""

from __future__ import annotations

import pytest

from jev_pilot.desktop import DesktopPilot, DriverUnavailable
from jev_pilot.loop import run_episode
from jev_pilot.providers.base import ScriptedChooser
from jev_pilot.safety import SafetyPolicy

BUTTONS = [("30", "Five", "t-five"), ("23", "Plus", "t-plus"),
           ("28", "Three", "t-three"), ("24", "Equals", "t-equals")]
BY_TOKEN = {token: (label, index) for index, label, token in BUTTONS}


class FakeCalculatorDriver(DesktopPilot):
    """A stand-in for a real window: clicks change what the next observation reports."""

    def __init__(self, *, pid: int = 4242, **kwargs):
        super().__init__(driver="fake-driver", attach_pid=pid, **kwargs)
        self.display = "0"
        self.pending = None
        self.calls = []
        self.killed = False
        self.empty_tree = False

    def call(self, tool, args, timeout=120.0):
        self.calls.append((tool, dict(args)))
        if tool == "get_window_state":
            if self.empty_tree:
                return {"structuredContent": {"elements": []}}
            return {
                "structuredContent": {
                    "window_id": args.get("window_id") or "w-1",
                    "window_title": "Calculator",
                    "total_element_count": len(BUTTONS) + 1,
                    "elements": [{"element_index": 8, "role": "Text",
                                  "label": f"Display is {self.display}"}] + [
                        {"element_index": int(index), "role": "Button", "label": label,
                         "element_token": token} for index, label, token in BUTTONS],
                },
            }
        if tool == "click":
            token = args.get("element_token")
            label = BY_TOKEN.get(token, (None, None))[0]
            if label == "Five":
                self.display = "5"
            elif label == "Plus":
                self.pending = int(self.display)
            elif label == "Three":
                self.display = "3"
            elif label == "Equals" and self.pending is not None:
                self.display = str(self.pending + int(self.display))
            return {"route": "accessibility", "effect": "unverifiable", "tool": tool}
        if tool == "kill_app":
            self.killed = True
            return {"ok": True}
        return {"isError": True, "error": f"unexpected tool {tool}"}


@pytest.fixture(autouse=True)
def no_invoke_wait(monkeypatch):
    """The real surface waits 1.4 s for a UWP invoke to land; a scripted driver needs none."""
    monkeypatch.setattr("jev_pilot.desktop.time.sleep", lambda *_: None)


def test_a_full_episode_through_the_scripted_driver():
    driver = FakeCalculatorDriver()
    chooser = ScriptedChooser(["30", "23", "28", "24"])  # Five, Plus, Three, Equals
    episode = run_episode(driver, chooser, "compute 5 + 3 and stop when the display shows 8",
                          verifiers=["text-contains:8"], steps=6,
                          safety=SafetyPolicy(allow_actions=("click",)))

    assert episode.reached is True, episode.summary()
    assert episode.stopped == "reached"
    assert len(episode.steps) == 4
    assert driver.display == "8"

    clicks = [args for tool, args in driver.calls if tool == "click"]
    assert [args.get("element_token") for args in clicks] == ["t-five", "t-plus", "t-three", "t-equals"]
    assert all(args["pid"] == 4242 for args in clicks)


def test_the_window_text_is_content_only_and_values_lead():
    driver = FakeCalculatorDriver()
    snapshot = driver.observe()
    assert snapshot.text.startswith("Display is 0")
    # buttons are candidates, not window text
    assert "Five" not in snapshot.text
    assert "Five" in [el.name for el in snapshot.elements]

    # item roles count as content, so a file list or a tree is readable; menu chrome does not
    text = DesktopPilot._text_of([{"role": "ListItem", "label": "report.txt"},
                                  {"role": "Text", "label": "3 items"},
                                  {"role": "MenuItem", "label": "File"}])
    assert text.startswith("3 items")
    assert "report.txt" in text
    assert "File" not in text


def test_an_empty_tree_is_reported_rather_than_guessed():
    driver = FakeCalculatorDriver()
    driver.empty_tree = True
    with pytest.raises(DriverUnavailable) as excinfo:
        driver.observe()
    assert "accessibility tree came back empty" in str(excinfo.value)


def test_a_click_without_a_token_falls_back_to_the_element_index():
    driver = FakeCalculatorDriver()
    # strip the token, the way a driver that does not expose one would
    original = driver.call

    def call(tool, args, timeout=120.0):
        if tool == "get_window_state":
            payload = original(tool, args)
            for element in payload["structuredContent"]["elements"]:
                element.pop("element_token", None)
            driver.calls.append((tool, dict(args)))
            return payload
        return original(tool, args)

    driver.call = call
    driver.observe()
    result = driver.act("30")
    assert result["clicked"] is True
    click_args = [args for tool, args in driver.calls if tool == "click"][-1]
    assert click_args["element_index"] == 30
    assert click_args["window_id"] == "w-1"
    assert "element_token" not in click_args


def test_kill_is_explicit_and_off_by_default():
    driver = FakeCalculatorDriver()
    driver.observe()
    driver.close()          # closing leaves the window alone
    assert driver.killed is False
    driver.kill()
    assert driver.killed is True
