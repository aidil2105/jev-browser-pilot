"""Benchmark harness: freeze one observation, put every chooser on identical input.

The comparison that matters for a decision layer is not "which model is smarter" but
"on this state, how often is the pick right, how long does it take, does it answer at
all, and what does it cost". Freezing the state removes the perceptual variance that
otherwise dominates a live comparison, and every fixture records where it came from.

Fixture file format (JSON):

    {"cases": [
      {"name": "start",
       "category": "calculator",
       "goal": "compute 5 + 3",
       "state": "URL: ...\\nCANDIDATE ACTIONS ...",
       "options": [{"id": "30", "label": "Button 'Five'"}],
       "expect": "Button 'Five'",       // a label, or "__done__" / "__stuck__", or "id:30"
       "notes": "captured from a real window on 2026-09-18"}
    ]}
"""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from jev_pilot.policy import DONE, STUCK, apply_policy
from jev_pilot.providers.base import Chooser
from jev_pilot.types import Option


@dataclass(frozen=True)
class Fixture:
    name: str
    goal: str
    state: str
    options: Sequence[Option]
    expect: str
    category: str = ""
    notes: str = ""
    floor: float = 0.0


def load_fixtures(path: str) -> List[Fixture]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError("fixture file must be a list of cases or {'cases': [...]}")
    out: List[Fixture] = []
    for case in cases:
        out.append(Fixture(
            name=str(case["name"]),
            goal=str(case["goal"]),
            state=str(case["state"]),
            options=[Option.from_dict(opt) for opt in case.get("options", [])],
            expect=str(case["expect"]),
            category=str(case.get("category", "")),
            notes=str(case.get("notes", "")),
            floor=float(case.get("floor", 0.0)),
        ))
    return out


def _normalize(text: str) -> str:
    """Case- and spacing-insensitive, quote-insensitive: `Button 'Five'` == `button five`."""
    return re.sub(r"\s+", " ", re.sub(r"['\"]", "", text or "")).strip().lower()


def expected_match(fixture: Fixture, outcome: str, pick: Optional[str], label: Optional[str]) -> bool:
    expect = fixture.expect.strip()
    if expect in (DONE, STUCK):
        return outcome == ("done" if expect == DONE else "stuck")
    if expect.startswith("id:"):
        return outcome == "act" and str(pick) == expect[3:].strip()
    return outcome == "act" and _normalize(label or "") == _normalize(expect)


def run_bench(
    fixtures: Sequence[Fixture],
    choosers: Mapping[str, Chooser],
    *,
    repeats: int = 1,
    floor: float = 0.0,
    timeout: Optional[float] = None,
    progress=None,
) -> Dict[str, Any]:
    """Run every fixture against every chooser. Returns a JSON-friendly report."""
    results: List[Dict[str, Any]] = []
    for fixture in fixtures:
        for chooser_name, chooser in choosers.items():
            for repeat in range(1, max(1, repeats) + 1):
                started = time.perf_counter()
                raw = chooser.choose(goal=fixture.goal, state=fixture.state,
                                     options=fixture.options, timeout=timeout)
                wall_ms = int(round((time.perf_counter() - started) * 1000))
                decision = apply_policy(
                    raw_pick=raw.pick, confidence=raw.confidence, options=fixture.options,
                    floor=fixture.floor or floor, probabilities=raw.probabilities,
                    provider=chooser_name, model=raw.model or getattr(chooser, "model", None),
                    latency_ms=raw.latency_ms or wall_ms, input_tokens=raw.input_tokens,
                    output_tokens=raw.output_tokens, cost_usd=raw.cost_usd, error=raw.error,
                )
                correct = expected_match(fixture, decision.outcome, decision.pick, decision.label)
                record = {
                    "case": fixture.name,
                    "category": fixture.category,
                    "chooser": chooser_name,
                    "repeat": repeat,
                    "expect": fixture.expect,
                    "outcome": decision.outcome,
                    "pick": decision.pick,
                    "label": decision.label,
                    "confidence": decision.confidence,
                    "latency_ms": decision.latency_ms,
                    "correct": correct,
                    "input_tokens": decision.input_tokens,
                    "output_tokens": decision.output_tokens,
                    "cost_usd": decision.cost_usd,
                    "error": decision.error,
                    "reason": decision.reason,
                }
                results.append(record)
                if progress is not None:
                    progress(record)

    summary: Dict[str, Dict[str, Any]] = {}
    for chooser_name in choosers:
        rows = [r for r in results if r["chooser"] == chooser_name]
        if not rows:
            continue
        latencies = sorted(r["latency_ms"] for r in rows if r["latency_ms"] is not None)
        answered = [r for r in rows if r["outcome"] != "error"]
        summary[chooser_name] = {
            "decisions": len(rows),
            "correct": sum(1 for r in rows if r["correct"]),
            "accuracy": round(sum(1 for r in rows if r["correct"]) / len(rows), 4),
            "answered": len(answered),
            "coverage": round(len(answered) / len(rows), 4),
            "errors": sum(1 for r in rows if r["outcome"] == "error"),
            "abstentions": sum(1 for r in rows if r["outcome"] in ("done", "stuck")),
            "escalations": sum(1 for r in rows if r["outcome"] == "escalate"),
            "median_latency_ms": int(statistics.median(latencies)) if latencies else None,
            "min_latency_ms": latencies[0] if latencies else None,
            "max_latency_ms": latencies[-1] if latencies else None,
            "input_tokens": sum(r["input_tokens"] or 0 for r in rows),
            "output_tokens": sum(r["output_tokens"] or 0 for r in rows),
            "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 8),
            "model": next((r.get("model") for r in rows if r.get("model")), None),
        }
    return {"repeats": repeats, "cases": len(fixtures), "results": results, "summary": summary}


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = ["| chooser | correct | accuracy | answered | median ms | range ms | in tok | cost |",
             "|---|---|---|---|---|---|---|---|"]
    for name, stats in report.get("summary", {}).items():
        rng = (f"{stats['min_latency_ms']}-{stats['max_latency_ms']}"
               if stats["min_latency_ms"] is not None else "n/a")
        lines.append(
            f"| {name} | {stats['correct']}/{stats['decisions']} | {stats['accuracy']:.0%} | "
            f"{stats['answered']}/{stats['decisions']} | {stats['median_latency_ms']} | {rng} | "
            f"{stats['input_tokens']} | ${stats['cost_usd']:.6f} |"
        )
    lines.append("")
    lines.append("| case | chooser | expect | got | correct | conf | ms |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in report.get("results", []):
        conf = "" if row["confidence"] is None else f"{row['confidence']:.2f}"
        got = row["label"] or row["outcome"]
        lines.append(
            f"| {row['case']} | {row['chooser']} | {row['expect']} | {got} | "
            f"{'yes' if row['correct'] else 'no'} | {conf} | {row['latency_ms']} |"
        )
    return "\n".join(lines)
