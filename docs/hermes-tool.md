# Using the decision step from an agent

The library is useful to a host agent for exactly one thing: the bounded pick. This page is how a
Hermes agent borrows that step without adopting the loop.

The plugin ships in this repository at [`hermes-plugin/jev-decide/`](../hermes-plugin/jev-decide/):
one tool, `jev_decide`, that takes a candidate list you already built and returns one typed answer.

```
your tooling observes  ->  jev_decide picks  ->  your tooling acts  ->  your tooling verifies
```

Perception, content, actuation and verification stay yours. The tool cannot click, cannot type and
cannot invent an id.

## Install

1. The tool runs the `jev-pilot` CLI, so it needs the CLI. One line, from PyPI:

   ```
   uv tool install jev-browser-pilot        # or: pip install --user jev-browser-pilot
   ```

   If you would rather point at a checkout, set `JEV_PILOT_BIN` in `$HERMES_HOME/.env` to the
   command (for example `JEV_PILOT_BIN=C:/path/to/venv/Scripts/jev-pilot.exe`). The tool resolves
   it before falling back to `PATH`.

2. Copy the plugin directory into place and enable it:

   ```
   cp -r hermes-plugin/jev-decide "$HERMES_HOME/plugins/jev-decide"
   hermes plugins doctor jev-decide        # validates the manifest and the registration
   hermes plugins enable jev-decide
   ```

   Enabling does not grant tool-override rights, and this plugin does not ask for them: it adds a
   tool, it does not intercept yours.

3. Confirm the model can see it. The tool registers only when the CLI resolves, so a machine
   without the library shows no dead tool:

   ```
   hermes plugins list                     # jev-decide | enabled | 0.1.0 | user
   ```

   `hermes chat -q` prints `Warning: Unknown toolsets: ... jev_decide` on some versions. That is a
   name-registry note about plugin-provided toolsets, not a failure: the tool loads and dispatches.
   It appears for bundled plugins with their own toolset name too.

## The tool

| argument | meaning |
|---|---|
| `goal` | What the episode is trying to do, in one sentence, specific enough to tell a right pick from a wrong one. |
| `options` | The candidates you can execute: `{"id": ..., "name": ...}`. The id is what you get back; the name is what the model sees, so describe the element the way a person reading a screenshot would. |
| `state` | What the model can see, as text: the page or window, the relevant text, and the actions already taken. |
| `confidence_floor` | Below this, the answer is `escalate` with the pick attached rather than `act`. 0.6 is a reasonable start. |
| `provider`, `model` | `jev` by default, or any OpenAI-compatible endpoint through `openai` plus a model name. |

The answer is one JSON object:

```json
{"ok": true, "decision": {"outcome": "act", "pick": "100", "label": "a 'slide rule'",
                          "confidence": 0.8, "reason": "picked", "provider": "keyword",
                          "model": "keyword-overlap-1", "ms": 372, "cost_usd": 0.00031}}
```

## Handling the five outcomes

| outcome | what it means | what to do |
|---|---|---|
| `act` | The model picked a candidate and is confident enough. | Execute exactly that id, then verify with your own postcondition. |
| `escalate` | Below your floor. `pick` is still attached. | Do not execute it silently. Re-observe, narrow the candidates, or hand the step to your planner. |
| `done` | The goal looks already achieved. | Verify it yourself before stopping; the model cannot check anything. |
| `stuck` | No candidate can advance the goal. | Stop the episode and change the page, the candidate list, or the plan. |
| `error` | The decision never happened (transport, credential, timeout). `ok` is false, `pick` is null, `reason` says why. | Stop and report it. Never substitute a guess: `pick` being null is the point. |

## Enumerating candidates

The candidate list is your job, and the ids must be something you can act on. In the Hermes browser
tool, one `js(...)` call gives both:

```js
(() => {
  const nodes = [...document.querySelectorAll('a[href], button, [role=button], [role=link]')];
  const seen = new Set(), out = [];
  nodes.forEach((el, i) => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;                       // invisible
    const label = (el.innerText || el.getAttribute('aria-label') || el.title || '').trim();
    if (!label) return;
    const key = label.toLowerCase() + '|' + i;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({id: String(i), name: (el.getAttribute('role') || el.tagName.toLowerCase()) + " '" + label.slice(0, 80) + "'"});
  });
  return JSON.stringify({url: location.href, title: document.title, candidates: out.slice(0, 200)});
})()
```

Then the state is the URL, the title, the page text you can read, the actions already taken, and
one line naming what "done" would look like. Feed the ids straight back to `click_at_xy` after
mapping the chosen id back to its element, and verify with a URL or text check of your own.

## Cost

One decision is one small call: about 300 ms and $0.0003 with Jev on the measured task set, against
seconds and a full turn for asking the same question of the agent's own model. That is the entire
argument for the tool: the pick is the cheap part of the loop, and the expensive parts stay where
they belong.

## What was verified here

- `hermes plugins doctor jev-decide`: runtime discovery, manifest parsing, import and registration
  all pass; one tool, no hooks.
- A live `hermes chat -q` run in which the agent called `jev_decide` through the ordinary tool
  dispatch and received `{"outcome": "act", "pick": "100", ...}`.
- Nineteen tests in `tests/test_hermes_plugin.py`, all credential-free: the round trip through the
  real CLI with the keyword chooser, the floor escalating with the pick attached, and every
  fail-closed path (missing CLI, silent CLI, non-JSON output, bad options, reserved sentinels,
  duplicate ids, unknown keys dropped).
- Two bugs worth recording, both caught by those tests rather than in production: the request field
  is `label`, so forwarding `name` turned every candidate into its bare id and produced `stuck`
  instead of an error; and `shlex.split` in posix mode mangles Windows paths, so a
  `JEV_PILOT_BIN` pointing at `C:\\...` resolved to nothing.
