# jev-browser-pilot

## Project

A public, dependency-light Python library and CLI that puts a decision-only model
(TypeSafe Jev, or any OpenAI-compatible model) in the driving seat of a browser or
desktop loop, while the code keeps every part that can fail silently: observation,
content, actuation and verification. The point is a step that costs a fraction of
a cent and answers in a few hundred milliseconds, with a confidence signal the
caller can route on.

## Key files

- `README.md`: what this is, status, how to run it, results. Read this first.
- `src/jev_pilot/cli.py`: the entry point (`jev-pilot run|decide|bench|selftest`).
- `src/jev_pilot/loop.py`: the episode runner and the decision policy.
- `src/jev_pilot/providers/`: the chooser implementations (`jev`, `openai`, `mock`).
- `docs/findings.md`: measured numbers, including the failures.
- `AGENTS.md`: this file.

## Conventions for any AI agent in this folder

- Work only inside this folder. New files go in a sensible subfolder, not loose at the root.
- Read `README.md` before changing anything, and update its Status line and Log when you finish.
- Set the working directory to this folder for every command. Do not run project commands from the home folder.
- Ask before deleting or overwriting a file you did not create.
- Scratch and temp output goes in `scratch/`, dated `YYYY-MM-DD` if it is worth keeping.
- File and folder names are kebab-case.
- Say plainly what you changed and what you verified. No filler.
- If a task needs a decision the owner has not made, ask instead of guessing.

## Extra rules for this project

- This repo is public. No API keys, tokens, personal paths, or scraping targets in
  source, tests, fixtures, docs, traces or commit messages. Credentials come from
  the environment only, and `.env` is git-ignored.
- Tests must pass with no credentials and no network: the default suite runs
  against the mock provider and injected fake transports. Anything that needs a
  real browser or a live endpoint carries the `live` pytest marker and is
  deselected in CI.
- Documentation states measured results and their caveats. No invented numbers,
  no benchmark claim without the fixture and the command that produced it.
