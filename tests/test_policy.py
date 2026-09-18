import pytest

from jev_pilot.policy import (DONE, STUCK, apply_policy, build_criteria,
                              build_instructions)
from jev_pilot.types import Option

OPTIONS = [Option(id="1", label="a 'Alpha report'"),
           Option(id="2", label="a 'Omega appendix'", detail="link")]


def test_criteria_includes_every_option_and_both_sentinels():
    criteria = build_criteria(OPTIONS)
    assert set(criteria) == {"1", "2", DONE, STUCK}
    assert criteria["1"] == "a 'Alpha report'"
    assert "link" in criteria["2"]


def test_criteria_rejects_sentinel_collision():
    with pytest.raises(ValueError):
        build_criteria([Option(id=DONE, label="sneaky")])


def test_instructions_carry_the_goal():
    text = build_instructions("open the Omega appendix")
    assert "open the Omega appendix" in text
    assert DONE in text and STUCK in text


def test_act():
    decision = apply_policy(raw_pick="2", confidence=0.9, options=OPTIONS)
    assert decision.outcome == "act"
    assert decision.pick == "2"
    assert decision.label == "a 'Omega appendix'"
    assert decision.confidence == 0.9


def test_done_and_stuck_are_abstentions():
    assert apply_policy(raw_pick=DONE, confidence=0.3, options=OPTIONS).outcome == "done"
    assert apply_policy(raw_pick=STUCK, confidence=0.3, options=OPTIONS).outcome == "stuck"


def test_unknown_id_fails_closed():
    decision = apply_policy(raw_pick="99", confidence=0.99, options=OPTIONS)
    assert decision.outcome == "error"
    assert decision.pick is None
    assert "not an offered option" in decision.reason


def test_below_floor_escalates_with_the_pick_attached():
    decision = apply_policy(raw_pick="2", confidence=0.41, options=OPTIONS, floor=0.5)
    assert decision.outcome == "escalate"
    assert decision.pick == "2"
    assert "below floor" in decision.reason


def test_floor_boundary_is_inclusive():
    assert apply_policy(raw_pick="2", confidence=0.5, options=OPTIONS, floor=0.5).outcome == "act"


def test_transport_failure_is_an_error_not_a_pick():
    decision = apply_policy(raw_pick=None, error="HTTP 503: overloaded")
    assert decision.outcome == "error"
    assert decision.pick is None
    assert "503" in (decision.error or "")


def test_missing_answer_is_an_error():
    assert apply_policy(raw_pick=None, confidence=None).outcome == "error"


def test_unknown_outcome_rejected_at_construction():
    from jev_pilot.types import Decision
    with pytest.raises(ValueError):
        Decision(outcome="click")


def test_decision_serialises_without_nones_noise():
    payload = apply_policy(raw_pick="1", confidence=0.8, options=OPTIONS).as_dict()
    assert payload["outcome"] == "act"
    assert "error" not in payload
