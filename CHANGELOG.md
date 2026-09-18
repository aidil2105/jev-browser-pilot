# Changelog

All notable changes to this project. Format follows Keep a Changelog; versioning follows SemVer.

## [0.1.2] - 2026-09-18

### Fixed

- The install section on the project page said the package was not on PyPI, on PyPI. The
  description of a release is the README inside the uploaded artifact, so a documentation change
  only reaches pypi.org with a new version. This is that version.

### Added

- The first release on PyPI. `0.1.1` was uploaded by `.github/workflows/publish.yml` through
  trusted publishing, and `pip install jev-browser-pilot` in a clean environment pulls it
  (`jev-pilot version` reports 0.1.1, `selftest` prints PASS).

## [0.1.1] - 2026-09-18

### Added

- `docs/publishing.md` and `.github/workflows/publish.yml`: releases are built, installed from
  their own artifacts and uploaded to PyPI through trusted publishing, with no token in the repo.
- `tests/test_desktop_loop.py`: the desktop surface driven by a scripted driver, so the whole
  desktop path (observe, pick, click by element token, verify from the window's own text) runs in
  the credential-free suite instead of only by hand.
- A live two-chooser loop comparison in the README: the same three tasks, the same postconditions,
  two passes per chooser, with the coverage difference stated next to the latency difference.
- `examples/bench-calculator.json`: the reference fixture behind the README's benchmark table, so
  those numbers can be reproduced from the repository instead of quoted.
- The manual live lane was dispatched once on a GitHub runner with the key as a repository secret,
  and reached all three hops (277 / 124 / 127 ms, $0.00086), so the lane is known to work instead of
  merely being configured.
- 147 credential-free tests (139 before this release).

### Changed

- The window text of a native surface now includes item roles (`listitem`, `treeitem`,
  `dataitem`), so a file list, a tree or a table is readable by a postcondition. Menu chrome is
  still excluded.

### Fixed during development

- `__version__` was a literal, so a wheel built as 0.1.1 still reported `0.1.0` and every trace
  recorded the wrong version. It now reads the installed metadata, and a test fails loudly when the
  installed metadata and `pyproject.toml` disagree.
- `pip install jev-browser-pilot` was in the README while the package was not on PyPI. The install
  section now gives the git form, and both forms were run anonymously in clean environments.
- `bench` wrote its `--out` and `--markdown` files after printing, so piping it into `head` closed
  stdout, killed the process mid-print and left the artifacts unwritten. Artifacts are written
  first, and a closed pipe exits cleanly instead of dumping a traceback.

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
