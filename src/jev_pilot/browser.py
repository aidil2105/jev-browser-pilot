"""A real Chrome, driven over CDP, as a `Surface`.

Design choices that came out of live failures:

- the browser runs on its own `--user-data-dir` and its own debugging port, so it
  can never attach to a logged-in profile;
- `observe()` retries until the page is readable, because `Runtime.evaluate` returns
  nothing while a navigation is in flight;
- the click addresses the element by the stamp the serializer put on it
  (`data-jev-idx`), so the element clicked is the element that was described;
- after a click the surface waits for both a changed URL and `readyState == complete`,
  and reports what happened instead of assuming success.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from jev_pilot.perception import DomRules, Snapshot, click_js, parse_snapshot, probe_js
from jev_pilot.safety import SafetyPolicy
from jev_pilot.surface import Surface

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)


class BrowserUnavailable(RuntimeError):
    pass


def find_chrome(explicit: Optional[str] = None) -> str:
    if explicit:
        if not Path(explicit).exists() and not shutil.which(explicit):
            raise BrowserUnavailable(f"chrome/edge not found at {explicit!r}")
        return explicit
    env = os.environ.get("JEV_PILOT_CHROME")
    if env and (Path(env).exists() or shutil.which(env)):
        return env
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise BrowserUnavailable(
        "no Chrome/Chromium found. Set JEV_PILOT_CHROME=/path/to/chrome or pass chrome=..."
    )


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Tab:
    """The smallest CDP client that is enough: evaluate, navigate, close."""

    def __init__(self, ws_url: str, timeout: float = 30.0):
        try:
            import websocket  # from websocket-client
        except ImportError as exc:  # pragma: no cover
            raise BrowserUnavailable("websocket-client is required for the browser surface") from exc
        self._ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
        self._id = 0

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._id += 1
        mid = self._id
        self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self._ws.recv())
            if message.get("id") == mid:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def eval_js(self, expression: str):
        result = self.call("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True,
        })
        return result.get("result", {}).get("value")

    def safe_eval(self, expression: str, default=None):
        try:
            return self.eval_js(expression)
        except Exception:
            return default

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass


class BrowserPilot(Surface):
    name = "chrome"

    def __init__(
        self,
        start_url: str,
        *,
        chrome: Optional[str] = None,
        port: Optional[int] = None,
        profile_dir: Optional[str] = None,
        window_size: str = "1280,900",
        headless: bool = False,
        settle_seconds: float = 2.5,
        nav_timeout: float = 12.0,
        rules: Optional[DomRules] = None,
        safety: Optional[SafetyPolicy] = None,
        verbose: bool = False,
    ):
        self.start_url = start_url
        self.rules = rules or DomRules()
        self.safety = safety
        self.verbose = verbose
        self.port = port or free_port()
        default_base = Path(os.environ.get("JEV_PILOT_PROFILE_DIR") or tempfile.gettempdir())
        self.profile_dir = Path(profile_dir or (default_base / f"jev-pilot-profile-{self.port}"))
        self.window_size = window_size
        self.headless = headless
        self.settle_seconds = settle_seconds
        self.nav_timeout = nav_timeout
        self._process: Optional[subprocess.Popen] = None
        self._tab: Optional[Tab] = None
        self.chrome_path = find_chrome(chrome)

    # ---- lifecycle ----------------------------------------------------
    def start(self) -> "BrowserPilot":
        if self.safety is not None:
            self.safety.check_url(self.start_url)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        args = [
            self.chrome_path,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            f"--window-size={self.window_size}",
            self.start_url,
        ]
        if self.headless:
            args.insert(1, "--headless=new")
        self._process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._wait_for_cdp()
        self._tab = Tab(self._page_ws_url())
        self._tab.call("Page.enable")
        time.sleep(self.settle_seconds)
        return self

    def _wait_for_cdp(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        last_error: Optional[Exception] = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=3) as r:
                    json.load(r)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.4)
        raise BrowserUnavailable(f"CDP endpoint never came up on port {self.port}: {last_error}")

    def _page_ws_url(self, want_host: Optional[str] = None) -> str:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=10) as r:
            targets = json.load(r)
        pages = [t for t in targets if t.get("type") == "page"
                 and not (t.get("url") or "").startswith(("devtools://", "chrome://"))]
        if not pages:
            raise BrowserUnavailable("no page target on the CDP endpoint")
        if want_host:
            pages.sort(key=lambda t: want_host not in (t.get("url") or ""))
        return pages[0]["webSocketDebuggerUrl"]

    def close(self) -> None:
        if self._tab is not None:
            self._tab.close()
            self._tab = None
        if self._process is not None and self._process.poll() is None:
            if sys.platform.startswith("win"):
                subprocess.run(["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                               capture_output=True, text=True)
            else:
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:  # pragma: no cover
                    self._process.kill()
        self._process = None

    def __enter__(self) -> "BrowserPilot":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- Surface ------------------------------------------------------
    def observe(self) -> Snapshot:
        tab = self._require_tab()
        payload = None
        for _ in range(30):
            payload = tab.safe_eval(self.rules.js())
            if isinstance(payload, dict) and "elements" in payload:
                break
            time.sleep(0.4)
        if not isinstance(payload, dict):
            raise BrowserUnavailable("could not read the page state (no readable document)")
        return parse_snapshot(payload, self.rules)

    def url(self) -> Optional[str]:
        return self._require_tab().safe_eval("location.href")

    def probe(self, selector: str) -> Optional[bool]:
        return bool(self._require_tab().safe_eval(probe_js(selector), default=False))

    def act(self, option_id: str) -> Dict[str, Any]:
        tab = self._require_tab()
        before = tab.safe_eval("location.href")
        if self.safety is not None:
            self.safety.check_action("click", before or self.start_url)
        result = tab.safe_eval(click_js(self.rules, option_id), default={"clicked": False})
        navigated = self._settle(before)
        return {
            "clicked": bool((result or {}).get("clicked")),
            "option_id": str(option_id),
            "tag": (result or {}).get("tag"),
            "navigation": navigated,
            "url": tab.safe_eval("location.href"),
            "engine": "cdp",
        }

    def go(self, url: str) -> Dict[str, Any]:
        if self.safety is not None:
            self.safety.check_url(url)
        tab = self._require_tab()
        before = tab.safe_eval("location.href")
        tab.call("Page.navigate", {"url": url})
        return {"navigation": self._settle(before), "url": tab.safe_eval("location.href")}

    def _settle(self, url_before: Optional[str]) -> str:
        """Wait for a changed URL and a complete document. Reports, never assumes."""
        tab = self._require_tab()
        deadline = time.time() + self.nav_timeout
        while time.time() < deadline:
            time.sleep(0.25)
            now = tab.safe_eval("location.href")
            ready = tab.safe_eval("document.readyState")
            if now and now != url_before and ready == "complete":
                return "settled"
            if now and now != url_before and ready is None:
                continue
        now = tab.safe_eval("location.href")
        if now == url_before:
            return "no_change"
        return "timeout"

    def _require_tab(self) -> Tab:
        if self._tab is None:
            raise BrowserUnavailable("browser surface is not started; call start()")
        return self._tab

    def describe(self) -> str:
        return f"chrome pid={getattr(self._process, 'pid', None)} port={self.port} profile={self.profile_dir.name}"
