"""The Chooser interface: what a decision backend must implement.

A chooser sees only three things: the serialized state, the goal, and the candidate
table with its ids. It returns a `RawAnswer`, which is *not* permission to act: the
loop passes it through `jev_pilot.policy.apply_policy`, which is where the
confidence floor, the sentinels and the fail-closed rules live.

Keeping the raw answer separate from the policy is what lets you swap the model
(Jev, any OpenAI-compatible endpoint, a scripted fake) without touching a single
line of the loop, the safety rails or the verification.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from jev_pilot.types import Option


class ProviderUnavailable(RuntimeError):
    """The chooser cannot run here: no credentials, no endpoint, missing dependency."""


@dataclass
class RawAnswer:
    pick: Optional[str] = None
    confidence: Optional[float] = None
    probabilities: Dict[str, float] = field(default_factory=dict)
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: int = 0
    error: Optional[str] = None
    raw: Optional[str] = None


class Chooser:
    """Base class. Subclasses implement `choose` and set `name`."""

    name = "chooser"
    model: Optional[str] = None

    def choose(
        self,
        *,
        goal: str,
        state: str,
        options: Sequence[Option],
        timeout: Optional[float] = None,
    ) -> RawAnswer:  # pragma: no cover - interface
        raise NotImplementedError

    # ---- helpers for subclasses ---------------------------------------
    @staticmethod
    def timer() -> float:
        return time.perf_counter()

    @staticmethod
    def elapsed_ms(started: float) -> int:
        return int(round((time.perf_counter() - started) * 1000))

    def describe(self) -> str:
        model = f" model={self.model}" if self.model else ""
        return f"{self.name}{model}"


class ScriptedChooser(Chooser):
    """Returns a fixed sequence of answers. The test and CI workhorse."""

    name = "scripted"

    def __init__(self, answers, *, model: str = "scripted-1", cost_per_call: Optional[float] = None,
                 tokens_per_call: int = 1000, fail_with: Optional[str] = None):
        self.answers = list(answers)
        self.model = model
        self.cost_per_call = cost_per_call
        self.tokens_per_call = tokens_per_call
        self.fail_with = fail_with
        self.calls = 0

    def choose(self, *, goal, state, options, timeout=None):
        started = self.timer()
        if self.fail_with:
            self.calls += 1
            return RawAnswer(error=self.fail_with, latency_ms=self.elapsed_ms(started), model=self.model)
        if not self.answers:
            raise AssertionError("scripted chooser ran out of answers")
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        self.calls += 1
        if isinstance(answer, RawAnswer):
            return answer
        pick, confidence = answer if isinstance(answer, tuple) else (answer, None)
        return RawAnswer(
            pick=str(pick) if pick is not None else None,
            confidence=confidence,
            model=self.model,
            input_tokens=self.tokens_per_call,
            cost_usd=self.cost_per_call,
            latency_ms=self.elapsed_ms(started),
        )


class KeywordChooser(Chooser):
    """A deterministic, credential-free chooser: the option whose label shares most
    words with the goal wins, with a confidence derived from the overlap.

    It exists so the library, the CLI and the tests are usable with no model at all
    (docs, demos, CI, offline development). It is deliberately naive: it is not a
    baseline to beat, it is a stand-in for one.
    """

    name = "keyword"

    def __init__(self, *, model: str = "keyword-overlap-1", done_threshold: float = 0.0,
                 stuck_below: float = 0.0):
        self.model = model
        self.done_threshold = done_threshold
        self.stuck_below = stuck_below

    @staticmethod
    def _tokens(text: str):
        import re
        return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}

    def choose(self, *, goal, state, options, timeout=None):
        started = self.timer()
        goal_tokens = self._tokens(goal)
        scored = []
        for opt in options:
            label_tokens = self._tokens(opt.label)
            overlap = len(goal_tokens & label_tokens)
            # prefer a full phrase hit, which is what a person would click
            phrase = 2 if opt.label.lower().strip("'\" ") in goal.lower() else 0
            scored.append((overlap + phrase, overlap, opt))
        if not scored:
            return RawAnswer(pick=None, error="no options", latency_ms=self.elapsed_ms(started))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, best_overlap, best = scored[0]
        if best_score <= 0:
            return RawAnswer(pick="__stuck__", confidence=0.5, model=self.model,
                             latency_ms=self.elapsed_ms(started))
        confidence = min(0.99, 0.5 + 0.1 * best_score + 0.05 * best_overlap)
        return RawAnswer(pick=str(best.id), confidence=round(confidence, 2), model=self.model,
                         latency_ms=self.elapsed_ms(started), probabilities={str(best.id): confidence})
