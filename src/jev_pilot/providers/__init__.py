"""Chooser registry. `build_chooser` is the single place a provider name is resolved."""

from __future__ import annotations

from typing import Optional, Sequence

from jev_pilot.providers.base import (
    Chooser,
    KeywordChooser,
    ProviderUnavailable,
    RawAnswer,
    ScriptedChooser,
)

__all__ = [
    "Chooser",
    "KeywordChooser",
    "ProviderUnavailable",
    "RawAnswer",
    "ScriptedChooser",
    "build_chooser",
    "PROVIDERS",
]


def build_chooser(kind: str, **kwargs) -> Chooser:
    """`jev` (default), `openai` (any compatible endpoint), `mock`/`keyword`, `scripted`."""
    key = (kind or "jev").strip().lower()
    if key == "jev":
        from jev_pilot.providers.jev import JevChooser
        return JevChooser(**kwargs)
    if key in ("openai", "compatible", "openai-compatible"):
        from jev_pilot.providers.openai_compat import OpenAIChatChooser
        model = kwargs.pop("model", None)
        if not model:
            raise ProviderUnavailable("provider 'openai' needs --model")
        return OpenAIChatChooser(model=model, **kwargs)
    if key in ("mock", "keyword"):
        return KeywordChooser(**kwargs)
    if key == "scripted":
        answers: Sequence = kwargs.pop("answers", [])
        return ScriptedChooser(answers, **kwargs)
    raise ProviderUnavailable(
        f"unknown provider {kind!r}; use jev, openai, mock or scripted"
    )


PROVIDERS = ("jev", "openai", "mock", "scripted")
