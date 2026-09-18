# Findings

Measured numbers, with the harness that produced them and the caveats that go with them. Nothing
here is a vendor claim reproduced as fact.

## 1. The decide step is where the seconds are (frozen-state bench)

Five states were built from one real Windows Calculator window captured through a UI Automation
tree: start, after `Five + Plus`, after `Five + Plus + Three`, at the answer, and one goal no
element in the table can serve. The element tables are verbatim; the display value and the action
history reconstruct what a live loop would have seen. Every chooser got a byte-identical state, and
there is no capture and no actuation involved, so the latency is the decision alone.

```
jev-pilot bench --fixtures examples/bench-calculator.json \
  --chooser jev --chooser mock --chooser openai:<a chat model> --repeats 3
```

| chooser | correct | accuracy | answered | median | range | in tokens | cost |
|---|---|---|---|---|---|---|---|
| `jev` | 15/15 | 100% | 15/15 | 349 ms | 277 to 870 ms | 9,354 | $0.000393 |
| `openai`, a mid-tier chat model | 12/15 | 80% | 12/15 | 2,858 ms | 4 to 15,328 ms | 3,840 | not metered |
| `mock`, keyword overlap | 3/15 | 20% | 15/15 | 0 ms | 0 ms | 0 | free |

Per state, the `jev` pick and its confidence (first repeat of each):

| state | expected | `jev` picked | confidence | latency |
|---|---|---|---|---|
| start | `Button 'Five'` | `Button 'Five'` | 0.99 | 870 ms |
| after-plus | `Button 'Three'` | `Button 'Three'` | 1.00 | 810 ms |
| after-three | `Button 'Equals'` | `Button 'Equals'` | 0.93 | 727 ms |
| at-answer | `__done__` | done | 0.78 | 735 ms |
| unreachable | `__stuck__` | stuck | 0.99 | 845 ms |

What to take from it, and what not to:

- the chat model's three misses are **not wrong answers**. All three are the same transport failure
  on the `unreachable` state (a relay 503 with an empty body, which is what a reasoning model
  produces when its token budget is spent on reasoning). Its accuracy on the calls it answered is
  12/12. The honest comparison here is latency and coverage, not judgment;
- `jev` never returned an error, never picked wrong, and its confidence splits in the shape a router
  needs: 0.93 to 1.00 on the four mechanical states, 0.78 on the one that depends on reading a
  display rather than matching a word;
- `mock` passes only the state whose answer is not a click at all, which is what a naive keyword
  overlap should do. It is a fixture for offline work, not a baseline to beat;
- this is five states, three repeats. It is enough to check the harness and to see the shape of the
  cost and latency difference. It is not enough to rank models, and nothing here justifies a general
  claim about any chooser's accuracy.

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

## 8. A full desktop click cycle on Windows Calculator (2026-09-18)

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

## 9. A second real desktop application: File Explorer (2026-09-18)

One application is enough to call the desktop surface real and not enough to call it tested. This is
the second: a File Explorer window on this repository's directory, attached by pid, driven through
two navigations.

```
jev-pilot run --surface desktop --attach-pid <explorer pid> \
  --task-file examples/desktop-explorer.json --provider jev --steps 6
```

| goal | pick | confidence | latency | postcondition |
|---|---|---|---|---|
| open the docs folder in this window | `ListItem 'docs'` | 0.97 | 926 ms | `text-contains:hermes-tool.md` passed |
| open the evidence folder, which is inside docs | `ListItem 'evidence'` | 0.97 | 393 ms | `text-contains:live-comparison` passed |

Both tasks reached, one click each, $0.000525 in total, exit code 0. The postconditions were chosen
so they could not pass by accident: `hermes-tool.md` does not exist outside `docs`, and
`live-comparison` exists only inside `docs/evidence`. The word `docs` was already in the window text
before any click, so it would have proved nothing.

What is different from the Calculator window. Explorer's tree is 163 elements of a different shape
(70 `Edit`, 22 `Button`, 17 `ListItem`, 14 `TreeItem`), the content lives in item roles rather than
in text labels, and what a postcondition reads is a file name. Including item roles in the window
text is what makes a file list verifiable at all.

