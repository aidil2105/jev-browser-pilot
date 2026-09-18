# jev-browser-pilot

[![CI](https://github.com/aidil2105/jev-browser-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/aidil2105/jev-browser-pilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A bounded decision layer for browser and desktop automation. Your code observes, decides what
can be done, executes it, and verifies the result. A decision-only model makes exactly one
choice per step: which candidate is next.

The loop is not new. What is new is the split: the model never sees a screenshot, never writes
a selector, never produces text, and never decides whether it succeeded. It answers one bounded
question over a list of ids your code built, and returns a confidence your code routes on.

```
observe (your code)  ->  decide (the model, one typed choice)  ->  act (your code)  ->  verify (your code)
```

## Why this shape

An agent that reads a page with a full language model pays seconds and cents per step for a
judgment that is often a single pick among a handful of visible options. Measured on the same
frozen observation in this repo (`docs/findings.md`):

| chooser | correct | median per decision | coverage |
|---|---|---|---|
| Jev (decision model) | 15/15 | 350 ms | 15/15 answered |
| a mid-tier chat model | 7/10 | 3,536 ms | 7/10 answered |
| a smaller free model | 5/10 | 7,318 ms | 8/10 answered |

And end to end on a live site through this library's own CLI, one browser session, three hops,
each goal reached in a single decision: 1454 ms, 297 ms, 295 ms, $0.00086 total.

## What this is not

- **Not an autonomous agent.** There is no lookahead. If the next step is not derivable from the
  current observation, the model answers `__stuck__`. Put a planner above it.
- **Not a text generator.** It cannot produce the string to type, the URL to open or the value
  to set. Your code owns content.
- **Not a success oracle.** The postcondition is checked by code, before and after every action.
  The model is never asked whether it worked.

## Install

```
pip install jev-browser-pilot              # core: browser surface over CDP
pip install "jev-browser-pilot[jev]"       # + the TypeSafe Jev provider (Python 3.10+)
```

Python 3.9 or newer. The browser surface needs `websocket-client` (installed with the package)
and a local Chrome, Chromium or Edge. The Jev provider needs Python 3.10 or newer, because the
vendor SDK does; on 3.9 the core, the OpenAI-compatible provider and the mock chooser all work and
the Jev provider reports that clearly instead of failing to install.

## Quickstart

Prove the loop works with no browser, no network and no credentials:

```
jev-pilot selftest
```

Borrow just the decision step (JSON in, JSON out) from any harness:

```
echo '{"goal":"open the Omega appendix",
       "state":"CANDIDATE ACTIONS:\n[1] a (Alpha report)\n[2] a (Omega appendix)",
       "options":[{"id":"1","label":"a (Alpha report)"},{"id":"2","label":"a (Omega appendix)"}]}' \
  | jev-pilot decide --provider jev
```

Drive a real site (own Chrome profile, own port, hosts locked to the start URL):

```
jev-pilot run \
  --start "https://en.wikipedia.org/wiki/Calculator" \
  --task-file examples/wikipedia-chain.json \
  --provider jev --trace scratch/run.jsonl --report scratch/run.html
```

Exit codes are part of the contract: `0` every goal reached, `1` a goal not reached, `2` a hard
error (no browser, no credentials, safety refusal, bad input).

Prefer the library to the CLI:

```python
from jev_pilot import SafetyPolicy, build_state, run_episode
from jev_pilot.browser import BrowserPilot
from jev_pilot.providers import build_chooser

safety = SafetyPolicy.for_url("https://en.wikipedia.org/wiki/Calculator")
with BrowserPilot("https://en.wikipedia.org/wiki/Calculator", headless=True, safety=safety) as pilot:
    episode = run_episode(
        pilot, build_chooser("jev"), "open the article about the slide rule",
        verifiers=["url-contains:Slide_rule"], steps=3, safety=safety,
    )
print(episode.reached, episode.summary())
```

## The decision policy (in code, not in a prompt)

- an answer that is not one of the offered ids is rejected (`error`);
- `__done__` and `__stuck__` are the only abstentions, and they never become an action;
- a pick below `--confidence-floor` becomes `escalate`, **with the pick attached**, so a planner
  or a human can take the step instead;
- a transport or API failure is `error` with no pick. Treat `error` as "no decision".

## Providers

| name | what it is | notes |
|---|---|---|
| `jev` | TypeSafe Jev, a decision-only model | needs `TYPESAFE_API_KEY`; `$0.042` per million input tokens, output free |
| `openai` | any OpenAI-compatible endpoint | Ollama, vLLM, LM Studio, a gateway; needs `--model` |
| `mock` | deterministic keyword overlap | credential-free: CI, docs, offline development |
| `scripted` | a fixed answer sequence | tests |

Swapping providers changes one argument. The policy, the safety rails, the traces and the
verification are identical, which is the point of keeping the model behind an interface.

## Safety rails

Opt-in by construction, because this drives a real browser on a real machine:

- **hosts are declared**, not inferred: navigation is confined to them (a `file://` page reports
  the pseudo-host `file`), and the moment the surface lands elsewhere the episode stops with
  `blocked` and the remaining tasks are abandoned;
- **only `click` is allowed** by default; typing is off until `--allow-typing`;
- there is no API for passwords, tokens or card numbers anywhere in this library;
- the browser always runs on its own `--user-data-dir` and its own debugging port, so it cannot
  attach to a logged-in profile;
- `--dry-run` decides and records, and stops before actuation.

## Benchmarks over frozen states

`jev-pilot bench` replays a JSON file of frozen observations against several choosers, so a
comparison is about the decision and not about who got luckier with perception:

```
jev-pilot bench --fixtures tests/fixtures/calc-frozen.json --chooser jev --chooser mock \
                --chooser openai:llama3.1 --repeats 3 --markdown bench.md
```

## Traces and reports

Every step is recorded: the exact state sent, the ids offered, the answer, the confidence, the
latency, the tokens and the cost. `jev-pilot report` renders it into one self-contained HTML file
with no external assets, so it can be attached to a bug report or a PR.

## Known limits

- **Perception is the ceiling.** On a Wikipedia article, 200 of 447 candidate links fit the cap;
  what falls past it is invisible, and a correct `__stuck__` can mean "I cannot see it" rather
  than "it is not there".
- **Confidence is a router, not a gate.** On the same ambiguous hop, the same model scored 0.49 in
  one run and 0.61 in another. Set the floor from the observed distribution on your own task.
- **No lookahead, no typing, no re-planning.** Those belong to a planner above this layer.
- **The desktop surface is experimental.** It drives a native window through a UI Automation tree
  via cua-driver; UIA quality varies by application.

## What has been verified

Every claim here was produced by a run, on this checkout, and the command is quoted with it.

| claim | evidence |
|---|---|
| the loop, policy and surfaces work | `pytest`: 130 passed, no credentials, no network |
| the browser surface drives a real browser | `pytest -m live`: launches headless Chrome against a local fixture and reaches its postcondition |
| the package installs and runs as a package | `uv build` then install the wheel into a fresh venv, with no extras: `jev-pilot selftest` prints PASS |
| Python 3.9 and 3.13 | `pytest` passes on 3.9.24 and 3.13.9 as well as 3.11 |
| a live site, real model, through the CLI | `jev-pilot run --start https://en.wikipedia.org/wiki/Calculator --task-file examples/wikipedia-chain.json --provider jev --headless`: 3/3 hops, 1454 / 297 / 295 ms, $0.00086 |
| the same chain through the library API | `python examples/browser_chain.py --provider jev --headless`: 3/3 hops reached |
| the OpenAI-compatible provider against a real endpoint | `jev-pilot decide --provider openai --model cl/deepseek/deepseek-v4-flash --base-url http://127.0.0.1:20128/v1`: correct pick in 4357 ms |
| a second chooser on the frozen fixtures | `jev-pilot bench --fixtures tests/fixtures/calc-frozen.json --chooser mock --chooser openai:cl/deepseek/deepseek-v4-flash`: mock 1/4, the chat model 3/4 with one unanswered call |
| the desktop surface | `jev-pilot run --surface desktop --aumid Microsoft.WindowsCalculator_8wekyb3d8bbwe!App --provider jev --steps 6 --verify text-contains:8`: four real clicks on a live window, display verified from the window's own text, exit code 0, $0.000247 |
| CI on three platforms | GitHub Actions run on `main`: 3.9, 3.11 on Ubuntu, Windows and macOS, 3.13, and the live browser job, all green |

Not yet verified, and the docs say so where it matters: task-set success rates, and a head-to-head
loop comparison against a frontier model.

## Status

`building`, released as `0.1.0` (alpha). Started 2026-09-18. What changed is in `CHANGELOG.md`; what
has been verified, and what has not, is in `docs/findings.md`. Roadmap items live as issues rather
than in this file.

## Where things live

- `src/jev_pilot/`: the library (loop, policy, perception, safety, traces, bench, CLI, surfaces).
- `tests/`: 137 credential-free tests, plus one `live` test that drives a real headless Chrome.
- `docs/`: architecture, perception, decisions, cookbook, findings, parity with the wider ecosystem
  effort, and a decision log that records which calls were made by a model and which by hand.
- `examples/`: a task file and runnable examples.
- `.github/workflows/`: CI (credential-free) and an optional manual live lane.

