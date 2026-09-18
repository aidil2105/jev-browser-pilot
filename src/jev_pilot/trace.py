"""Tracing: a JSONL record of every episode, plus a self-contained HTML report.

A decision layer that cannot be audited afterwards is a liability. Every step is
recorded with the state it saw, the ids it was offered, the answer, the confidence,
the latency, the tokens and the cost, and an episode ends with its postcondition
results. `write_report` renders that into one HTML file with no external assets, so
it can be attached to a PR, a bug report, or a support thread.
"""

from __future__ import annotations

import html
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from jev_pilot.types import Episode, Step


class TraceRecorder:
    """Append-only JSONL trace. One file can hold many episodes."""

    def __init__(self, path: Optional[str] = None, *, verbatim_state: bool = True, echo: bool = False):
        self.path = Path(path) if path else None
        self.verbatim_state = verbatim_state
        self.echo = echo
        self.records: List[Dict[str, Any]] = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    # ---- writing ------------------------------------------------------
    def _write(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.records.append(record)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.echo:
            print(json.dumps(record, ensure_ascii=False))
        return record

    def event(self, kind: str, **payload) -> Dict[str, Any]:
        return self._write({"kind": kind, **payload})

    def step(self, step: Step, note: Optional[str] = None) -> Dict[str, Any]:
        record = {"kind": "step", **step.as_dict(state=self.verbatim_state)}
        if note:
            record["note"] = note
        return self._write(record)

    def episode(self, episode: Episode) -> Dict[str, Any]:
        record = {"kind": "episode", **episode.as_dict(state=False)}
        return self._write(record)

    def close(self) -> None:
        return None


def load_trace(path: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _episode_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in records if r.get("kind") == "episode"]


def summarize(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    records = list(records)
    episodes = _episode_records(records)
    steps = [r for r in records if r.get("kind") == "step"]
    latencies = [s["decision"]["latency_ms"] for s in steps
                 if isinstance(s.get("decision"), dict) and s["decision"].get("latency_ms") is not None]
    latencies.sort()
    outcomes: Dict[str, int] = {}
    for step in steps:
        decision = step.get("decision") or {}
        outcomes[decision.get("outcome", "?")] = outcomes.get(decision.get("outcome", "?"), 0) + 1
    return {
        "episodes": len(episodes),
        "steps": len(steps),
        "reached": sum(1 for e in episodes if e.get("reached")),
        "outcomes": outcomes,
        "median_latency_ms": latencies[len(latencies) // 2] if latencies else None,
        "total_cost_usd": round(sum(e.get("cost_usd") or 0 for e in episodes), 8),
        "total_input_tokens": sum(e.get("input_tokens") or 0 for e in episodes),
    }


def write_report(trace_path: str, out_path: str, *, title: str = "jev-browser-pilot trace") -> Path:
    records = load_trace(trace_path)
    episodes = _episode_records(records)
    steps_by_episode: Dict[int, List[Dict[str, Any]]] = {}
    current = -1
    for record in records:
        if record.get("kind") == "episode":
            current += 1
            steps_by_episode.setdefault(current, [])
        elif record.get("kind") == "step" and current >= 0:
            steps_by_episode.setdefault(current, []).append(record)

    parts: List[str] = [
        "<!doctype html>",
        '<meta charset="utf-8">',
        f"<title>{html.escape(title)}</title>",
        "<style>",
        ":root{--fg:#16161a;--muted:#5c5f66;--line:#e2e2e6;--bg:#fbfbfc;--ok:#1a7f4b;--warn:#9a5b00;--err:#b3261e}",
        "body{margin:0;padding:28px;background:var(--bg);color:var(--fg);"
        "font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}",
        "h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}",
        ".sub{color:var(--muted);margin:0 0 20px}",
        ".chips{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}",
        ".chip{border:1px solid var(--line);border-radius:999px;padding:4px 11px;background:#fff;font-size:13px}",
        "table{border-collapse:collapse;width:100%;background:#fff;border:1px solid var(--line)}",
        "th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top;font-size:13px}",
        "th{background:#f4f4f6;font-weight:600}",
        "td.num{text-align:right;font-variant-numeric:tabular-nums}",
        "code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}",
        ".ok{color:var(--ok);font-weight:600}.warn{color:var(--warn);font-weight:600}.err{color:var(--err);font-weight:600}",
        "pre{background:#fff;border:1px solid var(--line);padding:10px;overflow:auto;max-height:340px;font-size:12.5px}",
        ".bar{display:inline-block;height:9px;background:#8a8f98;border-radius:2px;vertical-align:middle}",
        "</style>",
    ]

    summary = summarize(records)
    parts.append(f"<h1>{html.escape(title)}</h1>")
    parts.append(
        f'<p class="sub">{summary["episodes"]} episode(s), {summary["steps"]} decision step(s), '
        f'{summary["reached"]} reached, total cost ${summary["total_cost_usd"]:.6f}</p>'
    )
    parts.append('<div class="chips">')
    chips = [
        ("median step latency", f'{summary["median_latency_ms"]} ms' if summary["median_latency_ms"] else "n/a"),
        ("input tokens", str(summary["total_input_tokens"])),
        ("outcomes", ", ".join(f"{k}={v}" for k, v in sorted(summary["outcomes"].items())) or "none"),
    ]
    for label, value in chips:
        parts.append(f'<span class="chip">{html.escape(label)}: {html.escape(value)}</span>')
    parts.append("</div>")

    for index, episode in enumerate(episodes):
        verdict = ('<span class="ok">reached</span>' if episode.get("reached")
                   else f'<span class="err">not reached</span>')
        parts.append(f"<h2>Episode {index + 1}: {html.escape(str(episode.get('goal', '')))}</h2>")
        parts.append(
            f'<p class="sub">{verdict} · stopped: {html.escape(str(episode.get("stopped")))} · '
            f'{episode.get("steps")} step(s) · provider {html.escape(str(episode.get("provider")))} '
            f'{html.escape(str(episode.get("model") or ""))} · '
            f'median {episode.get("median_latency_ms")} ms · ${(episode.get("cost_usd") or 0):.6f}</p>'
        )
        parts.append(
            "<table><tr><th>#</th><th>outcome</th><th>pick</th><th>label</th><th>conf</th>"
            "<th>ms</th><th>latency</th><th>reason</th></tr>"
        )
        step_records = steps_by_episode.get(index, [])
        max_ms = max([(s.get("decision") or {}).get("latency_ms") or 0 for s in step_records] or [1])
        for step in step_records:
            decision = step.get("decision") or {}
            outcome = str(decision.get("outcome", ""))
            css = {"act": "ok", "done": "warn", "stuck": "warn", "escalate": "warn", "error": "err"}.get(outcome, "")
            ms = decision.get("latency_ms") or 0
            width = int(120 * (ms / max_ms)) if max_ms else 0
            confidence = decision.get("confidence")
            confidence_text = "" if confidence is None else f"{confidence:.2f}"
            parts.append(
                f"<tr><td class=\"num\">{step.get('index')}</td>"
                f'<td class="{css}">{html.escape(outcome)}</td>'
                f"<td><code>{html.escape(str(decision.get('pick')))}</code></td>"
                f"<td>{html.escape(str(decision.get('label') or ''))}</td>"
                f'<td class="num">{confidence_text}</td>'
                f'<td class="num">{ms}</td>'
                f'<td><span class="bar" style="width:{width}px"></span></td>'
                f"<td>{html.escape(str(decision.get('reason') or ''))}</td></tr>"
            )
        parts.append("</table>")

        checks = episode.get("checks") or []
        if checks:
            parts.append("<h2>Postconditions</h2><table><tr><th>spec</th><th>result</th><th>detail</th></tr>")
            for check in checks:
                css = "ok" if check.get("passed") else "err"
                parts.append(
                    f'<tr><td><code>{html.escape(str(check.get("spec")))}</code></td>'
                    f'<td class="{css}">{"pass" if check.get("passed") else "fail"}</td>'
                    f'<td>{html.escape(str(check.get("detail") or ""))}</td></tr>'
                )
            parts.append("</table>")

        states = [s for s in step_records if s.get("state")]
        if states:
            parts.append("<h2>State sent to the chooser (last step)</h2>")
            parts.append(f"<pre>{html.escape(str(states[-1]['state']))}</pre>")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    return out
