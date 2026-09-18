import json

from jev_pilot.perception import (DEFAULT_EXCLUDES, DomRules, Element,
                                  click_js, elements_from_uia, options_from_elements,
                                  parse_snapshot, probe_js, stamp_selector)


def test_js_carries_the_rules():
    rules = DomRules(cap=42)
    script = rules.js()
    assert "data-jev-idx" in script
    assert ".navbox" in script
    assert "42" in script
    assert "matched_total" in script


def test_element_label_matches_the_tree_language():
    assert Element(id="1", role="Button", name="Five").label() == "Button 'Five'"
    assert Element(id="1", role="a", name="  Omega   appendix ").label() == "a 'Omega appendix'"
    assert "value=" in Element(id="1", role="Edit", name="Name", value="Ada").label()
    assert Element(id="1", role="a", name="x", enabled=False).label().endswith("(disabled)")


def test_options_carry_ids_and_labels():
    options = options_from_elements([Element(id="7", role="Button", name="Plus")])
    assert options[0].id == "7"
    assert options[0].label == "Button 'Plus'"


def test_parse_snapshot_normalises_and_detects_truncation():
    payload = {
        "url": "https://example.test/",
        "title": "Example",
        "text": "hello world",
        "matched_total": 500,
        "elements": [
            {"index": 0, "tag": "a", "text": "Alpha report", "enabled": True},
            {"index": 1, "role": "button", "text": "Recalculate", "disabled": True},
            {"index": 2, "tag": "a", "text": "   "},
        ],
    }
    snapshot = parse_snapshot(payload)
    assert [e.id for e in snapshot.elements] == ["0", "1"]
    assert snapshot.elements[0].role == "a"
    assert snapshot.elements[1].enabled is False
    assert snapshot.truncated is True
    assert len(snapshot.options()) == 2


def test_parse_snapshot_without_truncation():
    snapshot = parse_snapshot({"elements": [{"index": 0, "tag": "a", "text": "one"}],
                               "matched_total": 1})
    assert snapshot.truncated is False


def test_elements_from_uia_respects_cap():
    raw = [{"element_index": i, "role": "Button", "label": f"Button {i}"} for i in range(10)]
    assert len(elements_from_uia(raw, cap=4)) == 4
    assert elements_from_uia([{"element_index": 0, "role": "Button", "label": ""}]) == []


def test_click_js_addresses_the_stamp():
    rules = DomRules()
    selector = stamp_selector(rules, "12")
    assert selector == '[data-jev-idx="12"]'
    script = click_js(rules, "12")
    # the CSS selector is embedded as a JS string literal, so quotes are escaped
    assert json.dumps(selector) in script
    assert "click()" in script


def test_probe_js_is_an_existence_check():
    assert probe_js("#thing") == '(() => !!document.querySelector("#thing"))()'


def test_default_excludes_cover_the_usual_junk():
    for fragment in ("table", ".navbox", ".reflist", "sup"):
        assert fragment in DEFAULT_EXCLUDES
