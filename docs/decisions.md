# Decisions

One question per step, one outcome per answer, and the rules that turn the second into the first
live in `policy.py` rather than in a prompt.

## The question

A single `Choice` over the candidate ids plus two sentinels:

```
__done__   the goal is already achieved in this observation
__stuck__  no candidate in this list can make progress toward the goal
```

Everything else the loop knows (the goal, the page facts, the history) is in the state, not in
the question. The label space is exactly what the harness can execute.

## The outcomes

| outcome | meaning | who handles it |
|---|---|---|
| `act` | a candidate was chosen and is safe to execute | the loop clicks it |
| `done` | the model reports the goal is achieved | the loop stops; the postcondition still decides `reached` |
| `stuck` | nothing in the list can make progress | the loop stops; a planner above decides what next |
| `escalate` | the pick is under the confidence floor, pick attached | the caller, a planner, or a human |
| `error` | no usable answer (unknown id, empty answer, transport failure) | the caller; never treated as a pick |

## Why one question, not two

Asking `next_action` (click / type / done) and `target_element` as separate questions produced
contradictory answers: the model picked `Five` and simultaneously answered "done". Collapsing them
into one choice over the candidate table fixed it immediately. One question, one answer, one
decision.

## The confidence floor

- a floor of `0.0` (the default) accepts every pick;
- a higher floor turns an unsure pick into `escalate` **with the pick attached**, so nothing is
  lost and the caller can route it;
- the floor is not a quality dial. On the same ambiguous hop, the same model scored 0.49 in one
  run and 0.61 in another, so set the floor from the distribution you observe on your own task,
  not from a number that looked reasonable in a demo;
- abstentions (`done`, `stuck`) are never escalated. They are already the signal.

## Confidence, in practice

Deterministic picks sit high (0.94 to 0.99 when the target's text matches the goal's words) and
the same model drops to 0.25 to 0.53 when the state does not prove the action (declaring `done`,
abstaining, or matching a person described rather than named). That is the shape a router needs:
high confidence for the mechanical steps, low confidence exactly where a second opinion is cheap.

## Fail closed

- an id that was not offered: `error`;
- a sentinel: abstention, never an action;
- a sentinel id used as a candidate: rejected before the call is made;
- a transport failure: `error` with the reason, no fabricated pick;
- anything under the floor: `escalate`, never executed.

## Where to put the planner

This layer has no lookahead. When the next hop is not derivable from the current observation it
says so instead of guessing, which is what you want at the bottom of the stack. The layer above
should own subgoals, exploration and recovery: it can accept an `escalate`, re-plan, and re-enter
the loop with a narrower goal.
