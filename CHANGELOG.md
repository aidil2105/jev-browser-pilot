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
- 139 credential-free tests, one live browser test, CI on Python 3.9 to 3.13, and an optional
  manual live lane.
- Documentation: architecture, perception, decisions, cookbook, findings, parity.

### Fixed during development

- a click that navigated outside the declared hosts was only caught before the next action, so an
  episode could read a page it had no permission to read. Episodes now stop with `blocked` on any
  observation outside the hosts, before verification, and a chain abandons its remaining tasks.
- `bench` ignored `--base-url` and `--api-key-env`, so an OpenAI-compatible chooser could not be
  built on that command at all.
- the desktop surface could not start through the CLI: the safety policy was derived from a start
  URL, and a native window has no URL. A hostless policy is now allowed for that surface, with the
  action allow list and the typing switch still enforced.
- `--dry-run` decided and stopped without reporting the step, which hid the only output a dry run
  exists to show.
- `apply_policy` required `confidence` even for transport-failure reporting; it is now optional.
- the OpenAI-compatible parser failed on bodies with two concatenated JSON objects, which real
  relays produce.
- the default browser profile directory was created inside the working directory, which polluted a
  checkout. It now defaults to the system temp directory (`JEV_PILOT_PROFILE_DIR` overrides it).
- the desktop surface reported the first text label in a window as its text, which is usually the
  window title, so a `text-contains:` postcondition silently inspected the wrong string. It now
  reports the window's text labels joined, value-like labels first.

### Verified before release

- `--api-key-env`, documented for the OpenAI-compatible chooser, was also handed to the Jev chooser,
  so a bench that mixed both authenticated Jev with the wrong key and every Jev call came back
  unanswered. Only the OpenAI-compatible provider takes endpoint flags now.
- `pytest`: 139 tests, no credentials, no network; `pytest -m live`: one real headless browser run.
- Python 3.9, 3.11 and 3.13.
- `uv build`, then install the wheel into a fresh virtual environment with no extras and run
  `jev-pilot selftest` from the installed console script.
- Three live Wikipedia hops through the CLI with a real decision model, and the same chain through
  the library API.
- One real OpenAI-compatible endpoint, and a two-chooser bench over the frozen fixtures.
- One real attach to a native window (dry run).
