import pytest

from jev_pilot.verify import (SpecificationError, VerificationContext, all_passed,
                              parse_postcondition, verify_all)


def make_ctx(**kwargs):
    defaults = dict(url="https://example.test/omega.html", text="GOAL REACHED: omega")
    defaults.update(kwargs)
    return VerificationContext(**defaults)


def test_url_contains_is_case_sensitive():
    assert parse_postcondition("url-contains:omega.html").check(make_ctx())["passed"] is True
    assert parse_postcondition("url-contains:OMEGA").check(make_ctx())["passed"] is False


def test_url_regex():
    assert parse_postcondition(r"url-regex:/wiki/[A-Z]").check(
        make_ctx(url="https://example.test/wiki/Slide_rule"))["passed"] is True


def test_text_contains_is_case_insensitive_and_whitespace_normalised():
    ctx = make_ctx(text="Goal\n   REACHED")
    assert parse_postcondition("text-contains:goal reached").check(ctx)["passed"] is True


def test_selector_check_reports_when_there_is_no_page():
    result = parse_postcondition("selector:#done").check(make_ctx())
    assert result["passed"] is False
    assert "no live page" in result["detail"]


def test_selector_check_uses_the_probe():
    ctx = make_ctx(probe=lambda selector: selector == "#done")
    assert parse_postcondition("selector:#done").check(ctx)["passed"] is True
    assert parse_postcondition("selector:#other").check(ctx)["passed"] is False


def test_file_contains(tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("the answer is 8", encoding="utf-8")
    spec = f"file-contains:{target}::answer is 8"
    assert parse_postcondition(spec).check(make_ctx())["passed"] is True
    missing = f"file-contains:{tmp_path / 'nope.txt'}::anything"
    assert parse_postcondition(missing).check(make_ctx())["passed"] is False


def test_bad_specs_are_rejected_loudly():
    for bad in ("", "no-colon", "file-contains:/tmp/x", "url-contains:", "whatever:x"):
        with pytest.raises(SpecificationError):
            parse_postcondition(bad)


def test_verify_all_records_every_spec_including_the_broken_one():
    results = verify_all(["url-contains:omega", "nonsense"], make_ctx())
    assert len(results) == 2
    assert results[0]["passed"] is True
    assert results[1]["passed"] is False
    assert "expected url-contains" in results[1]["detail"]


def test_all_passed_requires_a_non_empty_pass_set():
    assert all_passed([]) is False
    assert all_passed([{"passed": True}, {"passed": True}]) is True
    assert all_passed([{"passed": True}, {"passed": False}]) is False
