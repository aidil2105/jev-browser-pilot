from pathlib import Path

import pytest

from jev_pilot.bench import expected_match, load_fixtures, render_markdown, run_bench
from jev_pilot.providers.base import ScriptedChooser

FIXTURES = Path(__file__).parent / "fixtures" / "calc-frozen.json"


def test_shipped_fixture_loads():
    cases = load_fixtures(str(FIXTURES))
    assert [c.name for c in cases] == ["calc-start", "calc-after-plus", "calc-at-answer",
                                       "calc-unreachable"]
    assert cases[0].options[0].id == "13"
    assert cases[2].expect == "__done__"


def test_expected_match_accepts_labels_and_ids():
    case = load_fixtures(str(FIXTURES))[0]
    assert expected_match(case, "act", "30", "Button 'Five'") is True
    assert expected_match(case, "act", "30", "button   five") is True  # punctuation and spacing
    assert expected_match(case, "act", "27", "Button 'Two'") is False
    assert expected_match(case, "escalate", "30", "Button 'Five'") is False


def test_expected_match_on_sentinels():
    done_case = load_fixtures(str(FIXTURES))[2]
    assert expected_match(done_case, "done", None, None) is True
    assert expected_match(done_case, "act", "24", "Button 'Equals'") is False


def test_a_bare_option_id_is_read_as_an_id_not_a_label():
    """Regression: a captured fixture used bare ids against a label-comparing bench, so a run where
    every pick was right was reported as a total miss."""
    from jev_pilot.bench import Fixture
    from jev_pilot.types import Option

    options = [Option(id="100", label="a 'slide rule'"), Option(id="5", label="a 'abacus'")]
    bare = Fixture(name="c", goal="open the slide rule article", state="s", options=options,
                   expect="100")
    assert expected_match(bare, "act", "100", "a 'slide rule'") is True
    assert expected_match(bare, "act", "5", "a 'abacus'") is False

    prefixed = Fixture(name="c", goal="g", state="s", options=options, expect="id:100")
    assert expected_match(prefixed, "act", "100", "a 'slide rule'") is True
    assert expected_match(prefixed, "escalate", "100", "a 'slide rule'") is False

    # a label form keeps working, and an id that is not an option is still read as a label
    labelled = Fixture(name="c", goal="g", state="s", options=options, expect="a 'slide rule'")
    assert expected_match(labelled, "act", "100", "a 'slide rule'") is True
    assert expected_match(labelled, "act", "7", "something else") is False


def test_run_bench_aggregates_two_choosers():
    cases = load_fixtures(str(FIXTURES))[:2]
    choosers = {"right": ScriptedChooser(["30", "28"]), "wrong": ScriptedChooser(["13"])}
    report = run_bench(cases, choosers, repeats=1)
    assert report["summary"]["right"]["correct"] == 2
    assert report["summary"]["wrong"]["correct"] == 0
    assert report["summary"]["right"]["accuracy"] == 1.0
    assert report["summary"]["right"]["coverage"] == 1.0
    assert report["summary"]["right"]["median_latency_ms"] is not None
    assert len(report["results"]) == 4


def test_run_bench_counts_errors_as_unanswered_not_wrong():
    cases = load_fixtures(str(FIXTURES))[:1]
    choosers = {"broken": ScriptedChooser([], fail_with="HTTP 503")}
    report = run_bench(cases, choosers)
    stats = report["summary"]["broken"]
    assert stats["errors"] == 1
    assert stats["answered"] == 0
    assert stats["coverage"] == 0.0
    assert stats["correct"] == 0


def test_run_bench_honours_the_fixture_floor():
    cases = load_fixtures(str(FIXTURES))[:1]
    choosers = {"low": ScriptedChooser([("30", 0.1)])}
    report = run_bench(cases, choosers, floor=0.6)
    assert report["results"][0]["outcome"] == "escalate"
    assert report["summary"]["low"]["escalations"] == 1


def test_markdown_render_has_both_tables():
    cases = load_fixtures(str(FIXTURES))[:2]
    report = run_bench(cases, {"mock": ScriptedChooser(["30"])})
    markdown = render_markdown(report)
    assert "| chooser | correct |" in markdown
    assert "| case | chooser | expect |" in markdown
    assert "calc-start" in markdown


def test_bad_fixture_file_is_rejected(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text('{"cases": "not a list"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_fixtures(str(broken))
