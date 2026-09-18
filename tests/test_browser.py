"""Browser surface tests.

The pure parts run anywhere. The `live` test launches a real Chrome against a local
fixture page; it is deselected by default (`-m 'not live'`) and proves the whole loop:
perception, decision, click, navigation and verification.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jev_pilot.browser import BrowserPilot, BrowserUnavailable, find_chrome, free_port
from jev_pilot.perception import DomRules, click_js, probe_js, stamp_selector
from jev_pilot.providers.base import KeywordChooser
from jev_pilot.safety import SafetyError, SafetyPolicy

SITE = Path(__file__).parent / "fixtures" / "site"
INDEX_URI = (SITE / "index.html").as_uri()


def chrome_available() -> bool:
    try:
        find_chrome()
        return True
    except BrowserUnavailable:
        return False


needs_chrome = pytest.mark.skipif(not chrome_available(), reason="no chrome/chromium installed")


def test_free_port_is_a_usable_port():
    port = free_port()
    assert 1024 < port < 65536


def test_missing_browser_path_is_reported():
    with pytest.raises(BrowserUnavailable):
        find_chrome("C:/definitely/not/here/chrome.exe")


def test_click_js_targets_the_stamped_element():
    import json

    script = click_js(DomRules(), "17")
    assert json.dumps(stamp_selector(DomRules(), "17")) in script


def test_probe_js_shape():
    assert probe_js("main") == '(() => !!document.querySelector("main"))()'


@needs_chrome
def test_safety_is_checked_before_a_browser_is_launched():
    pilot = BrowserPilot("https://example.test/", safety=SafetyPolicy.for_hosts(["other.test"]))
    with pytest.raises(SafetyError):
        pilot.start()


@needs_chrome
def test_construction_does_not_launch_anything():
    pilot = BrowserPilot(INDEX_URI, safety=SafetyPolicy.for_hosts(["file"]))
    assert pilot._process is None
    assert pilot.port > 0
    pilot.close()  # nothing to close; must not raise


@pytest.mark.live
@needs_chrome
def test_live_loop_navigates_a_real_browser(tmp_path):
    safety = SafetyPolicy.for_hosts(["file"])
    rules = DomRules(cap=50)
    pilot = BrowserPilot(INDEX_URI, headless=True, rules=rules, safety=safety,
                         settle_seconds=1.5, profile_dir=str(tmp_path / "profile"))
    try:
        pilot.start()
        snapshot = pilot.observe()
        assert "Alpha report" in [el.name for el in snapshot.elements]
        assert snapshot.matched_total >= 2

        from jev_pilot.loop import run_episode
        episode = run_episode(pilot, KeywordChooser(), "open the Omega appendix",
                              verifiers=["url-contains:omega.html"], steps=3, safety=safety)
        assert episode.reached is True, episode.summary()
        assert episode.stopped == "reached"
        assert episode.steps[0].decision.label == "a 'Omega appendix'"
    finally:
        pilot.close()
