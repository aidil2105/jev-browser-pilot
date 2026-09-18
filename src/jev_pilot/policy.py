"""The decision policy: what a raw answer from a chooser is allowed to mean.

Kept in code, not in a prompt, because these are the rules that keep a wrong answer
from being executed:

- an answer that is not one of the offered ids is rejected (fail closed);
- `__done__` / `__stuck__` are the only abstentions, and they are never turned into
  an action;
- a pick below the confidence floor comes back as `escalate` WITH the pick attached,
  so the caller can route it to a planner or a human instead of guessing;
- a transport or API failure is `error`, never a fabricated pick. Callers must treat
  `error` as "no decision".
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

from jev_pilot.types import Decision, Option

DONE = "__done__"
STUCK = "__stuck__"
SENTINELS = (DONE, STUCK)

DEFAULT_INSTRUCTIONS = (
    "You are the decision step of a computer-use loop. The harness gives you one "
    "observation and a list of candidate actions it can execute for you.\n"
    "Goal: {goal}\n"
    "Choose exactly ONE option id as the single next step. Choose {done} if the goal "
    "is already achieved in this observation, or {stuck} if no option can make "
    "progress toward it. Never invent an option that is not in the list."
)


def build_instructions(goal: str, template: Optional[str] = None) -> str:
    return (template or DEFAULT_INSTRUCTIONS).format(goal=goal, done=DONE, stuck=STUCK)


def build_criteria(options: Sequence[Option], *, max_label: int = 120,
                   done_hint: str = "Stop: the goal is already achieved",
                   stuck_hint: str = "No option in this list can make progress toward the goal",
                   detail: bool = True) -> Dict[str, str]:
    """The full label space the chooser may answer with. Raised loudly on id collisions."""
    criteria: Dict[str, str] = {DONE: done_hint, STUCK: stuck_hint}
    for opt in options:
        if str(opt.id) in SENTINELS:
            raise ValueError(f"option id {opt.id!r} collides with a reserved sentinel")
        label = opt.label
        if detail and opt.detail:
            label = f"{label} ({opt.detail})"
        criteria[str(opt.id)] = label[:max_label]
    return criteria


def apply_policy(
    *,
    raw_pick: Optional[str],
    confidence: Optional[float] = None,
    options: Sequence[Option] = (),
    floor: float = 0.0,
    probabilities: Optional[Dict[str, float]] = None,
    provider: str = "",
    model: Optional[str] = None,
    latency_ms: int = 0,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    error: Optional[str] = None,
) -> Decision:
    """Turn one raw chooser answer into the outcome the loop is allowed to act on."""
    labels = {str(o.id): o.label for o in options}
    base = dict(confidence=confidence, probabilities=dict(probabilities or {}),
                latency_ms=latency_ms, provider=provider, model=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=cost_usd)

    if error:
        return Decision(outcome="error", reason="chooser failed", error=error, **base)

    if raw_pick is None:
        return Decision(outcome="error", reason="chooser returned no answer",
                        error="empty answer", **base)

    pick = str(raw_pick)

    if pick == DONE:
        return Decision(outcome="done", reason="model reports the goal is already achieved", **base)
    if pick == STUCK:
        return Decision(outcome="stuck", reason="model reports no option can make progress", **base)

    if labels and pick not in labels:
        return Decision(outcome="error", reason=f"answer {pick!r} is not an offered option",
                        error="unknown option id", **base)

    label = labels.get(pick)
    if confidence is not None and confidence < floor:
        return Decision(outcome="escalate", pick=pick, label=label,
                        reason=f"confidence {confidence:.2f} below floor {floor}",
                        **base)
    return Decision(outcome="act", pick=pick, label=label, reason="picked", **base)
