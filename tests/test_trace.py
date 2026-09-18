import json

from jev_pilot.loop import run_episode
from jev_pilot.perception import Element, Snapshot
from jev_pilot.providers.base import ScriptedChooser
from jev_pilot.surface import ScriptedSurface
from jev_pilot.trace import TraceRecorder, load_trace, summarize, write_report

INDEX = Snapshot(url="https://example.test/index.html", title="Index",
                 text="Omega appendix is listed.",
                 elements=[Element(id="2", role="a", name="Omega appendix")])
OMEGA = Snapshot(url="https://example.test/omega.html", title="Omega",
                 text="GOAL REACHED", elements=[])


def make_episode(trace):
    surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
    episode = run_episode(surface, ScriptedChooser(["2"]), "open the Omega appendix",
                          verifiers=["url-contains:omega.html"], steps=2, trace=trace)
    trace.episode(episode)
    return episode


def test_recorder_writes_jsonl_and_loads_back(tmp_path):
    path = tmp_path / "trace.jsonl"
    trace = TraceRecorder(str(path))
    make_episode(trace)
    records = load_trace(str(path))
    kinds = [r["kind"] for r in records]
    assert kinds == ["step", "act", "episode"]
    assert records[0]["index"] == 1
    assert records[0]["state"].startswith("URL:")


def test_verbatim_state_can_be_turned_off(tmp_path):
    path = tmp_path / "trace.jsonl"
    trace = TraceRecorder(str(path), verbatim_state=False)
    make_episode(trace)
    step = [r for r in load_trace(str(path)) if r["kind"] == "step"][0]
    assert "state" not in step


def test_summary_counts_episodes_steps_and_outcomes(tmp_path):
    path = tmp_path / "trace.jsonl"
    trace = TraceRecorder(str(path))
    make_episode(trace)
    stats = summarize(load_trace(str(path)))
    assert stats["episodes"] == 1
    assert stats["steps"] == 1
    assert stats["reached"] == 1
    assert stats["outcomes"] == {"act": 1}
    assert stats["median_latency_ms"] is not None


def test_report_is_a_self_contained_page(tmp_path):
    path = tmp_path / "trace.jsonl"
    trace = TraceRecorder(str(path))
    make_episode(trace)
    out = write_report(str(path), str(tmp_path / "report.html"), title="selftest trace")
    html = out.read_text(encoding="utf-8")
    assert out.exists()
    assert "<!doctype html>" in html
    assert "selftest trace" in html
    assert "open the Omega appendix" in html
    assert "Postconditions" in html
    assert "url-contains:omega.html" in html
    assert "reached" in html
    assert "http://" not in html.replace("https://example.test", "")  # no external assets


def test_recorder_without_a_path_keeps_records_in_memory():
    trace = TraceRecorder()
    make_episode(trace)
    assert [r["kind"] for r in trace.records] == ["step", "act", "episode"]
    assert json.dumps(trace.records[0])  # JSON-serializable
