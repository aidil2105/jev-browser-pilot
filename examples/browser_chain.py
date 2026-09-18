"""Run a three-hop chain with the library API instead of the CLI.

    python examples/browser_chain.py                     # credential-free (mock chooser)
    python examples/browser_chain.py --provider jev      # needs TYPESAFE_API_KEY
    python examples/browser_chain.py --dump              # print the state the chooser sees

The chain is a list of (goal, postcondition) pairs executed in one browser session. Verification
is by URL, so the success decision never involves the model.

The default `mock` chooser is a naive keyword overlap stand-in for development: it gets the first
hop (where the goal nearly quotes the link text) and then wanders, which is exactly the behaviour
that exposed the host-safety gap. Use `--provider jev` or another real chooser for real runs.
"""

from __future__ import annotations

import argparse
import sys

from jev_pilot import SafetyPolicy, run_episode
from jev_pilot.browser import BrowserPilot
from jev_pilot.providers import build_chooser

START = "https://en.wikipedia.org/wiki/Calculator"
CHAIN = [
    ("open the article about the slide rule", "url-contains:Slide_rule"),
    ("open the article about William Oughtred, the inventor of the slide rule",
     "url-contains:William_Oughtred"),
    ("open the article about Richard Delamain, the rival who claimed priority for the slide rule",
     "url-contains:Delamain"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="mock", help="jev, openai, mock or scripted")
    parser.add_argument("--model", default=None)
    parser.add_argument("--steps", type=int, default=2, help="step budget per hop")
    parser.add_argument("--floor", type=float, default=0.0, help="escalate below this confidence")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--dump", action="store_true", help="print the state, then exit")
    args = parser.parse_args()

    safety = SafetyPolicy.for_url(START)
    chooser = build_chooser(args.provider, **({"model": args.model} if args.model else {}))
    print(f"provider={chooser.describe()} safety={safety.describe()}")

    failures = 0
    with BrowserPilot(START, headless=args.headless, safety=safety) as pilot:
        if args.dump:
            from jev_pilot.serialize import build_state
            snapshot = pilot.observe()
            print(build_state(options=snapshot.options(), url=snapshot.url, title=snapshot.title,
                              text=snapshot.text, matched_total=snapshot.matched_total))
            print(f"--- {len(snapshot.elements)} kept of {snapshot.matched_total} matched ---")
            return 0

        for goal, postcondition in CHAIN:
            episode = run_episode(pilot, chooser, goal, verifiers=[postcondition],
                                  steps=args.steps, floor=args.floor, safety=safety)
            summary = episode.summary()
            mark = "PASS" if summary["reached"] else "FAIL"
            print(f"{mark} {goal[:52]:<54} steps={summary['steps']} "
                  f"median={summary['median_latency_ms']}ms cost=${summary['cost_usd']:.6f}")
            if not summary["reached"]:
                failures += 1
                print(f"     stopped={summary['stopped']} final={summary['final_url']}")
                if summary["stopped"] == "blocked":
                    print("     the surface left the allowed hosts; stopping the chain")
                    break

    print(f"\n{len(CHAIN) - failures}/{len(CHAIN)} hops reached")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
