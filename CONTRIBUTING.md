# Contributing

Small, focused changes with real evidence. This project is about a decision layer, so the bar for
a claim is a measurement, not an argument.

## Setting up

```
git clone https://github.com/aidil2105/jev-browser-pilot
cd jev-browser-pilot
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,jev]"      # Windows
# .venv/bin/python -m pip install -e ".[dev,jev]"        # macOS / Linux
```

## The test contract

```
pytest                       # 171 tests, no credentials, no network
pytest -m live               # also drives a real headless Chrome against a local fixture
```

- The default suite must pass with **no credentials and no network**. Anything that needs either
  carries the `live` marker and is deselected in CI.
- New providers get an injected fake transport, so no test ever spends money or depends on an
  endpoint being up.
- A bug fix comes with a test that fails before the fix. The safety fix in `loop.py` and its two
  tests are the reference example.

## What a good change looks like

- one idea per pull request, with the reasoning in the description;
- state what you ran and what it returned, quoted from the real output;
- if you changed perception or the policy, include the before and after on a real fixture;
- no new dependency unless the standard library genuinely cannot do it;
- no secrets, personal paths, or scraping targets in code, tests, fixtures, docs or commit
  messages. Credentials come from the environment only.

## Style

- Python 3.9 compatible, standard library first, `from __future__ import annotations`;
- type hints on public functions, dataclasses for data;
- comments explain why, not what. If a rule exists because of a failure, say which failure;
- prose in docs states the caveat next to the number. Numbers without their harness are noise.