Two harness faults had to be fixed before the episode could run at all, and neither looked like a
model problem:

- **Attaching by pid alone could not work.** cua-driver 0.28 requires an integer `window_id` for
  `get_window_state`, and nothing resolved one, so the first observation failed with the driver's
  own complaint. The surface now asks `list_windows` for the pid's window when no id was passed.
- **A driver refusal became a traceback.** The tolerant parser called `raw_decode` inside an `if`
  and let the exception escape, so a clear sentence ("Missing required integer field window_id")
  surfaced as a `JSONDecodeError` and the driver's message was lost. Refusals are reported now, and
  a UTF-8 BOM on the driver's stdout is stripped, since `json.loads` rejects one outright.

Still thin, and the README says so: two applications, one platform, one episode each.

## 10. A larger frozen set, and where the decision layer actually loses (2026-09-18)

The first frozen set was five states from one Calculator window, and Jev answered all fifteen replays
correctly. That is a set built to its shape. This one is built to the pages instead: 27 states from
eight live Wikipedia articles, each state paired with a goal, and every page contributing two
abstention shapes (the goal is already satisfied, and the goal cannot be reached from here).

Ground truth comes from the DOM, not from a model. `scripts/capture-bench.py` reads each candidate's
link target, which the harness knows and the chooser never sees, and sets the case's answer to the
element whose `href` leads to the article the goal names. Where a page links the same article twice
the extra links are dropped, so a case has exactly one right answer.

| chooser | correct | picks | abstentions | answered | median | cost |
|---|---|---|---|---|---|---|
| `jev` | 25/27 (93%) | 9/11 | 16/16 | 27/27 | 316 ms | $0.0070 |
| qwen3-30b-a3b-instruct (30B MoE, open weights) | 10/27 (37%) | 10/11 | 0/16 | 27/27 | 1,339 ms | about $0.01 |
| llama-3.1-8b-instruct (8B, open weights) | 9/27 (33%) | 9/11 | 0/16 | 27/27 | 1,146 ms | about $0.01 |

The open models match Jev on picks and never abstain: 0 of 16 each, on states where the goal was
already satisfied or unreachable from the page. That is the whole of the accuracy gap.

**Where it loses, precisely.** Both misses are name matching, not navigation:

- `william_oughtred->richard_delamaine`: the article's title is *Richard Delamaine*, the page's link
  text is *Richard Delamain*. One letter. Jev picked something else. The same hop came in at
  0.49 confidence in the live task-set run, the lowest of that chain, so the model was already
  signalling doubt here.
- `richter_scale->logarithm`: the link to *Logarithm* on the Richter scale page is labelled
  "logarithmic", so the goal's word does not appear in the label. Jev answered `stuck`, which is a
  defensible reading of a goal it cannot match.

**What it never got wrong is abstention.** Sixteen of sixteen: it never clicked when the goal was
already satisfied, and never claimed progress was possible when the page could not reach the target.
For a layer whose job is to keep a wrong answer from being executed, that is the column that matters.

**Coverage failures worth recording as such.** Two free-tier arms could not be measured: OpenRouter's
free models refused with `429 Rate limit exceeded: free-models-per-day-high-balance`, and the local
relay's free route answered 26 of 27 calls with `503 ... empty response content`. The two open-weights
arms in the README are the same models at their cheap paid rates, about a cent an arm, so the
comparison exists rather than being a footnote about rate limits.

**A bug this set exposed, in the harness rather than the model.** The first run reported Jev at 16/27
while its every pick was correct: the bench compares `expect` against a *label* unless the value is a
sentinel or `id:`-prefixed, and the captured fixture carried bare ids. Fixed on both sides, the fixture
now writes `id:<id>` and the bench reads a bare value that matches one of its own option ids as an id,
with a test. The audit script checks the encoding, because a benchmark that silently scores a correct
run as a total miss is worse than no benchmark.

