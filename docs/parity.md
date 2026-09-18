# Parity with the wider effort

Several teams are converging on the same architecture: a model that picks among candidates your
code built, with everything else in code. This page records what this library shares with that
work and where it differs, so nobody has to reverse-engineer the relationship. Status as of
2026-09-18.

## cua (trycua/cua)

| artifact | what it proposes | relationship |
|---|---|---|
| PR #3914, `suggest_action` | an optional driver tool where a decision model returns the next element index plus confidence, off unless the key is set | same idea, different boundary: theirs is a driver-side tool, this library keeps the model outside the driver and provider-agnostic |
| PR #3916, `jev-use` recipe | a runnable client recipe: the application builds complete candidate actions, the model selects one id, the caller validates it before the driver executes | the same contract, implemented here as a reusable library with providers, safety rails, traces and verification |
| RFC #3931, perception extension | an opt-in perception extension, with Jev credentials, prompts, retry policy and provider logic explicitly kept **outside** the driver | this library agrees and takes the same position |
| PR #3943, `cua-perception` (draft) | offline OCR and icon regions through an optional extension | out of scope here: this library is text-state only, and says so in `docs/perception.md` |

Shared positions worth stating plainly:

- the application owns the candidate table, and the model may only return an id from it;
- the model never invents tool names, coordinates, refs, arguments or text;
- unknown, stale or denied ids fail closed;
- the caller verifies completion independently, never from the model's answer or a screenshot.

## Hermes Agent

| artifact | what it proposes |
|---|---|
| issue #113850 | Jev as an **optional** System One lane for computer use, explicitly "do not replace the planner", with typed questions (`ACTION`, `TARGET`, `NEEDS_VISION`, `DONE`) and a backend order of rules, then reranker, then fast aux model, then the decision model |
| PR #114365 | wires that lane into a `decide` action with fail-open behaviour |

Two notes from this library's own measurements that are relevant to that design:

- the issue's advice to keep questions small and factorized (action, then target) is the opposite
  of what worked in a browser context here: two questions produced contradictory answers
  (picking an element while also answering "done"), and one choice over a single candidate table
  fixed it immediately. The right factoring probably depends on whether the candidate space is
  bounded by code (this library) or reasoned about by the model (a desktop planner);
- the recommended order, rules then reranker then fast model then decision model, matches this
  library's shape exactly: the model is last, optional, and fail-open.

## What this library adds that the others do not (yet)

- a provider interface, so the decision layer is not tied to one model vendor, plus a
  credential-free `mock` chooser that makes the whole loop testable in CI;
- declared-host safety with a fail-closed stop the moment the surface leaves them;
- deterministic postconditions as first-class inputs, checked before and after every action;
- JSONL traces plus a self-contained HTML report per run;
- a frozen-state bench so comparisons measure decisions instead of perception luck.

## What it does not do

- no screenshot or OCR perception path (text states only);
- no multi-agent orchestration and no planner: it is the bottom of the stack;
- no driver-side packaging: it drives Chrome over CDP and, experimentally, a desktop window
  through cua-driver's CLI.
