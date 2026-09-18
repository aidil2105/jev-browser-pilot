"""Handler for the jev_decide tool.

It runs `jev-pilot decide` and hands back whatever the policy decided. The wrapper deliberately
does very little: it validates the request the model produced, passes it through, and reports
failures as failures. Every judgement (the prompt, the labels, the confidence floor, the
sentinels, the refusal to answer when a transport call dies) belongs to the library, so a fix
there fixes this too.

Two rules this file exists to keep:

- A transport or configuration failure is reported as an error with its reason. It never becomes
  a pick. Returning a confident-looking id when the decision never happened is the one failure
  mode a decision layer cannot have.
- `TYPESAFE_API_KEY` is read from `$HERMES_HOME/.env` when it is not already in the environment,
  because the agent process does not necessarily export it and the key must never be logged.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TIMEOUT_S = 60.0
MAX_OPTIONS = 200
MAX_STATE_CHARS = 20000

# The library's request field is `label`, not `name` (Option.from_dict reads `label` and falls
# back to the id). The tool exposes `name` because that is what the label is, and maps it here:
# passing `name` straight through made every label a bare id, which scores zero overlap and comes
# back as `stuck` rather than as an error. Accept either key so a caller who read the library
# docs is not punished for it.
_OPTION_FIELDS = ("id", "name", "label", "detail")


def _clean_options(raw: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, list) or not raw:
        return [], "options must be a non-empty array of {id, name}"
    if len(raw) > MAX_OPTIONS:
        return [], f"too many options: {len(raw)} (limit {MAX_OPTIONS}); narrow the candidate list"
    cleaned: List[Dict[str, Any]] = []
    seen = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            return [], f"option {index} is not an object"
        oid = str(item.get("id") or "").strip()
        label = str(item.get("name") or item.get("label") or "").strip()
        if not oid or not label:
            return [], f"option {index} needs both id and name"
        if oid in ("__done__", "__stuck__"):
            return [], f"option id {oid!r} is a reserved sentinel; the policy offers those itself"
        if oid in seen:
            return [], f"duplicate option id {oid!r}"
        seen.add(oid)
        option: Dict[str, Any] = {"id": oid, "label": label}
        detail = str(item.get("detail") or "").strip()
        if detail:
            option["detail"] = detail
        cleaned.append(option)
    return cleaned, None


def _hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    return Path(env) if env else Path.home() / ".hermes"


def _split_command(value: str) -> List[str]:
    """Split `JEV_PILOT_BIN` into an argv without mangling Windows paths.

    `shlex.split` in posix mode treats a backslash as an escape, so `C:\\Python\\python.exe`
    becomes `C:Pythonpython.exe`, which resolves to nothing. On Windows the split keeps
    backslashes and only strips surrounding quotes.
    """
    if os.name == "nt":
        parts = shlex.split(value, posix=False)
        return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    return shlex.split(value)


def _binary() -> List[str]:
    """The command that runs the CLI: JEV_PILOT_BIN may be a full command line."""
    configured = (os.environ.get("JEV_PILOT_BIN") or "").strip()
    if configured:
        parts = _split_command(configured)
        if parts:
            return parts
    found = shutil.which("jev-pilot")
    if found:
        return [found]
    return ["jev-pilot"]


def available() -> bool:
    """check_fn for the registry: hide the tool when the CLI cannot be resolved."""
    parts = _binary()
    return bool(shutil.which(parts[0]) or Path(parts[0]).exists())


def _env_with_key() -> Dict[str, str]:
    env = dict(os.environ)
    if env.get("TYPESAFE_API_KEY"):
        return env
    dotenv = _hermes_home() / ".env"
    if not dotenv.is_file():
        return env
    try:
        for line in dotenv.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "TYPESAFE_API_KEY" and value.strip():
                env["TYPESAFE_API_KEY"] = value.strip().strip("'\"")
                break
    except OSError:
        pass
    return env


def _error(reason: str, **extra: Any) -> str:
    payload = {"ok": False, "outcome": "error", "reason": reason, "pick": None}
    payload.update(extra)
    return json.dumps(payload)


def jev_decide(args: Dict[str, Any], **kwargs: Any) -> str:
    goal = str(args.get("goal") or "").strip()
    if not goal:
        return _error("goal is required: one sentence describing what the episode is trying to do")
    options, problem = _clean_options(args.get("options"))
    if problem:
        return _error(problem)

    state = str(args.get("state") or "")
    if len(state) > MAX_STATE_CHARS:
        state = state[:MAX_STATE_CHARS]

    request: Dict[str, Any] = {"goal": goal, "state": state, "options": options}
    floor = args.get("confidence_floor")
    if isinstance(floor, (int, float)) and not isinstance(floor, bool):
        request["confidence_floor"] = float(floor)

    command = _binary() + ["decide", "--provider", str(args.get("provider") or "jev")]
    if args.get("model"):
        command += ["--model", str(args["model"])]
    if isinstance(floor, (int, float)) and not isinstance(floor, bool):
        command += ["--floor", str(float(floor))]

    try:
        completed = subprocess.run(
            command,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DEFAULT_TIMEOUT_S,
            env=_env_with_key(),
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        return _error(f"the decision call did not return within {DEFAULT_TIMEOUT_S:.0f}s")
    except FileNotFoundError:
        return _error(
            "could not run the jev-pilot CLI; install it (pip install jev-browser-pilot) or point "
            "JEV_PILOT_BIN at it"
        )
    except OSError as exc:
        return _error(f"could not run the jev-pilot CLI: {exc}")

    stdout = (completed.stdout or "").strip()
    if not stdout:
        detail = (completed.stderr or "").strip().splitlines()
        return _error(
            "the decision CLI returned nothing on stdout"
            + (f": {detail[-1]}" if detail else f" (exit {completed.returncode})"),
            exit_code=completed.returncode,
        )
    try:
        decision = json.loads(stdout)
    except json.JSONDecodeError:
        return _error("the decision CLI did not return JSON", exit_code=completed.returncode)

    # The CLI exits 2 when the decision itself is an error (no answer, transport failure). The
    # payload still carries the reason, so report it rather than inventing an outcome.
    outcome = decision.get("outcome") or decision.get("decision")
    if completed.returncode != 0 and outcome != "error":
        return _error(
            f"the decision CLI exited {completed.returncode}",
            exit_code=completed.returncode,
            decision=decision,
        )
    return json.dumps({"ok": outcome != "error", "decision": decision})
