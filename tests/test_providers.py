import io
import json
import urllib.error

import pytest

from jev_pilot.providers import build_chooser
from jev_pilot.providers.base import KeywordChooser, ProviderUnavailable, RawAnswer, ScriptedChooser
from jev_pilot.providers.openai_compat import OpenAIChatChooser
from jev_pilot.types import Option

OPTIONS = [Option(id="1", label="a 'Alpha report'"),
           Option(id="2", label="a 'Omega appendix'"),
           Option(id="3", label="button 'Recalculate'")]

STATE = "URL: https://example.test/index.html\nCANDIDATE ACTIONS:\n[1] a 'Alpha report'"


# ---------------------------------------------------------------- scripted
def test_scripted_chooser_repeats_its_last_answer():
    chooser = ScriptedChooser(["a", "b"])
    picks = [chooser.choose(goal="g", state="s", options=OPTIONS).pick for _ in range(4)]
    assert picks == ["a", "b", "b", "b"]


def test_scripted_chooser_passes_confidence_and_cost():
    chooser = ScriptedChooser([("2", 0.75)], tokens_per_call=900, cost_per_call=0.00004)
    answer = chooser.choose(goal="g", state="s", options=OPTIONS)
    assert answer.pick == "2" and answer.confidence == 0.75
    assert answer.input_tokens == 900 and answer.cost_usd == 0.00004


def test_scripted_chooser_can_fail():
    answer = ScriptedChooser([], fail_with="connection reset").choose(goal="g", state="s", options=OPTIONS)
    assert answer.error == "connection reset" and answer.pick is None


# ---------------------------------------------------------------- keyword
def test_keyword_chooser_prefers_the_phrase_match():
    chooser = KeywordChooser()
    answer = chooser.choose(goal="open the Omega appendix", state=STATE, options=OPTIONS)
    assert answer.pick == "2"
    assert answer.confidence >= 0.5


def test_keyword_chooser_abstains_when_nothing_overlaps():
    answer = KeywordChooser().choose(goal="reticulate splines", state=STATE, options=OPTIONS)
    assert answer.pick == "__stuck__"


def test_keyword_chooser_without_options_is_an_error():
    answer = KeywordChooser().choose(goal="anything", state=STATE, options=[])
    assert answer.error == "no options"


# ---------------------------------------------------------------- registry
def test_registry_rejects_an_unknown_provider():
    with pytest.raises(ProviderUnavailable):
        build_chooser("gpt-that-does-not-exist")


def test_registry_builds_the_credential_free_chooser():
    assert build_chooser("mock").name == "keyword"


# ---------------------------------------------------------------- openai-compatible
class FakeTransport:
    def __init__(self, body: bytes):
        self.body = body
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return self.body


def chooser_with(content: str, **kwargs):
    transport = FakeTransport(content.encode())
    chooser = OpenAIChatChooser(model="some-model", base_url="http://127.0.0.1:9/v1",
                                transport=transport, **kwargs)
    return chooser, transport


def test_openai_parses_a_plain_answer():
    chooser, _ = chooser_with('{"choices":[{"message":{"content":"{\\"id\\": \\"2\\"}"}}]}')
    answer = chooser.choose(goal="open the omega appendix", state=STATE, options=OPTIONS)
    assert answer.pick == "2"
    assert answer.error is None


def test_openai_parses_a_data_envelope():
    chooser, _ = chooser_with('{"data":{"choices":[{"message":{"content":"{\\"id\\": \\"1\\"}"}}]},'
                              '"success":true}')
    assert chooser.choose(goal="g", state=STATE, options=OPTIONS).pick == "1"


def test_openai_survives_concatenated_json_bodies():
    body = '{"object":"chat.completion","choices":[{"message":{"content":"{\\"id\\": \\"3\\"}"}}]}\n{"extra":1}'
    chooser, _ = chooser_with(body)
    assert chooser.choose(goal="g", state=STATE, options=OPTIONS).pick == "3"


def test_openai_falls_back_to_a_bare_id_in_prose():
    chooser, _ = chooser_with('{"choices":[{"message":{"content":"I would pick 2 here."}}]}')
    assert chooser.choose(goal="g", state=STATE, options=OPTIONS).pick == "2"


def test_openai_reports_a_prose_answer_without_an_id():
    chooser, _ = chooser_with('{"choices":[{"message":{"content":"I cannot help with that."}}]}')
    answer = chooser.choose(goal="g", state=STATE, options=OPTIONS)
    assert answer.pick is None
    assert "no id in the answer" in answer.error


def test_openai_surfaces_the_http_body():
    def failing(request, timeout):
        raise urllib.error.HTTPError("http://x", 503,
                                     "Service Unavailable", None,
                                     io.BytesIO(b'{"error":"insufficient_credits"}'))
    chooser = OpenAIChatChooser(model="m", base_url="http://127.0.0.1:9/v1", transport=failing)
    answer = chooser.choose(goal="g", state=STATE, options=OPTIONS)
    assert "HTTP 503" in answer.error and "insufficient_credits" in answer.error


def test_openai_request_keeps_the_large_token_cap_and_the_model():
    chooser, transport = chooser_with('{"choices":[{"message":{"content":"{\\"id\\": \\"1\\"}"}}]}')
    chooser.choose(goal="goal text", state=STATE, options=OPTIONS)
    request, timeout = transport.requests[0]
    payload = json.loads(request.data.decode())
    assert payload["model"] == "some-model"
    assert payload["max_tokens"] == 800
    prompt = payload["messages"][0]["content"]
    assert "2: a 'Omega appendix'" in prompt
    assert "__stuck__" in prompt and "goal text" in prompt


def test_openai_counts_cost_when_prices_are_known():
    body = ('{"choices":[{"message":{"content":"{\\"id\\": \\"1\\"}"}}],'
            '"usage":{"prompt_tokens":2000,"completion_tokens":100}}')
    chooser, _ = chooser_with(body, input_price_per_mtok=1.0, output_price_per_mtok=2.0)
    answer = chooser.choose(goal="g", state=STATE, options=OPTIONS)
    assert answer.cost_usd == pytest.approx(0.002 + 0.0002)


def test_openai_needs_a_key_for_a_remote_endpoint():
    with pytest.raises(ProviderUnavailable):
        OpenAIChatChooser(model="m", base_url="https://api.example.com/v1", api_key="")


def test_openai_local_endpoint_needs_no_key():
    chooser = OpenAIChatChooser(model="llama3.1", base_url="http://localhost:11434/v1",
                                api_key="")
    assert chooser.describe().startswith("openai model=llama3.1")


def test_openai_rejects_sentinel_collisions_before_calling_out():
    chooser, transport = chooser_with("{}")
    answer = chooser.choose(goal="g", state=STATE,
                            options=[Option(id="__done__", label="sneaky")])
    assert answer.error and "sentinel" in answer.error
    assert transport.requests == []
