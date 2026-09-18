"""Desktop surface: a native window driven through cua-driver's CLI (experimental).

The same loop, the same policy, the same verification: only the observation source
and the actuation call change. Perception here is a UI Automation tree instead of a
DOM, so the elements are normalized with `elements_from_uia`, and a click is
addressed by the accessibility element token that the snapshot handed out.

This module is marked experimental because UIA trees vary in quality by toolkit, and
because the driver must be installed and reachable. It is included because the
architecture claim ("a decision layer, not a browser hack") is only credible if the
same loop drives a desktop window too.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jev_pilot.perception import Snapshot, elements_from_uia
from jev_pilot.safety import SafetyPolicy
from jev_pilot.surface import Surface

DRIVER_CANDIDATES = (
    r"C:\Users\Public\Cua\cua-driver\bin\cua-driver.exe",
    os.path.expanduser("~/.local/bin/cua-driver"),
    "/usr/local/bin/cua-driver",
)


class DriverUnavailable(RuntimeError):
    pass


def _tolerant_json(text: str) -> Optional[Any]:
    """Parse the driver's reply: plain JSON, or the first JSON value in noise. None if neither.

    The driver prints a human sentence when it refuses a call, so a strict decode here used to turn
    a clear message into a JSONDecodeError traceback.
    """
    if not text:
        return None
    # A UTF-8 BOM on stdout is common on Windows and json.loads rejects it outright.
    text = text.lstrip("\ufeff \t\r\n")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        value, _ = json.JSONDecoder().raw_decode(text)
        return value
    except json.JSONDecodeError:
        return None


def find_driver(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("JEV_PILOT_CUA_DRIVER")
    if env and (Path(env).exists() or shutil.which(env)):
        return env
    for candidate in DRIVER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    found = shutil.which("cua-driver")
    if found:
        return found
    raise DriverUnavailable(
        "cua-driver not found. Install it (https://github.com/trycua/cua) or set "
        "JEV_PILOT_CUA_DRIVER=/path/to/cua-driver."
    )


class DesktopPilot(Surface):
    """Drive one window: one observe-decide-act cycle per step, in the background."""

    name = "desktop"

    def __init__(
        self,
        *,
        app: Optional[str] = None,
        aumid: Optional[str] = None,
        driver: Optional[str] = None,
        attach_pid: Optional[int] = None,
        window_id: Optional[str] = None,
        settle_seconds: float = 2.5,
        max_elements: int = 400,
        safety: Optional[SafetyPolicy] = None,
        verbose: bool = False,
    ):
        self.driver = find_driver(driver)
        self.app = app
        self.aumid = aumid
        self.attach_pid = attach_pid
        self.window_id = window_id
        self.settle_seconds = settle_seconds
        self.max_elements = max_elements
        self.safety = safety
        self.verbose = verbose
        self.pid: Optional[int] = attach_pid
        self._tokens: Dict[str, str] = {}
        self._latest = Snapshot()

    # ---- driver plumbing ----------------------------------------------
    def call(self, tool: str, args: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
        proc = subprocess.run(
            [self.driver, "call", tool, "--json", json.dumps(args)],
            capture_output=True, text=True, timeout=timeout,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        payload = _tolerant_json(text)
        if payload is None:
            # The driver refused or crashed and said why in plain text. Report it: raising here
            # turned "Missing required integer field window_id" into a JSONDecodeError traceback.
            return {"isError": True, "raw": text[:500], "returncode": proc.returncode}
        return payload if isinstance(payload, dict) else {"isError": True, "raw": text[:500]}

    def _window_for_pid(self) -> Optional[int]:
        """The driver wants a numeric window id; find this process's window when nobody passed one.

        Attaching by pid alone used to fail at the first observation with the driver's own
        complaint, because the window id never came from anywhere.
        """
        if not self.pid:
            return None
        result = self.call("list_windows", {})
        windows = result.get("windows")
        if windows is None:
            for key in ("data", "structuredContent"):
                candidate = result.get(key)
                if isinstance(candidate, dict) and candidate.get("windows"):
                    windows = candidate["windows"]
                    break
                if isinstance(candidate, list):
                    windows = candidate
                    break
        for window in windows or []:
            if not isinstance(window, dict):
                continue
            try:
                if int(window.get("pid") or 0) == int(self.pid) and window.get("window_id"):
                    return int(window["window_id"])
            except (TypeError, ValueError):
                continue
        return None

    # ---- lifecycle -----------------------------------------------------
    def start(self) -> "DesktopPilot":
        if self.pid is None:
            if self.safety is not None:
                self.safety.check_action("click")  # fails closed if actuation is off
            launched = None
            for args in ([{"aumid": self.aumid}] if self.aumid else []) + (
                    [{"name": self.app}] if self.app else []):
                result = self.call("launch_app", args)
                if result.get("pid"):
                    launched = result
                    break
            if not launched:
                raise DriverUnavailable(
                    f"could not launch {self.aumid or self.app!r}; check the app name or AUMID"
                )
            self.pid = int(launched["pid"])
            windows = launched.get("windows") or []
            if windows and not self.window_id:
                self.window_id = windows[0].get("window_id")
        if not self.window_id:
            resolved = self._window_for_pid()
            if resolved:
                self.window_id = resolved
        time.sleep(self.settle_seconds)
        return self

    def close(self) -> None:
        # Leaving the app running is intentional: the caller may own it. Killing is opt-in.
        return None

    def kill(self) -> None:
        if self.pid:
            self.call("kill_app", {"pid": self.pid})

    def __enter__(self) -> "DesktopPilot":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- Surface -------------------------------------------------------
    def observe(self) -> Snapshot:
        if self.pid is None:
            raise DriverUnavailable("desktop surface is not attached to a process; call start()")
        if not self.window_id:
            resolved = self._window_for_pid()
            if resolved:
                self.window_id = resolved
        args: Dict[str, Any] = {"pid": self.pid, "include_screenshot": False,
                                "max_elements": self.max_elements}
        if self.window_id:
            args["window_id"] = self.window_id
        raw = self.call("get_window_state", args)
        if raw.get("isError"):
            raise DriverUnavailable(
                "the desktop driver refused the observation: "
                f"{raw.get('raw') or 'no detail'} (exit {raw.get('returncode')})"
            )
        structured = raw.get("structuredContent") or raw
        elements = structured.get("elements") or []
        if not elements:
            raise DriverUnavailable(
                "the accessibility tree came back empty; the window may be minimised, on another "
                "virtual desktop, or the app may expose no UIA tree"
            )
        if structured.get("window_id"):
            self.window_id = structured["window_id"]
        self._tokens = {str(el.get("element_index")): el.get("element_token")
                        for el in elements if el.get("element_token")}
        snapshot = Snapshot(
            url=None,
            title=structured.get("window_title") or self.app or "window",
            text=self._text_of(elements),
            elements=elements_from_uia(elements, cap=self.max_elements),
            matched_total=structured.get("total_element_count"),
        )
        self._latest = snapshot
        return snapshot

    # Roles that carry content worth showing: text, and the item roles a file list, a tree or a
    # table uses. Menu chrome is deliberately excluded, since it is not what a task is about.
    TEXT_ROLES = ("text", "listitem", "treeitem", "dataitem")

    @classmethod
    def _content_labels(cls, elements: List[Dict[str, Any]]) -> List[str]:
        labels: List[str] = []
        seen = set()
        for el in elements:
            role = str(el.get("role") or "").lower()
            if not any(marker in role for marker in cls.TEXT_ROLES):
                continue
            label = " ".join(str(el.get("label") or "").split())
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            labels.append(label)
        return labels

    @staticmethod
    def _text_of(elements: List[Dict[str, Any]]) -> str:
        """What this window says, best effort.

        A native window has no document text, so the surface reports its own content labels
        joined together. Labels that contain a digit lead, because they are usually the display
        or a field value, which is what a postcondition is normally about. A single label was
        wrong: it returned the window title, so a `text-contains:` check on the calculator's
        display silently inspected the word "Calculator".
        """
        labels = DesktopPilot._content_labels(elements)
        if not labels:
            return ""
        valued = [l for l in labels if any(ch.isdigit() for ch in l)]
        rest = [l for l in labels if l not in valued]
        return " | ".join(valued + rest)[:400]

    def url(self) -> Optional[str]:
        return None

    def probe(self, selector: str) -> Optional[bool]:
        return None  # no CSS in a native window

    def act(self, option_id: str) -> Dict[str, Any]:
        token = self._tokens.get(str(option_id))
        args: Dict[str, Any] = {"pid": self.pid}
        if token:
            args["element_token"] = token
        else:
            args["element_index"] = int(option_id)
            if self.window_id:
                args["window_id"] = self.window_id
        result = self.call("click", args)
        time.sleep(1.4)  # UWP invoke latency; see docs/findings.md
        return {
            "clicked": not result.get("isError"),
            "option_id": str(option_id),
            "effect": result.get("effect"),
            "route": result.get("route"),
            "engine": "uia",
            "raw": {k: v for k, v in result.items() if k in ("isError", "error", "code")},
        }

    def describe(self) -> str:
        return f"desktop pid={self.pid} window={self.window_id}"
