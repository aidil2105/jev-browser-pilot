# Cookbook

## Test your own site with a frozen page (no browser)

Capture the state once, freeze it, and check how each chooser answers. This is the cheapest way to
find out whether a decision layer fits a problem at all.

```json
{"cases": [
  {"name": "checkout-with-coupon",
   "goal": "apply the coupon field, then continue",
   "state": "URL: https://shop.example.test/cart\nACTIONS ALREADY TAKEN THIS EPISODE: (none)\nCANDIDATE ACTIONS (answer with one id from this list):\n[3] button 'Apply coupon'\n[4] input 'Coupon code' value=''\n[9] button 'Continue to payment'",
   "options": [{"id": "3", "label": "button 'Apply coupon'"},
               {"id": "4", "label": "input 'Coupon code'"},
               {"id": "9", "label": "button 'Continue to payment'"}],
   "expect": "button 'Apply coupon'"}
]}
```

```
jev-pilot bench --fixtures cases.json --chooser jev --chooser mock --repeats 3 --markdown out.md
```

## Drive a real chain of pages

```json
{"tasks": [
  {"goal": "open the pricing page", "verify": ["url-contains:/pricing"], "steps": 2},
  {"goal": "open the enterprise plan", "verify": ["text-contains:enterprise"], "steps": 2}
]}
```

```
jev-pilot run --start https://example.test/ --task-file tasks.json --provider jev \
              --allow-host example.test --steps 3 --trace run.jsonl --report run.html
```

Tasks run in order on the same browser session, so a chain is just a list. The first task that
leaves the declared hosts stops the whole run (`blocked`), which is deliberate: a chain that
wandered is not a chain you can trust.

## Verify against something a page cannot fake

Prefer a postcondition the page's own advertising cannot satisfy:

```
--verify "file-contains:/tmp/export.csv::row count: 3"     # a real download happened
--verify "selector:.order-confirmation[data-order-id]"     # the state machine advanced
--verify "url-regex:/orders/[0-9]{4,}"                     # an id was minted
```

`text-contains:` is the weakest check: it passes on marketing copy that merely mentions the word.

## Route the unsure steps somewhere useful

```python
episode = run_episode(surface, chooser, goal, verifiers=checks, steps=6, floor=0.6)
if episode.stopped == "escalate":
    step = episode.steps[-1]
    ask_planner(step.decision.pick, step.decision.score if hasattr(step.decision, "score") else None)
```

The escalated `Decision` still carries `pick`, `label`, `confidence` and the full probability map,
so the fallback is an informed one, not a retry.

## Run the same goal against several choosers

```python
from jev_pilot.bench import load_fixtures, render_markdown, run_bench
from jev_pilot.providers import build_chooser

fixtures = load_fixtures("cases.json")
choosers = {"jev": build_chooser("jev"),
            "local": build_chooser("openai", model="llama3.1",
                                   base_url="http://localhost:11434/v1")}
report = run_bench(fixtures, choosers, repeats=3)
print(render_markdown(report))
```

Compare `claimed` accuracy with `coverage`: a chooser that answers 6 of 10 calls correctly and
returns errors on 4 is not the same as one that answers 10 of 10.

## Use it without the browser surface

Any object with `observe()`, `url()`, `probe()`, `act()` and `close()` is a surface. Recorded
sessions, a mobile driver, a local mock server, or a queue of prepared snapshots all fit:

```python
from jev_pilot import run_episode
from jev_pilot.surface import ScriptedSurface

episode = run_episode(ScriptedSurface(snapshots=my_snapshots), chooser, "goal",
                      verifiers=["text-contains:done"], steps=4)
```

## Keep the audit trail

```
--trace run.jsonl            # every step, with the state that produced it
--report run.html            # one self-contained page: steps, confidences, latencies, checks
--no-verbatim-state          # when the page content must not be persisted
```

Attach the report to the ticket when a run fails. It shows the exact state the model saw, which
ends most "the model was wrong" arguments within a minute.
