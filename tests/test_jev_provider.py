"""Jev provider tests. The SDK is replaced by a fake client, so nothing is charged."""

from types import SimpleNamespace

import pytest

pytest.importorskip("typesafe_sdk", reason="install the 'jev' extra to run these")

from jev_pilot.providers.base import ProviderUnavailable  # noqa: E402
from jev_pilot.providers.jev import JevChooser  # noqa: E402
from jev_pilot.types import Option  # noqa: E402

OPTIONS = [Option(id="30", label="Button 'Five'"),
           Option(id="23", label="Button 'Plus'")]
STATE = "DISPLAY: 'Display is 0'\n[30] Button 'Five'\n[23] Button 'Plus'"


class FakeResponse:
    def __init__(self, choice, confidence, probabilities, tokens):
        self.answers = {"next_step": SimpleNamespace(choice=choice, confidence=confidence,
                                                     probabilities=probabilities)}
        self.usage = SimpleNamespace(input_tokens=tokens, output_tokens=0)
        self.model = "jev-1.13.0"


class FakeClient:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def system_one(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return self.response


def test_answer_is_mapped_with_cost():
    client = FakeClient(FakeResponse("30", 0.97, {"30": 0.97, "23": 0.03}, 2000))
    chooser = JevChooser(client=client)
    answer = chooser.choose(goal="compute 5 + 3", state=STATE, options=OPTIONS)
    assert answer.pick == "30"
    assert answer.confidence == 0.97
    assert answer.probabilities["23"] == 0.03
    assert answer.model == "jev-1.13.0"
    assert answer.cost_usd == pytest.approx(2000 * 0.042 / 1_000_000)
    assert answer.error is None


def test_the_question_carries_the_goal_and_the_full_label_space():
    client = FakeClient(FakeResponse("30", 0.9, {}, 1000))
    JevChooser(client=client).choose(goal="compute 5 + 3", state=STATE, options=OPTIONS)
    question = client.calls[0]["questions"]["next_step"]
    assert "compute 5 + 3" in question.instructions
    assert set(question.criteria) == {"30", "23", "__done__", "__stuck__"}
    assert client.calls[0]["state"] == STATE


def test_timeout_is_only_sent_when_requested():
    client = FakeClient(FakeResponse("30", 0.9, {}, 1000))
    JevChooser(client=client).choose(goal="g", state=STATE, options=OPTIONS)
    assert "timeout" not in client.calls[0]
    JevChooser(client=client).choose(goal="g", state=STATE, options=OPTIONS, timeout=7.5)
    assert client.calls[1]["timeout"] == 7.5


def test_transport_failure_becomes_an_error_not_an_exception():
    client = FakeClient(raises=RuntimeError("connection reset"))
    answer = JevChooser(client=client).choose(goal="g", state=STATE, options=OPTIONS)
    assert answer.pick is None
    assert "RuntimeError" in answer.error and "connection reset" in answer.error


def test_sentinel_collision_is_rejected_before_calling_out():
    client = FakeClient(FakeResponse("30", 0.9, {}, 1000))
    answer = JevChooser(client=client).choose(
        goal="g", state=STATE, options=[Option(id="__done__", label="sneaky")])
    assert answer.error and "sentinel" in answer.error
    assert client.calls == []


def test_missing_key_and_missing_client_is_unavailable(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ProviderUnavailable):
        JevChooser()


def test_env_key_is_accepted(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "not-a-real-key")
    chooser = JevChooser(client=FakeClient(FakeResponse("30", 0.9, {}, 10)))
    assert chooser.describe() == "jev model=jev-latest"


def test_custom_price_is_honoured():
    client = FakeClient(FakeResponse("30", 0.9, {}, 1_000_000))
    chooser = JevChooser(client=client, price_per_mtok=1.0)
    answer = chooser.choose(goal="g", state=STATE, options=OPTIONS)
    assert answer.cost_usd == pytest.approx(1.0)
