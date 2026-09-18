# Architecture

Four stages, one model call in the middle, and a hard rule: **every stage that can fail
silently is code.**

```
                 +---------------------------- your code ----------------------------+
                 |                                                                   |
  observe  --->  |  perceive(surface)      -> Snapshot(url, title, text, elements)     |
                 |  candidates(snapshot)   -> [Option(id, label)]                     |
                 |  serialize(...)         -> the exact string the model sees         |
                 +-------------------------------------------------------------------+
                                        |
                                        v
                 +----------------- the decision layer ------------------------------+
                 |  Chooser.choose(goal, state, options) -> RawAnswer                 |
                 |      jev | openai-compatible | mock | scripted                     |
                 |  apply_policy(raw, floor) -> Decision(act|done|stuck|escalate|error)|
                 +-------------------------------------------------------------------+
                                        |
                                        v
                 +---------------------------- your code -----------------------------+
                 |  act(surface, decision.pick)     -> click by stamped id           |
                 |  verify(specs, context)          -> deterministic postconditions   |
                 |  guard(state_signature)          -> no-progress stop               |
                 |  trace(...)                      -> JSONL + HTML report            |
                 +-------------------------------------------------------------------+
```

## Modules

| module | responsibility | why it is separate |
|---|---|---|
| `perception.py` | turn a surface into `Element`s and mint `Option` ids | the rules that decide what is visible are the single biggest cause of failure, so they have one home and one cap |
| `serialize.py` | render the state string | the format is a contract with the model; keeping it in one place stops drift between surfaces |
| `policy.py` | what an answer is allowed to mean | fail-closed rules must not live in prompts |
| `loop.py` | the episode: observe, decide, act, verify, guard | the only place that holds the step budget and the safety checks |
| `surface.py` | the interface the loop drives | lets the same loop drive Chrome, a desktop window, or a scripted replay |
| `browser.py` / `desktop.py` | two real surfaces | actuation details are the parts that break per platform |
| `providers/` | the choosers | swapping the model must not touch the loop |
| `verify.py` | postconditions | the success decision is never the model's |
| `safety.py` | hosts, actions, typing, dry run | the rails are checked by the loop, not asked of the model |
| `trace.py` | audit trail and report | a decision layer you cannot audit is a liability |
| `bench.py` | frozen-state comparison | a live comparison measures perception luck, not decisions |
| `cli.py` | the operator interface | exit codes are a contract for pipelines |

## Data flow of one step

1. `surface.observe()` returns a `Snapshot`. The browser surface runs its serializer inside the
   page and stamps each kept element with `data-jev-idx`.
2. The loop first asks the postconditions: if they already hold, the goal is done with **zero**
   model calls.
3. `snapshot.options()` mints the candidate table. Ids are element ids (snapshot-local).
4. `build_state(...)` renders the state: URL, title, visible text, the actions already taken this
   episode, the perception-cap notice, and the candidate list with **no link targets**.
5. The loop asks for `safety.check_url(snapshot.url)`, then the chooser answers with an id.
6. `apply_policy` maps that answer onto an outcome; anything unknown or under the floor stops the
   episode rather than acting.
7. The action click addresses the stamped element, so the element clicked is the element described.
8. One observation after the action serves verification and the no-progress guard.
9. The trace records the state verbatim (unless disabled), so the failure can be read afterwards.

## Invariants

- The model may only return an id that was in the candidate table.
- An episode can only be `reached` because a postcondition passed, never because a model said so.
- Nothing outside the declared hosts is read or acted on; landing outside stops the episode.
- Every step is either recorded in the trace or the trace is explicitly disabled.
- A failed chooser call is `error`, never a plausible default.
