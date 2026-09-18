"""Data types shared by every part of the loop. Plain dataclasses, JSON-friendly."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

OUTCOMES = ("act", "done", "stuck", "escalate", "error")


@dataclass(frozen=True)
class Option:
    """One action the harness can actually execute. The chooser may only return an id."""

    id: str
    label: str
    detail: str = ""

    def as_dict(self, max_label: int = 0) -> Dict[str, str]:
        label = self.label if not max_label else self.label[:max_label]
        out = {"id": self.id, "label": label}
        if self.detail:
            out["detail"] = self.detail
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Option":
        return cls(id=str(data["id"]), label=str(data.get("label", data["id"])),
                   detail=str(data.get("detail", "")))


@dataclass
class Decision:
    """A normalized chooser answer. `outcome` is the only field callers must branch on."""

    outcome: str
    pick: Optional[str] = None
    label: Optional[str] = None
    confidence: Optional[float] = None
    probabilities: Dict[str, float] = field(default_factory=dict)
    latency_ms: int = 0
    provider: str = ""
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    reason: str = ""
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {self.outcome!r}; expected one of {OUTCOMES}")

    @property
    def has_pick(self) -> bool:
        return self.pick is not None

    def as_dict(self, probabilities: bool = True) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "outcome": self.outcome,
            "pick": self.pick,
            "label": self.label,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "reason": self.reason,
        }
        if self.error:
            out["error"] = self.error
        if probabilities and self.probabilities:
            out["probabilities"] = dict(self.probabilities)
        return out


@dataclass
class Step:
    """One observe-decide-act cycle, as recorded for the trace."""

    index: int
    goal: str
    url: Optional[str] = None
    title: Optional[str] = None
    candidates: int = 0
    matched_total: Optional[int] = None
    truncated: bool = False
    decision: Optional[Decision] = None
    action: Optional[str] = None
    verified: Optional[bool] = None
    no_progress: bool = False
    state: Optional[str] = None

    def as_dict(self, state: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "index": self.index,
            "goal": self.goal,
            "url": self.url,
            "title": self.title,
            "candidates": self.candidates,
            "matched_total": self.matched_total,
            "truncated": self.truncated,
            "action": self.action,
            "verified": self.verified,
            "no_progress": self.no_progress,
        }
        if self.decision is not None:
            out["decision"] = self.decision.as_dict()
        if state and self.state is not None:
            out["state"] = self.state
        return out


@dataclass
class Episode:
    """One goal pursued to success, failure, or the step budget."""

    goal: str
    start_url: Optional[str] = None
    steps: List[Step] = field(default_factory=list)
    reached: bool = False
    stopped: str = "budget"  # reached | done | stuck | escalate | error | budget | no_progress | blocked | dry_run
    final_url: Optional[str] = None
    checks: List[Dict[str, Any]] = field(default_factory=list)
    provider: str = ""
    model: Optional[str] = None

    # totals
    decisions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, step: Step) -> None:
        self.steps.append(step)
        if step.decision is not None:
            self.decisions += 1
            self.input_tokens += step.decision.input_tokens or 0
            self.output_tokens += step.decision.output_tokens or 0
            self.cost_usd += step.decision.cost_usd or 0.0

    @property
    def latencies(self) -> List[int]:
        return [s.decision.latency_ms for s in self.steps if s.decision is not None]

    @property
    def verified_steps(self) -> int:
        return sum(1 for s in self.steps if s.verified)

    def summary(self) -> Dict[str, Any]:
        latencies = self.latencies
        return {
            "goal": self.goal,
            "start_url": self.start_url,
            "reached": self.reached,
            "stopped": self.stopped,
            "steps": len(self.steps),
            "decisions": self.decisions,
            "final_url": self.final_url,
            "provider": self.provider,
            "model": self.model,
            "median_latency_ms": int(statistics.median(latencies)) if latencies else None,
            "min_latency_ms": min(latencies) if latencies else None,
            "max_latency_ms": max(latencies) if latencies else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 8),
            "checks": self.checks,
        }

    def as_dict(self, state: bool = False) -> Dict[str, Any]:
        out = self.summary()
        out["steps_detail"] = [s.as_dict(state=state) for s in self.steps]
        return out


def median(values: Sequence[float]) -> Optional[float]:
    return float(statistics.median(values)) if values else None
