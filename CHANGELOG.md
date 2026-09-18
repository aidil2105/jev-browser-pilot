# Changelog

All notable changes to this project. Format follows Keep a Changelog; versioning follows SemVer.

## [0.1.0] - 2026-09-18

First release.

### Added

- `run_episode`: the observe, decide, act, verify loop, with a step budget, an action history in
  the state, a no-progress guard, and an opt-in dry run.
- `policy.apply_policy`: the fail-closed decision rules (`act`, `done`, `stuck`, `escalate`,
  `error`), including the confidence floor and rejection of unknown ids.
- Providers: `jev` (TypeSafe Jev), `openai` (any OpenAI-compatible endpoint), `mock` (deterministic
  keyword overlap, credential-free) and `scripted` (tests).
- Surfaces: `BrowserPilot` (Chrome/Chromium/Edge over CDP, own profile and port) and
  `DesktopPilot` (UI Automation through cua-driver's CLI, experimental), plus `ScriptedSurface`.
- Perception: `DomRules` (root, interactive, exclude and skip rules, cap, stamping) and
  `elements_from_uia` for accessibility trees, with truncation reported to the model and the log.
- `verify`: deterministic postconditions (`url-contains`, `url-regex`, `text-contains`, `selector`,
  `file-contains`) with an explicit no-live-page result for selector checks.
- `safety.SafetyPolicy`: declared hosts, allowed actions, typing off by default, dry run, step cap,
  and a fail-closed `blocked` stop when the surface leaves the declared hosts.
- `trace`: a JSONL recorder and a self-contained HTML report with per-step latencies and
  postcondition results.
- `bench`: frozen-state comparison across choosers with accuracy, coverage, latency, token and cost
  aggregates, plus markdown rendering.
- CLI: `run`, `decide`, `bench`, `report`, `selftest`, `version`, with documented exit codes.
- 127 credential-free tests, one live browser test, CI on Python 3.9 to 3.13, and an optional
  manual live lane.
- Documentation: architecture, perception, decisions, cookbook, findings, parity.

### Fixed during development

- a click that navigated outside the declared hosts was only caught before the next action, so an
  episode could read a page it had no permission to read. Episodes now stop with `blocked` on any
  observation outside the hosts, before verification.
- `apply_policy` required `confidence` even for transport-failure reporting; it is now optional.
- the OpenAI-compatible parser failed on bodies with two concatenated JSON objects, which real
  relays produce.
