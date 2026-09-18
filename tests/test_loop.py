import pytest

from jev_pilot.loop import run_episode, state_signature
from jev_pilot.perception import Element, Snapshot
from jev_pilot.providers.base import ScriptedChooser
from jev_pilot.surface import ScriptedSurface

INDEX = Snapshot(url="https://example.test/index.html", title="Index",
                 text="Alpha report and Omega appendix are listed.",
                 elements=[Element(id="1", role="a", name="Alpha report"),
                           Element(id="2", role="a", name="Omega appendix")],
                 matched_total=2)
OMEGA = Snapshot(url="https://example.test/omega.html", title="Omega",
                 text="GOAL REACHED: omega appendix.",
                 elements=[Element(id="1", role="a", name="Back to the index")],
                 matched_total=1)
OMEGA_REACHED = ["url-contains:omega.html"]


def test_happy_path_reaches_the_postcondition():
    chooser = ScriptedChooser(["2"])
    surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
    episode = run_episode(surface, chooser, "open the Omega appendix",
                          verifiers=OMEGA_REACHED, steps=3)
    assert episode.reached is True
    assert episode.stopped == "reached"
    assert len(episode.steps) == 1
    assert surface.actions == ["2"]
    assert episode.steps[0].verified is True
    assert chooser.calls == 1


def test_verification_before_the_decision_avoids_a_model_call():
    chooser = ScriptedChooser(["1"])
    surface = ScriptedSurface(snapshots=[OMEGA])
    episode = run_episode(surface, chooser, "open the Omega appendix",
                          verifiers=OMEGA_REACHED, steps=3)
    assert episode.reached is True
    assert chooser.calls == 0
    assert episode.steps == []


def test_escalation_stops_the_episode_and_does_not_act():
    chooser = ScriptedChooser([("2", 0.2)])
    surface = ScriptedSurface(snapshots=[INDEX])
    episode = run_episode(surface, chooser, "open the Omega appendix",
                          verifiers=OMEGA_REACHED, steps=3, floor=0.6)
    assert episode.stopped == "escalate"
    assert episode.reached is False
    assert surface.actions == []
    assert episode.steps[0].decision.pick == "2"
    assert episode.steps[0].decision.confidence == 0.2


def test_done_and_stuck_stop_without_acting():
    for pick, expected in (("__done__", "done"), ("__stuck__", "stuck")):
        surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
        episode = run_episode(surface, ScriptedChooser([pick]), "goal", steps=3)
        assert episode.stopped == expected
        assert surface.actions == []


def test_transport_error_stops_the_episode():
    surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
    episode = run_episode(surface, ScriptedChooser([], fail_with="HTTP 503"), "goal", steps=3)
    assert episode.stopped == "error"
    assert surface.actions == []
    assert "503" in (episode.steps[0].decision.error or "")


def test_dry_run_decides_but_does_not_act():
    surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
    episode = run_episode(surface, ScriptedChooser(["2"]), "goal", steps=3, dry_run=True)
    assert episode.stopped == "dry_run"
    assert surface.actions == []
    assert episode.steps[0].decision.outcome == "act"


def test_empty_candidate_list_is_an_error_step():
    surface = ScriptedSurface(snapshots=[Snapshot(url="https://example.test/", elements=[])])
    episode = run_episode(surface, ScriptedChooser(["1"]), "goal", steps=2)
    assert episode.stopped == "error"
    assert len(episode.steps) == 1
    assert episode.steps[0].action == "none"


def test_no_progress_guard_stops_a_loop_that_repeats_itself():
    chooser = ScriptedChooser(["2"])
    surface = ScriptedSurface(snapshots=[INDEX])
    episode = run_episode(surface, chooser, "goal", steps=6)
    assert episode.stopped == "no_progress"
    assert len(episode.steps) == 3
    assert episode.steps[-1].no_progress is True


def test_step_records_the_exact_state_sent():
    surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
    episode = run_episode(surface, ScriptedChooser(["2"]), "open the Omega appendix",
                          verifiers=OMEGA_REACHED, steps=2)
    state = episode.steps[0].state
    assert "CANDIDATE ACTIONS" in state
    assert "[2] a 'Omega appendix'" in state
    assert "ACTIONS ALREADY TAKEN THIS EPISODE: (none)" in state


def test_episode_summary_counts_tokens_and_cost():
    chooser = ScriptedChooser(["2"], tokens_per_call=1500, cost_per_call=0.00006)
    surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
    episode = run_episode(surface, chooser, "goal", verifiers=OMEGA_REACHED, steps=2)
    summary = episode.summary()
    assert summary["decisions"] == 1
    assert summary["input_tokens"] == 1500
    assert summary["cost_usd"] == pytest.approx(0.00006)
    assert summary["median_latency_ms"] is not None


def test_state_signature_changes_with_the_page():
    assert state_signature(INDEX) != state_signature(OMEGA)
    assert state_signature(INDEX) == state_signature(INDEX)


def test_step_budget_is_respected():
    chooser = ScriptedChooser(["1", "2"])
    surface = ScriptedSurface(snapshots=[INDEX, Snapshot(
        url="https://example.test/other.html", title="Other",
        elements=[Element(id="1", role="a", name="Alpha report")])])
    episode = run_episode(surface, chooser, "goal", verifiers=["url-contains:never"], steps=1)
    assert len(episode.steps) == 1
    assert episode.reached is False


FOREIGN = Snapshot(url="https://elsewhere.test/page.html", title="Elsewhere",
                   text="A page outside the declared hosts.",
                   elements=[Element(id="1", role="a", name="Something else")])


def test_leaving_the_allowed_hosts_fails_closed_even_when_the_check_would_pass():
    from jev_pilot.safety import SafetyPolicy

    safety = SafetyPolicy.for_hosts(["example.test"])
    surface = ScriptedSurface(snapshots=[INDEX, FOREIGN])
    episode = run_episode(surface, ScriptedChooser(["2"]), "goal",
                          verifiers=["url-contains:elsewhere.test"], steps=3, safety=safety)
    assert surface.actions == ["2"]  # the click on the allowed host ran
    assert episode.stopped == "blocked"
    assert episode.reached is False  # the block outranks a postcondition on a foreign page
    assert episode.steps[-1].action.endswith("left the allowed hosts")


def test_starting_outside_the_allowed_hosts_never_calls_the_chooser():
    from jev_pilot.safety import SafetyPolicy

    safety = SafetyPolicy.for_hosts(["other.test"])
    chooser = ScriptedChooser(["1"])
    surface = ScriptedSurface(snapshots=[INDEX, OMEGA])
    episode = run_episode(surface, chooser, "goal", steps=3, safety=safety)
    assert episode.stopped == "blocked"
    assert chooser.calls == 0
    assert "not on an allowed host" in (episode.steps[0].state or "")
