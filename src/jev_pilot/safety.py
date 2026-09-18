"""Safety rails. Opt-in by construction: navigation is confined to hosts you name.

Defaults are deliberately narrow, because this library drives a real browser on a
real machine:

- only `click` is allowed as an action, and only on a URL whose host is allowed;
- typing is refused unless `allow_typing` is set, and credentials are never typed
  by the library at all (there is no API for passwords, tokens or card numbers);
- hosts must be listed explicitly (a start URL contributes its own host only when
  the caller asks for that), so a redirect to another domain fails closed;
- `dry_run` stops after the decision, before any actuation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Iterable, Optional, Sequence, Tuple
from urllib.parse import urlparse


class SafetyError(RuntimeError):
    """Raised when an action would leave the box the caller declared."""


def host_of(url: Optional[str]) -> Optional[str]:
    """The host a URL belongs to. `file://` URLs report the pseudo-host `file`,
    so a caller can allow local files explicitly instead of silently having no host
    to check against."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return "file"
    host = (parsed.hostname or "").lower()
    return host or None


@dataclass(frozen=True)
class SafetyPolicy:
    allow_hosts: FrozenSet[str] = frozenset()
    allow_actions: Tuple[str, ...] = ("click",)
    allow_typing: bool = False
    dry_run: bool = False
    max_steps: int = 12

    # ---- construction -------------------------------------------------
    @classmethod
    def for_hosts(cls, hosts: Iterable[str], **kwargs) -> "SafetyPolicy":
        cleaned = frozenset(h.strip().lower() for h in hosts if h and h.strip())
        if not cleaned:
            raise SafetyError("no hosts declared: pass at least one host to allow")
        return cls(allow_hosts=cleaned, **kwargs)

    @classmethod
    def for_url(cls, url: str, **kwargs) -> "SafetyPolicy":
        host = host_of(url)
        if not host:
            raise SafetyError(f"cannot derive a host from {url!r}")
        return cls.for_hosts([host], **kwargs)

    # ---- checks -------------------------------------------------------
    def host_allowed(self, url: Optional[str]) -> bool:
        host = host_of(url)
        if not host:
            return False
        for allowed in self.allow_hosts:
            if host == allowed or host.endswith("." + allowed):
                return True
        return False

    def check_url(self, url: Optional[str]) -> None:
        if not self.allow_hosts:
            raise SafetyError("no hosts declared; refusing to touch the network")
        if not self.host_allowed(url):
            raise SafetyError(
                f"host {host_of(url)!r} is not in the allow list "
                f"({', '.join(sorted(self.allow_hosts))}); refusing to navigate"
            )

    def check_action(self, action: str, url: Optional[str] = None) -> None:
        if action not in self.allow_actions:
            raise SafetyError(f"action {action!r} is not allowed ({', '.join(self.allow_actions)})")
        if url is not None:
            self.check_url(url)

    def require_typing_allowed(self) -> None:
        if not self.allow_typing:
            raise SafetyError("typing is disabled; enable allow_typing only for a task that needs it")

    def cap_steps(self, requested: Optional[int]) -> int:
        if requested is None:
            return self.max_steps
        return max(1, min(int(requested), self.max_steps))

    def describe(self) -> str:
        hosts = ", ".join(sorted(self.allow_hosts)) or "(none declared)"
        return (f"hosts=[{hosts}] actions={list(self.allow_actions)} "
                f"typing={'on' if self.allow_typing else 'off'} "
                f"dry_run={self.dry_run} max_steps={self.max_steps}")
