# jev-browser-pilot

[![CI](https://github.com/aidil2105/jev-browser-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/aidil2105/jev-browser-pilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9 to 3.13](https://img.shields.io/badge/python-3.9%20to%203.13-blue.svg)](pyproject.toml)

A bounded decision layer for browser and desktop automation. Your code observes the surface,
builds the list of things it could do, executes one of them, and checks the result. A
decision-only model makes exactly one choice per step: which candidate is next.

```
observe (your code)  ->  decide (the model, one typed choice)  ->  act (your code)  ->  verify (your code)
```

The loop is not new. What is different is the split. The model never sees a screenshot, never
writes a selector, never produces text to type, and is never asked whether it succeeded. It
answers one bounded question over a list of ids your code built, and returns a confidence your
code routes on. Everything that can fail silently stays in code.

That buys two things: a step that costs a fraction of a cent and answers in a few hundred
milliseconds, and an audit trail that shows exactly what the model was shown at every step.

## Install

Not on PyPI yet, so `pip install jev-browser-pilot` does not resolve. Use the repository:

```
pip install "git+https://github.com/aidil2105/jev-browser-pilot"
# with the Jev provider (Python 3.10 or newer):
pip install "jev-browser-pilot[jev] @ git+https://github.com/aidil2105/jev-browser-pilot"
```

Or from a clone, which is what the commands below assume:

```
git clone https://github.com/aidil2105/jev-browser-pilot
cd jev-browser-pilot
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,jev]"    # Windows
# .venv/bin/python -m pip install -e ".[dev,jev]"      # macOS and Linux
```

The only runtime dependency is `websocket-client`. The browser surface uses the Chrome,
Chromium or Edge you already have. The Jev provider needs Python 3.10 or newer because the
vendor SDK does; on 3.9 the core, the OpenAI-compatible provider and the mock chooser all work
and the Jev provider says so plainly instead of failing to install.

Releases are built and uploaded by `.github/workflows/publish.yml` when a GitHub release is
published, using PyPI's trusted publishing rather than a stored token; `docs/publishing.md` has
the one-time PyPI setup and the local fallback.

## Quickstart

Three commands, in this order. The first one needs nothing at all.

**1. Prove the loop works, offline.** No browser, no network, no credentials:

```
$ jev-pilot selftest
jev-browser-pilot 0.1.0 selftest
  step 1: act pick=2 link 'Omega appendix' 0ms
  pass: url-contains:omega.html
  pass: text-contains:goal reached
  reached=True stopped=reached steps=1 actions=['2']
  pass: unknown id is an error
  pass: low confidence escalates with the pick
  pass: transport failure is an error
selftest: PASS
```

**2. Borrow just the decision step.** JSON in, JSON out, so any harness can use it without
adopting the loop:

```
$ echo '{"goal":"open the Omega appendix",
         "state":"CANDIDATE ACTIONS:\n[1] link (Alpha report)\n[2] link (Omega appendix)",
         "options":[{"id":"1","label":"link (Alpha report)"},
                    {"id":"2","label":"link (Omega appendix)"}]}' \
  | jev-pilot decide --provider mock
{
  "outcome": "act",
  "pick": "2",
  "label": "link (Omega appendix)",
  "confidence": 0.8,
  "provider": "keyword",
  "reason": "picked"
}
```

Output trimmed to the fields that matter; the real object also carries the full probability map,
tokens, cost and latency. The mock provider reports itself as `keyword`, which is what it is: a
deterministic keyword overlap, so the quickstart needs no key and no network.

**3. Drive a real site.** The browser gets its own profile and its own debugging port, and the
hosts it may touch are declared up front:

```
$ jev-pilot run --start "https://en.wikipedia.org/wiki/Calculator" \
      --task-file examples/wikipedia-chain.json \
      --provider jev --headless --trace run.jsonl --report run.html
```

Exit codes are part of the contract, because this is meant to run in a pipeline: `0` every goal
reached its postcondition, `1` a goal did not reach it, `2` a hard error (no browser, no
credentials, a safety refusal, bad input).

## What a run looks like

Real output, three chained goals in one browser session, one decision per hop:

```
jev-browser-pilot 0.1.0
surface: browser | chooser: jev model=jev-latest
safety: hosts=[en.wikipedia.org] actions=['click'] typing=off dry_run=False max_steps=12
session: chrome pid=9804 port=33154 profile=33154

=== goal: open the article about the slide rule
  step 1: act conf=0.95 pick=100 a 'slide rule' 1454ms
  pass: url-contains:Slide_rule ('Slide_rule' in 'https://en.wikipedia.org/wiki/Slide_rule')
  result: reached=True stopped=reached steps=1 median=1454ms cost=$0.000270

=== goal: open the article about William Oughtred, the inventor of the slide rule
  step 1: act conf=0.99 pick=14 a 'William Oughtred' 297ms
  pass: url-contains:William_Oughtred ('William_Oughtred' in 'https://en.wikipedia.org/wiki/William_Oughtred')
  result: reached=True stopped=reached steps=1 median=297ms cost=$0.000286

=== goal: open the article about Richard Delamain, the rival who claimed priority for the slide rule
  step 1: act conf=0.47 pick=88 a 'Richard Delamain' 295ms
  pass: url-contains:Delamain ('Delamain' in 'https://en.wikipedia.org/wiki/Richard_Delamaine')
  result: reached=True stopped=reached steps=1 median=295ms cost=$0.000301
report: run.html
```

Three goals, three decisions, $0.00086 for the session. Note the third hop: it is the only one
whose goal describes a person rather than nearly quoting the link text, and it is the only one
answered at 0.47 confidence. Right answer, visibly less sure. That confidence is the signal you
route on.
## Why this shape

An agent that reads a page with a full language model pays seconds and cents per step for a
judgment that is often a single pick among a handful of visible options. Measured on five frozen
observations of a real window, three repeats each, no capture and no actuation involved, so this is
the decision alone (`examples/bench-calculator.json`):

| chooser | correct | accuracy | answered | median | range | cost |
|---|---|---|---|---|---|---|
| `jev` | 15/15 | 100% | 15/15 | 349 ms | 277 to 870 ms | $0.000393 |
| `openai`, a mid-tier chat model | 12/15 | 80% | 12/15 | 2,858 ms | 4 to 15,328 ms | not metered here |
| `mock`, keyword overlap | 3/15 | 20% | 15/15 | 0 ms | 0 ms | free |

Read that honestly: the chat model's three misses are all the same transport failure on the hardest
state (a relay 503, not a wrong answer), so the column that matters most between it and `jev` here
is latency. `jev` answered every call, never wrong, at 0.93 to 1.00 confidence on the four
deterministic states and 0.78 on the one that relies on reading a display. The `mock` chooser fails
every state whose answer is not in the goal's own words, which is exactly what a naive keyword
overlap should do.

Reproduce it, or run it against your own states:

```
jev-pilot bench --fixtures examples/bench-calculator.json \
                --chooser jev --chooser mock --chooser openai:llama3.1 \
                --base-url http://localhost:11434/v1 --repeats 3
```

The `mock` chooser is a deterministic keyword overlap stand-in, deliberately naive: it exists so
the library, its tests and its docs work with no key, no network and no spend. It is a fixture,
not a baseline to beat.

## What this is not

- **Not an autonomous agent.** There is no lookahead. If the next step is not derivable from the
  current observation, the model answers `__stuck__` instead of guessing. Put a planner above it.
- **Not a text generator.** It cannot produce the string to type, the URL to open or the value to
  set. Your code owns content. It also means no prompt injection can make it invent one.
- **Not a success oracle.** Postconditions are evaluated by code, before and after every action.
  The model's `done` is a report, not a proof.

## How it fits together

| piece | what it does |
|---|---|
| `Surface` | whatever you are driving: `BrowserPilot`, `DesktopPilot`, `ScriptedSurface`, or your own object with `observe`/`act`/`url`/`probe` |
| `perception` | turns a page or a window into `Element`s and mints the candidate `Option` ids |
| `serialize` | renders the exact state string the model sees |
| `Chooser` | the decision backend: `jev`, `openai` (any compatible endpoint), `mock`, `scripted`, or yours |
| `policy` | what an answer is allowed to mean, in code rather than in a prompt |
| `verify` | deterministic postconditions: URL, text, CSS selector, file contents |
| `safety` | declared hosts, allowed actions, typing off by default, dry run |
| `trace` | JSONL per step plus a self-contained HTML report |
| `bench` | the same frozen states replayed against several choosers |

The library API is small enough to quote:

```python
from jev_pilot import SafetyPolicy, run_episode
from jev_pilot.browser import BrowserPilot
from jev_pilot.providers import build_chooser

safety = SafetyPolicy.for_url("https://en.wikipedia.org/wiki/Calculator")
chooser = build_chooser("jev")          # or "openai" with model=..., or "mock"

with BrowserPilot("https://en.wikipedia.org/wiki/Calculator", headless=True,
                  safety=safety) as pilot:
    episode = run_episode(
        pilot, chooser,
        goal="open the article about the slide rule",
        verifiers=["url-contains:Slide_rule"],
        steps=3, floor=0.6, safety=safety,
    )

print(episode.reached, episode.stopped, episode.summary())
```

## The decision policy

One question per step: a single choice over the candidate ids, plus two sentinels. The rules that
turn an answer into an outcome live in `policy.py`:

| outcome | meaning | who handles it |
|---|---|---|
| `act` | a candidate was chosen and is safe to execute | the loop clicks it |
| `done` | the model reports the goal is achieved | the loop stops; the postcondition still decides `reached` |
| `stuck` | nothing in the list can make progress | the loop stops; a planner above decides what next |
| `escalate` | the pick is under the confidence floor, **with the pick attached** | your planner, or a human |
| `error` | unknown id, empty answer, transport failure | your caller; never treated as a pick |

Where an episode can stop is equally explicit: `reached`, `done`, `stuck`, `escalate`, `error`,
`blocked` (the surface left the declared hosts), `no_progress` (the same state twice in a row),
`budget`, `dry_run`.

Asking one question instead of two is deliberate: an earlier version asked for the action and the
target separately and produced contradictory answers, picking an element while also declaring the
task done. One question, one answer, one decision.

## Providers, including yours

| name | what it is | notes |
|---|---|---|
| `jev` | TypeSafe Jev, a decision-only model | needs `TYPESAFE_API_KEY`; returns the full probability map |
| `openai` | any OpenAI-compatible endpoint | Ollama, vLLM, LM Studio, a gateway; needs `--model`, no confidence returned |
| `mock` | deterministic keyword overlap | credential-free, for tests, docs and offline development |
| `scripted` | a fixed sequence of answers | assertions in tests |

A chooser is one method, so adding yours does not touch the loop, the safety rails or the
verification:

```python
from jev_pilot.providers.base import Chooser, RawAnswer

class MyChooser(Chooser):
    name = "mine"

    def choose(self, *, goal, state, options, timeout=None):
        answer = my_service(goal, state, [o.as_dict() for o in options])
        return RawAnswer(pick=answer["id"], confidence=answer.get("confidence"))
```

`RawAnswer` is not permission to act. It goes through `apply_policy`, which is where the floor,
the sentinels and the fail-closed rules apply to every provider equally.

## Postconditions

Verification is a list of specs, checked before the first decision and after every action. The
success decision never involves the model.

| spec | passes when |
|---|---|
| `url-contains:TEXT` | the current URL contains TEXT (case sensitive) |
| `url-regex:PATTERN` | the URL matches the pattern |
| `text-contains:TEXT` | the visible text contains TEXT (case and whitespace insensitive) |
| `selector:CSS` | the page has at least one matching element |
| `file-contains:PATH::TEXT` | the file exists and contains TEXT |

Prefer a postcondition the page cannot fake. `text-contains:` is the weakest of them, because
marketing copy that merely mentions the word passes it. A minted order id, a confirmation element
or a file that a download had to produce are all stronger.
## Safety rails

Opt-in by construction, because this drives a real browser on a real machine.

- **Hosts are declared, not inferred.** Navigation is confined to the hosts you name (a `file://`
  page reports the pseudo-host `file`). The moment an observation lands somewhere else, the
  episode stops with `blocked`, that outranks a postcondition which would have passed there, and a
  chain abandons its remaining tasks.
- **Only `click` is allowed** by default. Typing is off until you enable it, and there is no API in
  this library for passwords, tokens or card numbers at all.
- **The browser is isolated.** Its own `--user-data-dir` and its own debugging port, so it cannot
  attach to a logged-in profile.
- **`--dry-run` decides and records, and stops before anything is actuated.** Useful when wiring a
  new surface, and useful for showing what the model would have done.

The rails are checked by the loop, not requested of the model, so a provider that hallucinates a
better plan cannot walk around them.

## Benchmarks over frozen states

A live comparison mostly measures who got luckier with perception. `bench` removes that variable:
one observation, frozen to a file, replayed against several choosers, scored against a known
answer.

```json
{"cases": [
  {"name": "after-plus",
   "category": "calculator",
   "goal": "compute 5 + 3, stopping when the display shows the answer",
   "state": "DISPLAY: 'Display is 5'\nACTIONS ALREADY TAKEN THIS EPISODE: Five, Plus\n[23] Button 'Plus'\n[24] Button 'Equals'\n[28] Button 'Three'",
   "options": [{"id": "23", "label": "Button 'Plus'"},
               {"id": "24", "label": "Button 'Equals'"},
               {"id": "28", "label": "Button 'Three'"}],
   "expect": "Button 'Three'"}
]}
```

`expect` is a label, an `id:`, or a sentinel (`__done__`, `__stuck__`). The report gives you
accuracy next to **coverage**, because a chooser that answers 6 of 10 calls and gets them right is
not the same as one that answers all 10.

```
jev-pilot bench --fixtures examples/bench-calculator.json --chooser jev --repeats 3 \
                --markdown bench.md --out bench.json
```

### The same tasks, two choosers, twice each

The frozen states above isolate a single decision. This runs the whole loop instead: one task
file, one start page, the same postconditions, one arm per chooser, two passes, headless Chrome.

```
jev-pilot run --start https://en.wikipedia.org/wiki/Calculator \
  --task-file examples/wikipedia-chain.json --provider jev --headless

jev-pilot run --start https://en.wikipedia.org/wiki/Calculator \
  --task-file examples/wikipedia-chain.json --provider openai \
  --model <a free open-weights chat model> --base-url <an OpenAI-compatible relay> --headless
```

| chooser | tasks reached | per-decision latency | per-decision cost |
|---|---|---|---|
| `jev` | 6 of 6 | 302 to 939 ms | $0.00027 to $0.00030 |
| a free open-weights chat model | 4 of 6 | 2,733 to 52,000 ms | unmetered, free route |

What this does and does not say. Whenever the chat model answered it picked the same element Jev
picked, every time, so the two agreed on all four decisions it completed. Its two failures were
not wrong picks: they were calls that never returned, both on the same task, at 30 s and 52 s,
from a relay that answered with an empty response where Jev answered in 302 ms at 0.49
confidence. Read it as a reliability and latency result under this harness, not as a ranking of
two models' judgment. Three tasks, one site, two passes: enough to show the shape of the
difference, not enough to generalise past it.
## Traces and reports

Every step is recorded: the exact state sent, the ids offered, the answer, the confidence, the
latency, the tokens and the cost. `jev-pilot report` renders it into a single self-contained HTML
file with no external assets, so it can be attached to a bug report or a pull request.

```
jev-pilot run ... --trace run.jsonl --report run.html
jev-pilot report --trace run.jsonl --out run.html      # render later
```

Use `--no-verbatim-state` when the page content must not be persisted. The decision is still
recorded; only the state text is left out.

## Known limits

- **Perception is the ceiling.** On a Wikipedia article, 200 of 447 candidate links fit the cap.
  What falls past it is invisible, so a correct `__stuck__` can mean "I cannot see it" rather than
  "it is not there". Check `matched_total` in the trace before blaming the model.
- **Confidence is a router, not a gate you set once.** The same ambiguous hop scored 0.47 in one
  run, 0.49 in another and 0.61 in two more. Set the floor from the distribution you observe on
  your own task.
- **No lookahead, no typing, no re-planning.** Those belong to the layer above.
- **The desktop surface is experimental.** It drives a native window through a UI Automation tree
  via cua-driver. It has completed a real four-click episode (see below), but UIA quality varies
  by application and it has had far less use than the browser surface.
- **No screenshot perception.** Text states only, by design: cheaper, auditable and diffable.

## What has been verified

Every claim here was produced by a run, and the command is quoted with it so you can check it
yourself.

| claim | evidence |
|---|---|
| the loop, policy and surfaces work | `pytest`: 147 passed, no credentials, no network |
| the browser surface drives a real browser | `pytest -m live`: launches headless Chrome against a local fixture page and reaches its postcondition |
| the package installs and runs as a package | `uv build`, then install the wheel into a fresh venv with no extras: `jev-pilot selftest` prints PASS |
| CI on three platforms | GitHub Actions on `main`: 3.9, 3.11 on Ubuntu, Windows and macOS, 3.13, and the live browser job, all green |
| a live site, real model, through the CLI | the transcript above: three hops, 1454 / 297 / 295 ms, $0.00086 |
| the same chain through the library API | `python examples/browser_chain.py --provider jev --headless`: 3 of 3 hops reached |
| a real OpenAI-compatible endpoint | `jev-pilot decide --provider openai --model <a chat model> --file examples/decide-request.json` against a local OpenAI-compatible relay: correct pick in 4357 ms |
| the desktop surface, clicking | `jev-pilot run --surface desktop --aumid Microsoft.WindowsCalculator_8wekyb3d8bbwe!App --provider jev --steps 6 --verify text-contains:8`: four real clicks, display verified from the window's own text, exit code 0, $0.000247 |
| the desktop path is covered without a window | `tests/test_desktop_loop.py` drives a scripted driver through a full episode: observe, pick, click by element token, verify from the window's own text |
| the frozen-state bench | the table above, `examples/bench-calculator.json`, three repeats per chooser |
| the same tasks against a second chooser | the table above: 6 of 6 tasks reached against 4 of 6, two passes each |

Still not verified, and said plainly rather than buried: a success rate over a task set larger
than three, and any comparison that would support a claim about judgment rather than reliability
(the note above explains why the loop comparison does not support one). The desktop surface has
had one real episode, in one application, on one platform; issue #2 is that gap.

## Requirements

- Python 3.9 to 3.13 (`[jev]` needs 3.10+).
- Chrome, Chromium or Edge for the browser surface. Headless is supported; set `JEV_PILOT_CHROME`
  to point at a specific binary and `JEV_PILOT_CHROME_ARGS` for extra flags (containers and CI
  usually need `--no-sandbox --disable-dev-shm-usage`).
- [cua-driver](https://github.com/trycua/cua) for the desktop surface, and a Windows session that
  is actually on the interactive desktop.
- No credentials for the core, the browser surface, the mock chooser or the tests.

## Status

`building`, released as `0.1.0` (alpha). Started 2026-09-18. What changed is in `CHANGELOG.md`;
what has been verified, and what has not, is in `docs/findings.md`. Roadmap items live as issues
rather than in this file.

## Where things live

- `src/jev_pilot/`: the library (loop, policy, perception, safety, traces, bench, CLI, surfaces).
- `tests/`: 147 credential-free tests, plus one `live` test that drives a real headless Chrome.
- `docs/`: architecture, perception, decisions, cookbook, findings, parity with the wider ecosystem
  effort, publishing, and a decision log that records which calls were made by a model and which by
  hand.
- `examples/`: a task file, a reference bench fixture, and runnable examples.
- `.github/workflows/`: CI (credential-free), the release lane, and an optional manual live lane.

## Contributing

See `CONTRIBUTING.md`. The short version: the default test suite must pass with no credentials and
no network, a bug fix comes with a test that fails before it, and a performance or accuracy claim
comes with the command that produced it.

## License

MIT. See `LICENSE`.
