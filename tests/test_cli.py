"""CLI contract tests: real subprocesses, real exit codes, no credentials, no network."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(*args, env_extra=None, stdin=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("TYPESAFE_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-m", "jev_pilot.cli", *args],
                          capture_output=True, text=True, env=env, cwd=str(ROOT),
                          input=stdin, timeout=120)


def test_version():
    result = run_cli("version")
    assert result.returncode == 0
    assert "jev-browser-pilot" in result.stdout


def test_selftest_passes_offline():
    result = run_cli("selftest")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "selftest: PASS" in result.stdout
    assert "actions=['2']" in result.stdout


def test_decide_reads_json_from_a_file(tmp_path):
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "goal": "open the Omega appendix",
        "state": "URL: https://example.test/index.html",
        "options": [{"id": "1", "label": "a 'Alpha report'"},
                    {"id": "2", "label": "a 'Omega appendix'"}],
    }), encoding="utf-8")
    result = run_cli("decide", "--provider", "mock", "--file", str(request))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "act"
    assert payload["decision"] == "act"  # compatibility alias
    assert payload["pick"] == "2"
    assert payload["ms"] == payload["latency_ms"]


def test_decide_on_stdin_with_no_options_is_an_error_exit(tmp_path):
    request = json.dumps({"goal": "anything", "state": "state", "options": []})
    result = run_cli("decide", "--provider", "mock", stdin=request)
    assert result.returncode == 2  # a decision backend failure is a hard error, not "unreached"
    assert json.loads(result.stdout)["outcome"] == "error"


def test_decide_rejects_a_malformed_request():
    result = run_cli("decide", "--provider", "mock", stdin="{not json")
    assert result.returncode == 2
    assert "not valid JSON" in result.stderr


def test_decide_without_a_key_is_a_hard_error():
    result = run_cli("decide", "--provider", "openai", "--model", "gpt-x",
                     "--base-url", "https://api.example.com/v1", stdin="{}")
    assert result.returncode == 2
    assert "provider unavailable" in result.stderr


def test_bench_on_the_shipped_fixture():
    result = run_cli("bench", "--fixtures", str(FIXTURES / "calc-frozen.json"),
                     "--chooser", "mock")
    assert result.returncode == 0, result.stderr
    assert "| chooser | correct |" in result.stdout
    assert "calc-start" in result.stdout


def test_bench_writes_json_and_markdown(tmp_path):
    out = tmp_path / "bench.json"
    md = tmp_path / "bench.md"
    result = run_cli("bench", "--fixtures", str(FIXTURES / "calc-frozen.json"),
                     "--chooser", "mock", "--out", str(out), "--markdown", str(md))
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["cases"] == 4
    assert md.read_text(encoding="utf-8").startswith("| chooser |")


def test_bench_artifacts_survive_a_closed_pipe(tmp_path):
    """Regression: piping into head closed stdout, the process died while printing, and the
    --out/--markdown files were never written at all."""
    out = tmp_path / "bench.json"
    md = tmp_path / "bench.md"
    proc = subprocess.Popen(
        [sys.executable, "-m", "jev_pilot.cli", "bench",
         "--fixtures", str(FIXTURES / "calc-frozen.json"), "--chooser", "mock",
         "--out", str(out), "--markdown", str(md)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert proc.stdout is not None
    proc.stdout.readline()   # read one line, then slam the pipe shut
    proc.stdout.close()
    stderr = proc.stderr.read() if proc.stderr else ""
    if proc.stderr:
        proc.stderr.close()
    proc.wait(timeout=120)
    returncode = proc.returncode

    assert out.exists() and md.exists(), f"artifacts missing; stderr={stderr[:300]}"
    assert json.loads(out.read_text(encoding="utf-8"))["cases"] == 4
    assert "Traceback" not in stderr  # a closed pipe is not an error
    assert returncode == 0, f"exit={returncode} stderr={stderr[:300]}"


def test_endpoint_flags_are_not_handed_to_the_jev_chooser(monkeypatch):
    """Regression: --api-key-env (documented for the OpenAI path) leaked into the Jev chooser, so
    it authenticated with the wrong key and every call returned no answer."""
    import os
    from argparse import Namespace

    import pytest

    from jev_pilot.cli import _chooser_kwargs, _parse_chooser_specs
    from jev_pilot.providers import ProviderUnavailable

    os.environ["SOME_OTHER_KEY"] = "not-a-typesafe-key"
    args = Namespace(provider="jev", model=None, base_url="http://127.0.0.1:9/v1",
                     api_key_env="SOME_OTHER_KEY", max_tokens=64, input_price=1.0,
                     output_price=1.0)
    assert _chooser_kwargs(args) == {}

    # with no Typesafe key anywhere, the Jev chooser refuses rather than borrowing another
    # service's key
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ProviderUnavailable):
        _parse_chooser_specs(["jev"], args)

    # with one set, that is the key it uses
    monkeypatch.setenv("TYPESAFE_API_KEY", "the-typesafe-one")
    assert _parse_chooser_specs(["jev"], args)["jev"].api_key == "the-typesafe-one"

    openai_args = Namespace(provider="openai", model="m", base_url="http://127.0.0.1:9/v1",
                            api_key_env="SOME_OTHER_KEY", max_tokens=64, input_price=None,
                            output_price=None)
    assert _chooser_kwargs(openai_args)["api_key"] == "not-a-typesafe-key"


def test_bench_passes_endpoint_flags_to_the_openai_chooser():
    """Regression: --base-url/--api-key-env were ignored by bench, so the openai chooser
    could not be built there at all. Port 9 refuses the connection, which is enough to
    prove the chooser was constructed and called."""
    result = run_cli("bench", "--fixtures", str(FIXTURES / "calc-frozen.json"),
                     "--chooser", "openai:local-model",
                     "--base-url", "http://127.0.0.1:9/v1",
                     "--api-key-env", "JEV_PILOT_TEST_KEY",
                     env_extra={"JEV_PILOT_TEST_KEY": "not-a-real-key"})
    assert result.returncode == 0, result.stderr
    assert "openai:local-model" in result.stdout
    assert "no answer" in result.stderr  # every call failed, and the note says so


def test_bench_reports_a_missing_key_env_variable():
    result = run_cli("bench", "--fixtures", str(FIXTURES / "calc-frozen.json"),
                     "--chooser", "openai:local-model",
                     "--base-url", "https://api.example.com/v1",
                     "--api-key-env", "DEFINITELY_NOT_SET_ANYWHERE")
    assert result.returncode == 2
    assert "DEFINITELY_NOT_SET_ANYWHERE is not set" in result.stderr


def test_report_renders_from_a_trace(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps({
        "kind": "episode", "goal": "open the Omega appendix", "reached": True,
        "stopped": "reached", "steps": 1, "provider": "mock", "model": "m",
        "median_latency_ms": 12, "cost_usd": 0.0,
        "checks": [{"spec": "url-contains:omega.html", "passed": True, "detail": "ok"}],
    }) + "\n", encoding="utf-8")
    out = tmp_path / "report.html"
    result = run_cli("report", "--trace", str(trace), "--out", str(out))
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    assert "Episode 1" in html and "open the Omega appendix" in html


def test_run_without_a_goal_is_a_hard_error():
    result = run_cli("run", "--start", "https://example.test/")
    assert result.returncode == 2
    assert "nothing to do" in result.stderr


def test_run_refuses_a_goal_with_no_allowed_host():
    result = run_cli("run", "--start", "about:blank", "--goal", "do something",
                     "--provider", "mock")
    assert result.returncode == 2
    assert "safety" in result.stderr.lower()


@pytest.mark.parametrize("command", ["decide", "run", "bench", "report", "selftest"])
def test_help_works_for_every_subcommand(command):
    result = run_cli(command, "--help")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
