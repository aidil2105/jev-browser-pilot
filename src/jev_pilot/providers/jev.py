"""TypeSafe Jev provider: a System One model answering one typed choice.

Jev does not generate text. You send a state plus a typed question and get back a
label, the full probability map and a confidence. That is exactly the shape the loop
wants, which is why the CLI defaults to it.

The key is read from `TYPESAFE_API_KEY` (or passed explicitly). It is never logged,
never written to a trace, and never echoed by the CLI.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Optional, Sequence

from jev_pilot.policy import build_criteria, build_instructions
from jev_pilot.providers.base import Chooser, ProviderUnavailable, RawAnswer
from jev_pilot.types import Option

DEFAULT_MODEL = None  # the SDK's alias (jev-latest); the response reports the real id
DEFAULT_PRICE_PER_MTOK = 0.042  # USD per million input tokens; output is free


def _sdk_missing_message(version_info=None) -> str:
    """The remedy for a missing vendor SDK depends on the interpreter.

    `typesafe-sdk` is marker-gated to Python 3.10+ in this package's metadata, so on 3.9 the obvious
    advice is a loop: installing `[jev]` deliberately skips the SDK there and the user lands back on
    the same message. Say what will actually work instead.

    The version is a parameter so the branch is testable without patching `sys.version_info`, which
    makes `json`-shaped fakes and hides the very thing under test.
    """
    info = version_info if version_info is not None else sys.version_info
    version = f"{info[0]}.{info[1]}"
    if (info[0], info[1]) < (3, 10):
        return (
            f"typesafe-sdk is not installed, and it needs Python 3.10 or newer while this is "
            f"Python {version}. Use a newer interpreter for the jev provider, or use the mock or "
            f"openai provider here"
        )
    return "typesafe-sdk is not installed; run: pip install 'jev-browser-pilot[jev]'"


class JevChooser(Chooser):
    name = "jev"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client=None,
        price_per_mtok: float = DEFAULT_PRICE_PER_MTOK,
        instructions_template: Optional[str] = None,
        criteria_detail: bool = True,
    ):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        self.model = model
        self.price_per_mtok = price_per_mtok
        self.instructions_template = instructions_template
        self.criteria_detail = criteria_detail
        self._client = client
        if self._client is None and not self.api_key:
            raise ProviderUnavailable(
                "TYPESAFE_API_KEY is not set and no client was injected. "
                "Set the key, pass api_key=..., or use a different provider "
                "(mock, openai)."
            )

    def _get_client(self):
        if self._client is None:
            try:
                from typesafe_sdk import TypeSafeClient
            except ImportError as exc:  # pragma: no cover - depends on extras
                raise ProviderUnavailable(_sdk_missing_message()) from exc
            self._client = TypeSafeClient(api_key=self.api_key)
        return self._client

    def choose(self, *, goal: str, state: str, options: Sequence[Option],
               timeout: Optional[float] = None) -> RawAnswer:
        try:
            from typesafe_sdk import Choice
        except ImportError as exc:  # pragma: no cover
            raise ProviderUnavailable(_sdk_missing_message()) from exc

        try:
            criteria = build_criteria(options, detail=self.criteria_detail)
        except ValueError as exc:
            return RawAnswer(error=str(exc))

        question = Choice(
            instructions=build_instructions(goal, self.instructions_template),
            criteria=criteria,
        )

        started = self.timer()
        try:
            response = self._get_client().system_one(
                state=state,
                questions={"next_step": question},
                **({"model": self.model} if self.model else {}),
                **({"timeout": timeout} if timeout else {}),
            )
        except Exception as exc:  # noqa: BLE001 - transport errors are a caller concern
            return RawAnswer(error=f"{type(exc).__name__}: {exc}",
                             latency_ms=self.elapsed_ms(started), model=self.model)

        answer = response.answers["next_step"]
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None) if usage is not None else None
        output_tokens = getattr(usage, "output_tokens", None) if usage is not None else None
        cost = None
        if input_tokens is not None:
            cost = round(input_tokens * self.price_per_mtok / 1_000_000, 10)

        return RawAnswer(
            pick=str(answer.choice),
            confidence=getattr(answer, "confidence", None),
            probabilities=dict(getattr(answer, "probabilities", {}) or {}),
            model=getattr(response, "model", None) or self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=self.elapsed_ms(started),
        )

    def describe(self) -> str:
        return f"jev model={self.model or 'jev-latest'}"


def key_present() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY"))
