# Decision log

Decisions made while building this, with the evidence behind them. Where a decision was handed to
a decision model (TypeSafe Jev, through the `askjev` skill), the verdict, its confidence and the
gate are recorded here, because a machine judgment that is not written down is not auditable.

## 2026-09-18: what to build next after 0.1.0 was green

State sent to Jev: project goal, what was verified, the four open gaps, the pending human
decisions, and the operator's constraints. Four atomic questions in one call (1,041 input tokens,
about $0.00004).

| question | verdict | confidence | gate | what happened |
|---|---|---|---|---|
| which work makes 0.1.0 credible to a stranger | close the desktop click gap | 0.77 (0.82 on the winning label) | act | done: a real four-click cycle now passes against a live window, see `docs/findings.md` |
| is "experimental" honest for the desktop surface with only a dry run verified | yes | noul 0.70 | yes | the label and its caveat stand, and the gap is now closed rather than papered over |
| repository name | vendor-neutral, not Jev-branded | 0.84 (0.89) | act | escalated to the operator anyway: it is an identity call, and the model did not know the operator's attachment to the Jev name |
| publish before or after CI runs on GitHub | undecided | noul 0.53 | **uncertain** | escalated to the operator, not silently resolved. The model declined to pick, which is the correct behaviour for a coin-flip |

Two notes on how this was used:

- the model was not asked anything the tools could answer, and it was not asked to write anything;
- the one question it returned as `uncertain` was not overridden. Under the skill's own rule, an
  uncertain noul means gather more state, ask the operator, or take a reversible default, and
  publishing is not a default worth taking silently.

## Earlier decisions, made without a model

| decision | reason |
|---|---|
| one choice question per step, not an action question plus a target question | two questions produced contradictory answers: an element was picked while "done" was also answered |
| link targets are never sent to the chooser | an early label ended with `-> alpha.html`, which handed the model the answer |
| the postcondition is checked by code, never by the model | the model's `done` is a report, not a proof |
| fail closed when the surface leaves the declared hosts | found live: a click navigated off-site and the episode kept reading a page it had no permission to read |
| keep a credential-free chooser in the library | CI, docs and offline development must work with no key, no network and no spend |
| isolate the browser on its own profile and port | it must never be able to attach to a logged-in profile |
