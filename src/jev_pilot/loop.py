"""The episode runner: observe -> decide -> act -> verify, with the guardrails on.

What the loop guarantees, whatever chooser and surface you plug in:

- the candidate list is built from the observed surface, and the chooser may only
  answer with ids from that list (anything else is rejected by the policy);
- `done` and `stuck` stop the episode; `escalate` (a pick under the confidence
  floor) also stops it and hands the decision back to the caller with the pick
  attached, so a planner or a human can take it;
- the postcondition is evaluated by code, before and after every action, and it is
  the only thing that can set `reached`;
- a no-progress guard stops an episode that keeps seeing the same state;
- every step is recorded, including the exact state string if the trace asks for it.
"""

from __future__ import annotations

import hashlib
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from jev_pilot.perception import Snapshot
from jev_pilot.policy import apply_policy
from jev_pilot.safety import SafetyPolicy
from jev_pilot.serialize import SerializerOptions, build_state
from jev_pilot.surface import Surface
from jev_pilot.types import Episode, Step
from jev_pilot.verify import VerificationContext, all_passed, verify_all

StepHook = Callable[[Step, Episode], None]


def state_signature(snapshot: Snapshot) -> str:
    """A cheap fingerprint of "the world looks the same as last time"."""
    parts = [snapshot.url or "", snapshot.title or ""]
    parts.extend(f"{el.id}:{el.label()}" for el in snapshot.elements)
    return hashlib.sha1("|".join(parts).encode("utf-8", errors="replace")).hexdigest()[:12]


def verification_context(surface: Surface, snapshot: Snapshot) -> VerificationContext:
    return VerificationContext(
        url=snapshot.url or surface.url(),
        text=snapshot.text,
        probe=lambda selector: surface.probe(selector),
    )


def _outside_the_box(safety: Optional[SafetyPolicy], snapshot: Snapshot) -> bool:
    """True when the surface is no longer on a host the caller allowed.

    A redirect, a link that leaves the site, or an ad frame all move the surface
    somewhere the caller never agreed to. Failing closed here means the episode stops
    with `blocked` instead of reading (or acting on) a page outside the declared box.
    """
    if safety is None or not snapshot.url:
        return False
    return not safety.host_allowed(snapshot.url)


def run_episode(
    surface: Surface,
    chooser,
    goal: str,
    *,
    verifiers: Sequence[str] = (),
    steps: int = 4,
    floor: float = 0.0,
    serialize_opts: Optional[SerializerOptions] = None,
    safety: Optional[SafetyPolicy] = None,
    dry_run: bool = False,
    on_step: Optional[StepHook] = None,
    extra_lines: Sequence[str] = (),
    no_progress_limit: int = 2,
    timeout: Optional[float] = None,
    trace=None,
) -> Episode:
    """Run one goal to its postcondition, an abstention, the budget, or an error."""
    opts = serialize_opts or SerializerOptions()
    episode = Episode(goal=goal, start_url=getattr(surface, "start_url", None),
                      provider=getattr(chooser, "name", ""), model=getattr(chooser, "model", None))
    history: List[str] = []
    signatures: List[str] = []
    no_progress_streak = 0
    started: Optional[Snapshot] = None

    if safety is not None:
        episode.stopped = "budget"

    for index in range(1, max(1, steps) + 1):
        snapshot = surface.observe()
        if started is None:
            started = snapshot
        episode.final_url = snapshot.url

        if _outside_the_box(safety, snapshot):
            blocked = Step(index=index, goal=goal, url=snapshot.url, title=snapshot.title,
                           candidates=0, action="blocked")
            blocked.state = (f"BLOCKED: {snapshot.url} is not on an allowed host "
                             f"({', '.join(sorted(safety.allow_hosts))})")
            episode.add(blocked)
            episode.stopped = "blocked"
            if trace is not None:
                trace.step(blocked, note="outside the allowed hosts; failing closed")
            return episode

        # A postcondition that already holds means the goal is done, no model call.
        if verifiers:
            ctx = verification_context(surface, snapshot)
            episode.checks = verify_all(verifiers, ctx)
            if all_passed(episode.checks):
                episode.reached = True
                episode.stopped = "reached"
                if trace is not None:
                    trace.event("verified_before_decision", url=snapshot.url, step=index)
                return episode

        options = snapshot.options()
        step = Step(index=index, goal=goal, url=snapshot.url, title=snapshot.title,
                    candidates=len(options), matched_total=snapshot.matched_total,
                    truncated=snapshot.truncated)

        if not options:
            step.action = "none"
            step.state = build_state(options=[], url=snapshot.url, title=snapshot.title,
                                     text=snapshot.text, history=history, opts=opts)
            episode.add(step)
            episode.stopped = "error"
            if trace is not None:
                trace.step(step, note="no candidates in the observation")
            return episode

        state = build_state(options=options, url=snapshot.url, title=snapshot.title,
                            text=snapshot.text, history=history,
                            matched_total=snapshot.matched_total, extra_lines=extra_lines, opts=opts)
        step.state = state

        raw = chooser.choose(goal=goal, state=state, options=options, timeout=timeout)
        decision = apply_policy(
            raw_pick=raw.pick, confidence=raw.confidence, options=options, floor=floor,
            probabilities=raw.probabilities, provider=getattr(chooser, "name", ""),
            model=raw.model or getattr(chooser, "model", None), latency_ms=raw.latency_ms,
            input_tokens=raw.input_tokens, output_tokens=raw.output_tokens,
            cost_usd=raw.cost_usd, error=raw.error,
        )
        step.decision = decision
        episode.add(step)
        if trace is not None:
            trace.step(step)

        if decision.outcome in ("error", "done", "stuck", "escalate"):
            episode.stopped = decision.outcome
            break

        if dry_run:
            step.action = "dry_run"
            episode.stopped = "dry_run"
            if on_step is not None:
                on_step(step, episode)
            break

        if safety is not None:
            safety.check_action("click", snapshot.url)

        result = surface.act(str(decision.pick))
        step.action = f"click {result.get('option_id', decision.pick)}"
        history.append(decision.label or str(decision.pick))
        if trace is not None:
            trace.event("act", step=index, **result)

        # One observation after the action, reused for verification and the guard.
        after = surface.observe()
        episode.final_url = after.url
        if _outside_the_box(safety, after):
            step.action = f"{step.action} -> left the allowed hosts"
            episode.stopped = "blocked"
            if trace is not None:
                trace.event("blocked", step=index, url=after.url,
                            allowed=sorted(safety.allow_hosts))
            if on_step is not None:
                on_step(step, episode)
            return episode
        if verifiers:
            episode.checks = verify_all(verifiers, verification_context(surface, after))
            step.verified = all_passed(episode.checks)
            if step.verified:
                episode.reached = True
                episode.stopped = "reached"
                if on_step is not None:
                    on_step(step, episode)
                return episode

        signature = state_signature(after)
        if signatures and signature == signatures[-1]:
            no_progress_streak += 1
            step.no_progress = True
        else:
            no_progress_streak = 0
        signatures.append(signature)
        if on_step is not None:
            on_step(step, episode)
        if no_progress_streak >= no_progress_limit:
            episode.stopped = "no_progress"
            break

    # Final evaluation, so an episode that ran out of budget still reports honestly.
    if verifiers:
        final = surface.observe()
        episode.final_url = final.url
        episode.checks = verify_all(verifiers, verification_context(surface, final))
        episode.reached = all_passed(episode.checks)
        if episode.reached and episode.stopped in ("budget", "no_progress"):
            episode.stopped = "reached"
    elif not episode.steps:
        episode.stopped = "error"
    return episode
