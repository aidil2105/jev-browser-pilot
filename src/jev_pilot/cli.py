"""Command line interface: `jev-pilot run|decide|bench|report|selftest|version`.

Exit codes are part of the contract, because this is meant to run in a pipeline:

    0   every task reached its postcondition
    1   a task did not reach it (abstained, escalated, ran out of budget, no progress)
    2   a hard error: no browser/driver, no credentials, safety refusal, bad input

`decide` is the one-shot form: JSON in, JSON out, so any harness can borrow the
decision step without adopting the whole loop.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from jev_pilot import __version__
from jev_pilot.bench import load_fixtures, render_markdown, run_bench
from jev_pilot.loop import run_episode
from jev_pilot.perception import DomRules, Element, Snapshot
from jev_pilot.policy import apply_policy
from jev_pilot.providers import Chooser, ProviderUnavailable, build_chooser
from jev_pilot.safety import SafetyError, SafetyPolicy, host_of
from jev_pilot.serialize import SerializerOptions, build_state
from jev_pilot.surface import ScriptedSurface
from jev_pilot.trace import TraceRecorder, summarize, write_report
from jev_pilot.types import Option

EXIT_OK, EXIT_UNREACHED, EXIT_ERROR = 0, 1, 2


# ---------------------------------------------------------------- helpers
def _chooser_kwargs(args) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    if args.model:
        kwargs["model"] = args.model
    if getattr(args, "base_url", None):
        kwargs["base_url"] = args.base_url
    if getattr(args, "api_key_env", None):
        import os
        key = os.environ.get(args.api_key_env)
        if not key:
            raise ProviderUnavailable(f"{args.api_key_env} is not set")
        kwargs["api_key"] = key
    if getattr(args, "max_tokens", None):
        kwargs["max_tokens"] = args.max_tokens
    if getattr(args, "input_price", None) is not None:
        kwargs["input_price_per_mtok"] = args.input_price
    if getattr(args, "output_price", None) is not None:
        kwargs["output_price_per_mtok"] = args.output_price
    return kwargs


def _build_chooser(args) -> Chooser:
    kwargs = _chooser_kwargs(args)
    if args.provider == "openai" and not kwargs.get("model"):
        raise ProviderUnavailable("--provider openai needs --model (e.g. --model llama3.1)")
    return build_chooser(args.provider, **kwargs)


def _parse_chooser_specs(specs: Sequence[str]) -> Dict[str, Chooser]:
    choosers: Dict[str, Chooser] = {}
    for spec in specs:
        kind, _, model = spec.partition(":")
        label = spec if model else kind
        kwargs: Dict[str, Any] = {"model": model} if model else {}
        choosers[label] = build_chooser(kind, **kwargs)
    return choosers


def _safety_for(args, start_url: Optional[str]) -> SafetyPolicy:
    hosts = list(args.allow_host or [])
    if not hosts and start_url:
        host = host_of(start_url)
        if host:
            hosts.append(host)
    policy = SafetyPolicy.for_hosts(hosts, allow_typing=args.allow_typing,
                                    dry_run=args.dry_run, max_steps=args.max_steps_cap)
    return policy


def _make_surface(args, start_url: str, safety: SafetyPolicy, rules: DomRules):
    if args.surface == "desktop":
        from jev_pilot.desktop import DesktopPilot
        if not (args.app or args.aumid or args.attach_pid):
            raise ProviderUnavailable("--surface desktop needs --app, --aumid or --attach-pid")
        return DesktopPilot(app=args.app, aumid=args.aumid, attach_pid=args.attach_pid,
                            driver=args.driver, safety=safety, verbose=args.verbose)
    from jev_pilot.browser import BrowserPilot
    return BrowserPilot(start_url, chrome=args.chrome, headless=args.headless,
                        rules=rules, safety=safety, verbose=args.verbose,
                        profile_dir=args.profile_dir, settle_seconds=args.settle)


def _print_step(step, verbose: bool) -> None:
    decision = step.decision
    if decision is None:
        print(f"  step {step.index}: no decision ({step.candidates} candidates)")
        return
    conf = "" if decision.confidence is None else f" conf={decision.confidence:.2f}"
    print(f"  step {step.index}: {decision.outcome}{conf} pick={decision.pick} "
          f"{decision.label or ''} {decision.latency_ms}ms")
    if verbose and decision.reason:
        print(f"    reason: {decision.reason}")
    if verbose and step.truncated:
        print(f"    truncated: {step.candidates} of {step.matched_total} candidates shown")


# ---------------------------------------------------------------- commands
def cmd_version(args) -> int:
    print(f"jev-browser-pilot {__version__} (python {sys.version.split()[0]})")
    return EXIT_OK


def cmd_decide(args) -> int:
    raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    if not raw.strip():
        print("no request on stdin; pass JSON or use --file", file=sys.stderr)
        return EXIT_ERROR
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"request is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_ERROR

    options = [Option.from_dict(o) for o in request.get("options", [])]
    floor = args.floor if args.floor is not None else float(request.get("confidence_floor", 0.0))
    try:
        chooser = _build_chooser(args)
    except (ProviderUnavailable, SafetyError) as exc:
        print(f"provider unavailable: {exc}", file=sys.stderr)
        return EXIT_ERROR

    raw_answer = chooser.choose(goal=request.get("goal", ""), state=request.get("state", ""),
                                options=options, timeout=args.timeout)
    decision = apply_policy(
        raw_pick=raw_answer.pick, confidence=raw_answer.confidence, options=options,
        floor=floor, probabilities=raw_answer.probabilities, provider=chooser.name,
        model=raw_answer.model or chooser.model, latency_ms=raw_answer.latency_ms,
        input_tokens=raw_answer.input_tokens, output_tokens=raw_answer.output_tokens,
        cost_usd=raw_answer.cost_usd, error=raw_answer.error,
    )
    payload = decision.as_dict()
    payload["decision"] = decision.outcome  # compatibility with the original contract
    payload["ms"] = decision.latency_ms
    payload["provider"] = chooser.name
    print(json.dumps(payload, indent=2))
    return EXIT_ERROR if decision.outcome == "error" else EXIT_OK


def _tasks_from_args(args) -> List[Dict[str, Any]]:
    if args.task_file:
        payload = json.loads(Path(args.task_file).read_text(encoding="utf-8"))
        tasks = payload.get("tasks") if isinstance(payload, dict) else payload
        if not isinstance(tasks, list) or not tasks:
            raise ValueError("task file must contain a non-empty list of tasks")
        return [{"goal": str(t["goal"]), "verify": [str(v) for v in t.get("verify", [])],
                 "steps": int(t.get("steps", args.steps))} for t in tasks]
    goals = args.goal or []
    if not goals:
        raise ValueError("nothing to do: pass --goal or --task-file")
    return [{"goal": goal, "verify": list(args.verify or []), "steps": args.steps}
            for goal in goals]


def cmd_run(args) -> int:
    try:
        tasks = _tasks_from_args(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"bad task input: {exc}", file=sys.stderr)
        return EXIT_ERROR

    rules = DomRules(cap=args.max_candidates)
    try:
        chooser = _build_chooser(args)
    except (ProviderUnavailable, SafetyError) as exc:
        print(f"provider unavailable: {exc}", file=sys.stderr)
        return EXIT_ERROR

    safety: Optional[SafetyPolicy] = None
    if not args.no_safety:
        try:
            safety = _safety_for(args, args.start)
        except SafetyError as exc:
            print(f"safety: {exc}", file=sys.stderr)
            return EXIT_ERROR

    trace = TraceRecorder(args.trace, verbatim_state=not args.no_verbatim_state) if args.trace else None
    report = {"version": __version__, "surface": args.surface, "provider": chooser.name,
              "model": chooser.model, "tasks": []}

    try:
        surface = _make_surface(args, args.start, safety, rules)
    except (ProviderUnavailable, SafetyError, RuntimeError) as exc:
        print(f"surface unavailable: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(f"jev-browser-pilot {__version__}")
    print(f"surface: {args.surface} | chooser: {chooser.describe()}")
    if safety is not None:
        print(f"safety: {safety.describe()}")
    else:
        print("safety: DISABLED (--no-safety)")

    exit_code = EXIT_OK
    try:
        surface.start()
        print(f"session: {surface.describe()}")
        if args.dump_state:
            snapshot = surface.observe()
            print("\n--- state the chooser would see ---")
            print(build_state(options=snapshot.options(), url=snapshot.url, title=snapshot.title,
                              text=snapshot.text, history=[], matched_total=snapshot.matched_total,
                              opts=SerializerOptions()))
            print(f"--- {len(snapshot.elements)} candidates kept of {snapshot.matched_total} ---")
            return EXIT_OK

        for task in tasks:
            print(f"\n=== goal: {task['goal']}")
            episode = run_episode(
                surface, chooser, task["goal"], verifiers=task["verify"],
                steps=safety.cap_steps(task["steps"]) if safety else task["steps"],
                floor=args.confidence_floor, safety=safety, dry_run=args.dry_run,
                serialize_opts=SerializerOptions(), timeout=args.timeout, trace=trace,
                on_step=lambda step, ep: _print_step(step, args.verbose),
                extra_lines=args.extra_line or (),
            )
            for check in episode.checks:
                mark = "pass" if check["passed"] else "fail"
                print(f"  {mark}: {check['spec']} ({check['detail']})")
            summary = episode.summary()
            print(f"  result: reached={summary['reached']} stopped={summary['stopped']} "
                  f"steps={summary['steps']} median={summary['median_latency_ms']}ms "
                  f"cost=${summary['cost_usd']:.6f}")
            if trace is not None:
                trace.episode(episode)
            report["tasks"].append(summary)
            if not episode.reached:
                exit_code = max(exit_code, EXIT_UNREACHED)
            if episode.stopped == "blocked":
                print("  stopped: the surface left the allowed hosts; abandoning the "
                      "remaining tasks")
                break
    except (ProviderUnavailable, SafetyError, RuntimeError) as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    finally:
        if not args.keep_open:
            surface.close()
        if trace is not None:
            trace.close()

    if args.report and args.trace:
        path = write_report(args.trace, args.report)
        print(f"report: {path}")
    if args.json:
        print(json.dumps(report, indent=2))
    return exit_code


def cmd_bench(args) -> int:
    try:
        fixtures = load_fixtures(args.fixtures)
        choosers = _parse_chooser_specs(args.chooser)
    except (ValueError, OSError, json.JSONDecodeError, ProviderUnavailable) as exc:
        print(f"bench setup failed: {exc}", file=sys.stderr)
        return EXIT_ERROR

    report = run_bench(fixtures, choosers, repeats=args.repeats, floor=args.floor,
                       timeout=args.timeout,
                       progress=None if not args.verbose else lambda r: print(
                           f"  {r['case']:<18} {r['chooser']:<18} "
                           f"{'ok' if r['correct'] else 'MISS'} ({r['outcome']}) {r['latency_ms']}ms"))
    markdown = render_markdown(report)
    print(markdown)
    for name, stats in report["summary"].items():
        if stats["errors"]:
            print(f"note: {name} returned no answer on {stats['errors']} of {stats['decisions']} calls",
                  file=sys.stderr)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(markdown + "\n", encoding="utf-8")
        print(f"wrote {args.markdown}")
    return EXIT_OK


def cmd_report(args) -> int:
    try:
        path = write_report(args.trace, args.out, title=args.title)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"report failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    records = json.loads("[]")
    from jev_pilot.trace import load_trace
    stats = summarize(load_trace(args.trace))
    print(f"wrote {path}")
    print(json.dumps(stats, indent=2))
    return EXIT_OK


def cmd_selftest(args) -> int:
    """Prove the library works without a browser, a network and credentials."""
    print(f"jev-browser-pilot {__version__} selftest")
    elements = [Element(id="1", role="link", name="Alpha report"),
                Element(id="2", role="link", name="Omega appendix"),
                Element(id="3", role="button", name="Unrelated")]
    first = Snapshot(url="https://example.test/index.html", title="Index",
                     text="Welcome. Alpha report and Omega appendix are available.",
                     elements=elements, matched_total=len(elements))
    second = Snapshot(url="https://example.test/omega.html", title="Omega",
                      text="GOAL REACHED: omega appendix.", elements=[])
    from jev_pilot.providers.base import ScriptedChooser
    chooser = ScriptedChooser(["2"], tokens_per_call=1200, cost_per_call=0.00005)
    surface = ScriptedSurface(snapshots=[first, second])
    episode = run_episode(surface, chooser, "open the Omega appendix",
                          verifiers=["url-contains:omega.html", "text-contains:goal reached"],
                          steps=3, safety=None, on_step=lambda s, e: _print_step(s, False))
    for check in episode.checks:
        print(f"  {'pass' if check['passed'] else 'fail'}: {check['spec']}")
    print(f"  reached={episode.reached} stopped={episode.stopped} steps={len(episode.steps)} "
          f"actions={surface.actions}")

    chain_ok = episode.reached and surface.actions == ["2"]
    # policy checks
    from jev_pilot.policy import apply_policy
    policy_cases = {
        "unknown id is an error": apply_policy(raw_pick="99", confidence=0.9,
                                               options=[Option(id="1", label="x")]).outcome == "error",
        "low confidence escalates with the pick": (
            lambda d: d.outcome == "escalate" and d.pick == "1")(
            apply_policy(raw_pick="1", confidence=0.2, options=[Option(id="1", label="x")], floor=0.5)),
        "transport failure is an error": apply_policy(raw_pick=None, error="boom").outcome == "error",
    }
    for name, passed in policy_cases.items():
        print(f"  {'pass' if passed else 'fail'}: {name}")

    if args.live:
        try:
            live = build_chooser("jev", model=args.model) if args.model else build_chooser("jev")
            answer = live.choose(goal="pick the first option", state="Only one option exists.",
                                 options=[Option(id="1", label="the only option")])
            print(f"  live: outcome ok, pick={answer.pick} conf={answer.confidence} "
                  f"{answer.latency_ms}ms cost=${answer.cost_usd or 0:.8f} model={answer.model}")
            live_ok = answer.error is None
        except ProviderUnavailable as exc:
            print(f"  live: SKIPPED ({exc})")
            live_ok = True
        except Exception as exc:  # noqa: BLE001
            print(f"  live: FAILED ({type(exc).__name__}: {exc})")
            live_ok = False
    else:
        live_ok = True

    ok = chain_ok and all(policy_cases.values()) and live_ok
    print("selftest:", "PASS" if ok else "FAIL")
    return EXIT_OK if ok else EXIT_UNREACHED


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jev-pilot",
        description="A bounded decision layer for browser and desktop automation.",
    )
    parser.add_argument("--version", action="version", version=f"jev-browser-pilot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print the version").set_defaults(func=cmd_version)

    # decide
    decide = sub.add_parser("decide", help="one decision, JSON in / JSON out")
    decide.add_argument("--provider", default="jev", choices=["jev", "openai", "mock", "scripted"])
    decide.add_argument("--model")
    decide.add_argument("--base-url")
    decide.add_argument("--api-key-env")
    decide.add_argument("--max-tokens", type=int)
    decide.add_argument("--input-price", type=float)
    decide.add_argument("--output-price", type=float)
    decide.add_argument("--floor", type=float, default=None, help="override confidence_floor")
    decide.add_argument("--timeout", type=float, default=None)
    decide.add_argument("--file", help="read the request from a file instead of stdin")
    decide.set_defaults(func=cmd_decide)

    def add_provider_flags(p):
        p.add_argument("--provider", default="jev", choices=["jev", "openai", "mock", "scripted"],
                       help="decision backend (default: jev)")
        p.add_argument("--model", help="model id (required for --provider openai)")
        p.add_argument("--base-url", help="OpenAI-compatible base URL")
        p.add_argument("--api-key-env", help="environment variable holding the API key")
        p.add_argument("--max-tokens", type=int, help="cap for OpenAI-compatible calls")
        p.add_argument("--input-price", type=float, help="USD per million input tokens (for cost reporting)")
        p.add_argument("--output-price", type=float, help="USD per million output tokens")

    def add_surface_flags(p):
        p.add_argument("--surface", default="browser", choices=["browser", "desktop"])
        p.add_argument("--chrome", help="path to Chrome/Chromium")
        p.add_argument("--profile-dir", help="user-data-dir for the browser surface")
        p.add_argument("--headless", action="store_true")
        p.add_argument("--settle", type=float, default=2.5, help="seconds to wait after launch")
        p.add_argument("--max-candidates", type=int, default=DomRules().cap,
                       help="perception cap: how many candidates reach the chooser")
        p.add_argument("--app", help="desktop surface: app name to launch")
        p.add_argument("--aumid", help="desktop surface: packaged app AUMID")
        p.add_argument("--attach-pid", type=int, help="desktop surface: attach to a running pid")
        p.add_argument("--driver", help="desktop surface: path to cua-driver")

    # run
    run = sub.add_parser("run", help="run one or more bounded goals against a live surface")
    run.add_argument("--start", default="about:blank", help="start URL (browser surface)")
    run.add_argument("--goal", action="append", help="goal text; repeat for a chain")
    run.add_argument("--verify", action="append",
                     help="postcondition: url-contains:, url-regex:, text-contains:, selector:, "
                          "file-contains:PATH::TEXT (repeatable)")
    run.add_argument("--task-file", help="JSON list of {goal, verify[], steps} run in order")
    run.add_argument("--steps", type=int, default=4, help="step budget per goal")
    run.add_argument("--confidence-floor", type=float, default=0.0)
    run.add_argument("--allow-host", action="append", help="extra host to allow (repeatable)")
    run.add_argument("--allow-typing", action="store_true", help="enable typing actions")
    run.add_argument("--dry-run", action="store_true", help="decide, record, do not act")
    run.add_argument("--no-safety", action="store_true",
                     help="disable the host and action rails (not recommended)")
    run.add_argument("--max-steps-cap", type=int, default=12)
    run.add_argument("--timeout", type=float, default=None, help="per-decision timeout in seconds")
    run.add_argument("--trace", help="write a JSONL trace here")
    run.add_argument("--report", help="write an HTML report here (needs --trace)")
    run.add_argument("--no-verbatim-state", action="store_true",
                     help="do not store the exact state string in the trace")
    run.add_argument("--dump-state", action="store_true",
                     help="print the state the chooser would see, then exit")
    run.add_argument("--extra-line", action="append", help="extra line added to every state")
    run.add_argument("--keep-open", action="store_true")
    run.add_argument("--json", action="store_true", help="print the machine-readable summary")
    run.add_argument("--verbose", action="store_true")
    add_provider_flags(run)
    add_surface_flags(run)
    run.set_defaults(func=cmd_run)

    # bench
    bench = sub.add_parser("bench", help="compare choosers on frozen states")
    bench.add_argument("--fixtures", required=True)
    bench.add_argument("--chooser", action="append", default=None,
                       help="chooser spec: jev, openai:MODEL, mock, scripted (repeatable)")
    bench.add_argument("--repeats", type=int, default=1)
    bench.add_argument("--floor", type=float, default=0.0)
    bench.add_argument("--timeout", type=float, default=None)
    bench.add_argument("--out", help="write the full report JSON here")
    bench.add_argument("--markdown", help="write the markdown tables here")
    bench.add_argument("--verbose", action="store_true")
    bench.add_argument("--model", help="model for the openai chooser")
    bench.add_argument("--base-url")
    bench.add_argument("--api-key-env")
    bench.add_argument("--input-price", type=float)
    bench.add_argument("--output-price", type=float)
    bench.add_argument("--max-tokens", type=int)
    bench.set_defaults(func=cmd_bench)

    # report
    report = sub.add_parser("report", help="render an HTML report from a trace")
    report.add_argument("--trace", required=True)
    report.add_argument("--out", required=True)
    report.add_argument("--title", default="jev-browser-pilot trace")
    report.set_defaults(func=cmd_report)

    # selftest
    selftest = sub.add_parser("selftest", help="offline proof that the loop and policy work")
    selftest.add_argument("--live", action="store_true", help="also make one real Jev call")
    selftest.add_argument("--model")
    selftest.set_defaults(func=cmd_selftest)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "chooser", None) is None and args.command == "bench":
        args.chooser = ["mock"]
    try:
        return int(args.func(args))
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted", file=sys.stderr)
        return EXIT_ERROR
    except SafetyError as exc:
        print(f"safety refusal: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except ProviderUnavailable as exc:
        print(f"provider unavailable: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
