"""Desktop surface tests.

The pure parts run anywhere. There is no `live` test here yet: a full click cycle needs
a real window, a real driver and a real model, so it is run by hand and recorded in
`docs/findings.md` rather than wired into CI.
"""

from __future__ import annotations

import pytest

from jev_pilot.desktop import DesktopPilot, DriverUnavailable, find_driver

CALC_TREE = [
    {"element_index": 5, "role": "Text", "label": "Calculator", "enabled": True},
    {"element_index": 7, "role": "Text", "label": "PaneTitleTextBlock", "enabled": True},
    {"element_index": 8, "role": "Text", "label": "Display is 8", "enabled": True},
    {"element_index": 30, "role": "Button", "label": "Five", "element_token": "tok-30"},
    {"element_index": 24, "role": "Button", "label": "Equals", "element_token": "tok-24"},
]


def test_text_prefers_the_value_like_label():
    text = DesktopPilot._text_of(CALC_TREE)
    assert text.startswith("Display is 8")
    assert "Calculator" in text  # the rest is still reported, just not first


def test_text_deduplicates_and_ignores_non_text_roles():
    text = DesktopPilot._text_of(CALC_TREE + [{"element_index": 9, "role": "Text",
                                               "label": "Display is 8"}])
    assert text.count("Display is 8") == 1
    assert "Five" not in text and "Equals" not in text


def test_text_is_empty_without_text_elements():
    assert DesktopPilot._text_of([{"element_index": 1, "role": "Button", "label": "Run"}]) == ""


def test_text_is_capped():
    elements = [{"element_index": i, "role": "Text", "label": f"label {i}"} for i in range(200)]
    assert len(DesktopPilot._text_of(elements)) <= 400


def test_driver_can_be_pointed_at_a_path(tmp_path):
    fake = tmp_path / "cua-driver"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    assert find_driver(str(fake)) == str(fake)


def test_env_var_overrides_the_search(monkeypatch, tmp_path):
    fake = tmp_path / "cua-driver-env"
    fake.write_text("x", encoding="utf-8")
    monkeypatch.setenv("JEV_PILOT_CUA_DRIVER", str(fake))
    assert find_driver() == str(fake)


def test_a_missing_driver_is_reported(monkeypatch, tmp_path):
    monkeypatch.delenv("JEV_PILOT_CUA_DRIVER", raising=False)
    monkeypatch.setattr("jev_pilot.desktop.shutil.which", lambda name: None)
    monkeypatch.setattr("jev_pilot.desktop.DRIVER_CANDIDATES", (str(tmp_path / "nope"),))
    with pytest.raises(DriverUnavailable):
        find_driver()
