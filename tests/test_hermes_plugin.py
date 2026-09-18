"""The Hermes plugin's contract, tested without Hermes installed.

The plugin is a thin wrapper around `jev-pilot decide`, and its whole job is to be honest: pass a
validated request through, and report a failure as a failure. These tests pin that, using the
credential-free keyword chooser for the round trip. The plugin directory is loaded as a package by
path, the way Hermes loads it from `$HERMES_HOME/plugins/`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "hermes-plugin" / "jev-decide"
PACKAGE = "jev_decide_plugin"

OPTIONS = [{"id": "100", "name": "a 'slide rule'"}, {"id": "5", "name": "a 'abacus'"}]


def load_plugin():
    """Import the plugin directory as a package, the way a plugin loader would."""
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)]
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def plugin(monkeypatch):
    """The plugin package, with the CLI set to this interpreter so no PATH games are needed."""
    monkeypatch.setenv("JEV_PILOT_BIN", f"{sys.executable} -m jev_pilot.cli")
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "src"))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    return load_plugin()


def _call(plugin, **args):
    payload = json.loads(plugin.tools.jev_decide(args))
    return payload


# --- the happy path, through the real CLI ------------------------------------------------


def test_a_real_decision_round_trips_through_the_cli(plugin):
    payload = _call(plugin,
                    goal="open the article about the slide rule",
                    state="URL: https://en.wikipedia.org/wiki/Calculator\nTITLE: Calculator",
                    options=OPTIONS,
                    provider="mock")
    assert payload["ok"] is True
    decision = payload["decision"]
    assert decision["pick"] == "100"          # the keyword chooser's deterministic answer
    assert decision["outcome"] in ("act", "escalate")
    assert decision["provider"] == "keyword"  # the chooser's own name, not the CLI's provider key
    assert isinstance(decision.get("ms"), (int, float))


def test_the_confidence_floor_is_forwarded_and_escalates_rather_than_guessing(plugin):
    payload = _call(plugin,
                    goal="open the article about the slide rule",
                    options=OPTIONS,
                    provider="mock",
                    confidence_floor=0.99)
    assert payload["ok"] is True
    decision = payload["decision"]
    assert decision["outcome"] == "escalate"
    assert decision["pick"] == "100"          # the pick is attached, not executed


# --- fail-closed: a failed decision never becomes a pick ---------------------------------


def test_a_missing_cli_is_an_error_not_a_pick(plugin, monkeypatch):
    monkeypatch.setenv("JEV_PILOT_BIN", str(ROOT / "does-not-exist" / "jev-pilot"))
    payload = _call(plugin, goal="do the thing", options=OPTIONS)
    assert payload["ok"] is False
    assert payload["outcome"] == "error"
    assert payload["pick"] is None
    assert "JEV_PILOT_BIN" in payload["reason"]


def test_a_cli_that_fails_to_answer_is_an_error_not_a_pick(plugin, monkeypatch):
    monkeypatch.setenv("JEV_PILOT_BIN", f"{sys.executable} -c pass")  # exits 0, prints nothing
    payload = _call(plugin, goal="do the thing", options=OPTIONS)
    assert payload["ok"] is False
    assert payload["pick"] is None
    assert "nothing on stdout" in payload["reason"]


def test_non_json_output_is_an_error(plugin, monkeypatch):
    monkeypatch.setenv("JEV_PILOT_BIN", f"{sys.executable} -c \"print('not json')\"")
    payload = _call(plugin, goal="do the thing", options=OPTIONS)
    assert payload["ok"] is False
    assert "did not return JSON" in payload["reason"]


# --- request validation ------------------------------------------------------------------


@pytest.mark.parametrize("args, fragment", [
    ({"options": OPTIONS}, "goal is required"),
    ({"goal": "g"}, "non-empty array"),
    ({"goal": "g", "options": []}, "non-empty array"),
    ({"goal": "g", "options": [{"id": "1"}]}, "needs both id and name"),
    ({"goal": "g", "options": [{"name": "no id"}]}, "needs both id and name"),
    ({"goal": "g", "options": [{"id": "__done__", "name": "x"}]}, "reserved sentinel"),
    ({"goal": "g", "options": [{"id": "1", "name": "a"}, {"id": "1", "name": "b"}]}, "duplicate"),
    ({"goal": "g", "options": ["not an object"]}, "not an object"),
])
def test_bad_requests_are_rejected_with_a_reason(plugin, args, fragment):
    payload = _call(plugin, **args)
    assert payload["ok"] is False
    assert payload["pick"] is None
    assert fragment in payload["reason"]


def test_unknown_option_keys_are_dropped_rather_than_forwarded(plugin):
    payload = _call(plugin,
                    goal="open the article about the slide rule",
                    provider="mock",
                    options=[{"id": "100", "name": "a 'slide rule'", "shell": "rm -rf /"},
                             {"id": "5", "name": "a 'abacus'"}])
    assert payload["ok"] is True
    assert payload["decision"]["pick"] == "100"


# --- registration and availability -------------------------------------------------------


class FakeCtx:
    def __init__(self):
        self.tools = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def test_register_wires_the_tool_with_a_check_fn(plugin):
    ctx = FakeCtx()
    plugin.register(ctx)
    assert set(ctx.tools) == {"jev_decide"}
    entry = ctx.tools["jev_decide"]
    assert entry["toolset"] == "jev_decide"
    assert callable(entry["handler"]) and callable(entry["check_fn"])
    assert entry["schema"]["name"] == "jev_decide"
    assert entry["schema"]["parameters"]["required"] == ["goal", "options"]


def test_the_tool_hides_itself_when_the_cli_is_missing(plugin, monkeypatch):
    monkeypatch.setenv("JEV_PILOT_BIN", str(ROOT / "does-not-exist" / "jev-pilot"))
    assert plugin.tools.available() is False
    monkeypatch.setenv("JEV_PILOT_BIN", f"{sys.executable} -m jev_pilot.cli")
    assert plugin.tools.available() is True


def test_the_schema_is_a_wellformed_object_schema(plugin):
    schema = plugin.schemas.JEV_DECIDE
    params = schema["parameters"]
    assert params["type"] == "object"
    assert params["required"], "a tool with no required arguments is a tool the model will misuse"
    for name, spec in params["properties"].items():
        assert "type" in spec, f"{name} has no type"
        assert spec.get("description"), f"{name} has no description"


# --- the environment handoff -------------------------------------------------------------


def test_the_api_key_is_read_from_the_hermes_env_file_without_mutating_the_environment(
        plugin, monkeypatch, tmp_path):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    (hermes_home / ".env").write_text(
        "# comment\nTYPESAFE_API_KEY=not-a-real-key\nOTHER=1\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    child_env = plugin.tools._env_with_key()
    assert child_env["TYPESAFE_API_KEY"] == "not-a-real-key"
    assert "TYPESAFE_API_KEY" not in os.environ, "the parent environment must not be modified"


def test_an_absent_env_file_is_not_an_error(plugin, monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "nowhere"))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert "TYPESAFE_API_KEY" not in plugin.tools._env_with_key()
