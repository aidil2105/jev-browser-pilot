"""Deterministic postconditions. No model is ever asked whether the task succeeded.

Spec strings (what the CLI accepts, and what a task file stores):

    url-contains:TEXT          case-sensitive substring of the current URL
    url-regex:PATTERN          regular expression against the current URL
    text-contains:TEXT         case-insensitive substring of the page's visible text
    selector:CSS               the page has at least one element matching the CSS
    file-contains:PATH::TEXT   a local file exists and contains TEXT

`verify_all` returns one record per spec: {"spec", "passed", "detail"}. An episode
is `reached` only when every spec passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence


class SpecificationError(ValueError):
    pass


@dataclass(frozen=True)
class VerificationContext:
    """Where the checks read from. `probe` is the only part that needs a live page."""

    url: Optional[str] = None
    text: Optional[str] = None
    probe: Optional[Callable[[str], bool]] = None

    def selector_exists(self, selector: str) -> Optional[bool]:
        if self.probe is None:
            return None
        return bool(self.probe(selector))


class Postcondition:
    kind = "base"

    def check(self, ctx: VerificationContext) -> Dict[str, object]:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class UrlContains(Postcondition):
    needle: str
    kind = "url-contains"

    def check(self, ctx: VerificationContext) -> Dict[str, object]:
        url = ctx.url or ""
        passed = self.needle in url
        return {"passed": passed, "detail": f"{self.needle!r} in {url[:120]!r}"}

    def describe(self) -> str:
        return f"url-contains:{self.needle}"


@dataclass(frozen=True)
class UrlRegex(Postcondition):
    pattern: str
    kind = "url-regex"

    def check(self, ctx: VerificationContext) -> Dict[str, object]:
        url = ctx.url or ""
        passed = re.search(self.pattern, url) is not None
        return {"passed": passed, "detail": f"/{self.pattern}/ in {url[:120]!r}"}

    def describe(self) -> str:
        return f"url-regex:{self.pattern}"


@dataclass(frozen=True)
class TextContains(Postcondition):
    needle: str
    kind = "text-contains"

    def check(self, ctx: VerificationContext) -> Dict[str, object]:
        haystack = re.sub(r"\s+", " ", ctx.text or "").lower()
        passed = self.needle.lower() in haystack
        return {"passed": passed, "detail": f"{self.needle!r} in visible text"}

    def describe(self) -> str:
        return f"text-contains:{self.needle}"


@dataclass(frozen=True)
class SelectorExists(Postcondition):
    selector: str
    kind = "selector"

    def check(self, ctx: VerificationContext) -> Dict[str, object]:
        result = ctx.selector_exists(self.selector)
        if result is None:
            return {"passed": False, "detail": "no live page to probe (selector check unavailable)"}
        return {"passed": result, "detail": f"selector {self.selector!r} present={result}"}

    def describe(self) -> str:
        return f"selector:{self.selector}"


@dataclass(frozen=True)
class FileContains(Postcondition):
    path: str
    needle: str
    kind = "file-contains"

    def check(self, ctx: VerificationContext) -> Dict[str, object]:
        target = Path(self.path)
        if not target.exists():
            return {"passed": False, "detail": f"{self.path} does not exist"}
        try:
            body = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"passed": False, "detail": f"{self.path} unreadable: {exc}"}
        passed = self.needle in body
        return {"passed": passed, "detail": f"{self.needle!r} in {self.path}"}

    def describe(self) -> str:
        return f"file-contains:{self.path}::{self.needle}"


def parse_postcondition(spec: str) -> Postcondition:
    if not spec or ":" not in spec:
        raise SpecificationError(
            f"bad postcondition {spec!r}; expected url-contains:, url-regex:, "
            "text-contains:, selector: or file-contains:PATH::TEXT"
        )
    kind, _, rest = spec.partition(":")
    kind = kind.strip().lower()
    if kind == "file-contains":
        path, sep, needle = rest.partition("::")
        if not sep:
            raise SpecificationError("file-contains needs PATH::TEXT")
        return FileContains(path=path.strip(), needle=needle)
    if not rest:
        raise SpecificationError(f"{kind} needs a value after the colon")
    if kind == "url-contains":
        return UrlContains(needle=rest)
    if kind == "url-regex":
        return UrlRegex(pattern=rest)
    if kind == "text-contains":
        return TextContains(needle=rest)
    if kind == "selector":
        return SelectorExists(selector=rest)
    raise SpecificationError(f"unknown postcondition kind {kind!r}")


def verify_all(specs: Sequence[str], ctx: VerificationContext) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for spec in specs:
        try:
            cond = parse_postcondition(spec)
        except SpecificationError as exc:
            results.append({"spec": spec, "passed": False, "detail": str(exc)})
            continue
        record = cond.check(ctx)
        results.append({"spec": spec, "passed": bool(record["passed"]), "detail": record["detail"]})
    return results


def all_passed(results: Sequence[Dict[str, object]]) -> bool:
    return bool(results) and all(bool(r.get("passed")) for r in results)
