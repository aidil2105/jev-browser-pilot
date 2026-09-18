# Findings

Measured numbers, with the harness that produced them and the caveats that go with them. Nothing
here is a vendor claim reproduced as fact.

## 1. The decide step is where the seconds are (frozen-state bench)

One real Windows Calculator window was captured through a UI Automation tree (39 actionable
elements), frozen to a fixture, and five states were built from it: start, after `Five + Plus`,
after `Five + Plus + Three`, at the answer, and one goal no element in the table can serve. Every
chooser saw a byte-identical state string. No capture, no actuation, so the latency is the decision
alone.

| chooser | correct | median | range | tokens in |
|---|---|---|---|---|
| Jev | 15/15 | 350 ms | 258 to 812 ms | 20,892 |
| a mid-tier chat model | 7/10 | 3,536 ms | 1,357 to 21,757 ms | 5,200 |
| a smaller free model | 5/10 | 7,318 ms | 1,225 to 23,778 ms | 6,148 |

Cost of the whole Jev arm: $0.000877.

Caveats, all of them material:

- the two chat models ran through a local relay whose failures were transport, not judgment
  (an upstream 402 masked as a 503, and empty completions when the token cap was eaten by
  reasoning tokens). The mid-tier model was 7/7 correct on the calls it managed to answer; its
  other three calls returned nowhere. Read the table as latency and coverage, not as accuracy;
- the decision is small (39 labeled elements, no screenshots, no tool schemas). A heavier decision
  costs more for every chooser, so the ratio is not a constant;
- the same hop in a later run scored differently (see the confidence note below), which is why the
  repeats are reported rather than a single number.

The Jev arm's telling detail: on the goal nothing could serve, it answered `__stuck__` all three
times at 0.46 to 0.53 confidence, while the other choosers used the same state to pick a
plausible-looking wrong element or to declare the goal done.

## 2. Three hops on a live site, through this library's CLI

```
jev-pilot run --start https://en.wikipedia.org/wiki/Calculator \
              --task-file examples/wikipedia-chain.json --provider jev --headless
```

| hop | goal | pick | confidence | latency |
|---|---|---|---|---|
| 1 | open the article about the slide rule | `a 'slide rule'` | 0.95 | 1454 ms |
| 2 | open the article about William Oughtred | `a 'William Oughtred'` | 0.99 | 297 ms |
| 3 | open the article about Richard Delamain | `a 'Richard Delamain'` | 0.47 | 295 ms |

3/3 reached, one decision per hop, $0.00086 for the session, headless, hosts locked to
`en.wikipedia.org`.

The perception cap was hit on every page (200 of 447, 200 of 265, 200 of 258 candidates shown) and
it did not matter here, because the target was inside the cap. That is luck, not a guarantee.

## 3. Confidence is a router, not a gate

Hop 3 above is the interesting one. It is the only hop whose goal describes a person instead of
nearly quoting the link text, and it is the only hop with low confidence: 0.47 here, 0.49 in an
earlier run, and 0.61 to 0.62 in two runs of the same hop after a refactor. A floor of 0.6 would
have escalated it in some runs and accepted it in others.

The same shape appears in the frozen bench: 0.94 to 0.99 on unambiguous picks, 0.25 to 0.33 on the
correct `done` call (the observation does not prove the arithmetic; the display does), 0.46 to 0.53
on correct abstentions. Treat the number as a routing signal and set the floor from your own
distribution.

## 4. Perception failures look like model failures

The first Wikipedia attempt failed with `__stuck__` at 0.73 confidence on both hops. The element
list, capped at 70 with no filtering, held only the lead paragraph's links and navbox items in DOM
order; the goal link sat at position 107 of 487 matching anchors. The model was right about the
question it was actually asked. Excluding tables, navboxes, infoboxes, reference lists, thumbnails,
edit affordances and bare footnote markers, then capping at 200, turned the same task into a pass.

This is the fourth time in this line of work that a failure read as a model failure and was a
harness failure. Check the state before you check the model.

## 5. A safety gap found by a live run

Running the naive `mock` chooser against Wikipedia, it picked a reference title containing the
goal's words and left the site. The episode continued, observing a page on a host the caller never
allowed, because the host check only ran before an action, not after an observation.

Fixed the same day: any observation outside the declared hosts now stops the episode with
`blocked`, outranks a postcondition that would have passed there, and abandons the remaining tasks
in a chain. Re-run: the same mock sequence stops at the off-site navigation with exit code 1.

## 6. Cost model

Input is $0.042 per million tokens; output is free because the model never generates tokens. A
decision here costs 1.4k to 2.4k input tokens, so roughly $0.0003 per step, or about $0.002 for a
40-step episode. That is what makes per-page repetition and cron cadence affordable at all.

## 7. What the numbers do not show

- No head-to-head against a frontier model driving the same live tasks through this harness. The
  bench isolates the decision; the loop comparison is not run yet.
- No measurement of success rate over a task set, only over hops whose target was visible.

## 9. A full desktop click cycle (2026-09-18)

The experimental desktop surface has now completed a real episode on a real window:

```
jev-pilot run --surface desktop \
  --aumid Microsoft.WindowsCalculator_8wekyb3d8bbwe!App \
  --goal "compute 5 + 3 and stop when the display shows the answer" \
  --verify "text-contains:8" --provider jev --steps 6
```

| step | pick | confidence | latency |
|---|---|---|---|
| 1 | `Button 'Five'` | 0.98 | 789 ms |
| 2 | `Button 'Plus'` | 1.00 | 302 ms |
| 3 | `Button 'Three'` | 1.00 | 299 ms |
| 4 | `Button 'Equals'` | 0.99 | 285 ms |

Reached, exit code 0, four decisions, median 300 ms, $0.000247. One click per step, delivered in
the background, and the postcondition read from the window's own text rather than asked of the
model.

The first attempt at this failed, and the failure was mine rather than the model's: the surface's
`text` was the first text label in the tree, which is the window title, so `text-contains:8` was
checking the word "Calculator". The click sequence itself was correct, which the trace shows
(`[8] Text 'Display is 8'` in the state at step 5, followed by a `done` at 0.82 confidence). Fixed
by reporting the window's text labels joined, value-like labels first, and covered by tests.

## 8. A second real chooser on the frozen fixtures

The shipped fixture (`tests/fixtures/calc-frozen.json`, four states) run through two choosers:

```
jev-pilot bench --fixtures tests/fixtures/calc-frozen.json \
  --chooser mock --chooser openai:cl/deepseek/deepseek-v4-flash \
  --base-url http://127.0.0.1:20128/v1 --api-key-env NINE_ROUTER_API_KEY
```

| chooser | correct | accuracy | answered | median | range |
|---|---|---|---|---|---|
| mock (keyword overlap) | 1/4 | 25% | 4/4 | 0 ms | 0 to 0 ms |
| a mid-tier chat model | 3/4 | 75% | 3/4 | 3991 ms | 3575 to 22067 ms |

Read this as a sanity check on the fixture and the harness rather than as a model comparison: four
states is far too small to rank anything, the keyword chooser is deliberately naive (it fails the
states whose answer is not in the goal's words), and the chat model's single unanswered call is a
transport failure, not a wrong answer. What it does show is that the same frozen states can be
replayed across choosers with honest accounting of coverage next to accuracy.

