"""Any OpenAI-compatible endpoint as the chooser (Ollama, vLLM, LM Studio, a gateway).

Included because a decision layer that only works with one vendor is not a decision
layer, and because most people evaluating this library will not have Jev access yet.
The prompt asks for one id, the parser accepts the messy realities of real relays
(payload wrapped in a `data` envelope, or two JSON objects concatenated on one body),
and every knob that bit us in practice is exposed and documented.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional, Sequence

from jev_pilot.policy import DONE, STUCK, build_criteria, build_instructions
from jev_pilot.providers.base import Chooser, ProviderUnavailable, RawAnswer
from jev_pilot.types import Option

PROMPT_TEMPLATE = (
    "{state}\n\n"
    "GOAL: {goal}\n\n"
    "You are the decision step of a computer-use loop. Answer with JSON only, no prose: "
    '{{"id": "<one id from the list>"}}.\n'
    "The ids are:\n{listing}\n"
    f"Use {DONE} only if the goal is already achieved in the state, and {STUCK} only if no "
    "listed candidate can make progress toward the goal."
)


def default_transport(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class OpenAIChatChooser(Chooser):
    name = "openai"

    def __init__(
        self,
        *,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_tokens: int = 800,
        temperature: Optional[float] = None,
        transport: Optional[Callable[[urllib.request.Request, float], bytes]] = None,
        input_price_per_mtok: Optional[float] = None,
        output_price_per_mtok: Optional[float] = None,
        extra_body: Optional[Dict[str, object]] = None,
        criteria_detail: bool = False,
    ):
        self.model = model
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL")
                         or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key if api_key is not None else (
            os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_COMPAT_API_KEY") or "")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.transport = transport or default_transport
        self.input_price_per_mtok = input_price_per_mtok
        self.output_price_per_mtok = output_price_per_mtok
        self.extra_body = dict(extra_body or {})
        self.criteria_detail = criteria_detail
        if not self.api_key and "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
            raise ProviderUnavailable(
                "no API key: set OPENAI_API_KEY (or OPENAI_COMPAT_API_KEY), pass api_key=..., "
                "or point --base-url at a local server that needs none"
            )

    # ---- request/response ---------------------------------------------
    def build_prompt(self, goal: str, state: str, options: Sequence[Option]) -> str:
        listing = "\n".join(
            f"{opt.id}: {opt.label}" + (f" ({opt.detail})" if self.criteria_detail and opt.detail else "")
            for opt in options
        )
        return PROMPT_TEMPLATE.format(goal=goal, state=state, listing=listing)

    def _payload(self, goal: str, state: str, options: Sequence[Option]) -> Dict[str, object]:
        body: Dict[str, object] = {
            "model": self.model,
            "messages": [{"role": "user", "content": self.build_prompt(goal, state, options)}],
            # Reasoning models spend budget on reasoning before content; a small cap
            # produces an empty message, which relays report as a 5xx. Keep it generous.
            "max_tokens": self.max_tokens,
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        body.update(self.extra_body)
        return body

    @staticmethod
    def parse_payload(raw: str) -> Dict[str, object]:
        """Tolerant decoder: `data` envelope, concatenated JSON bodies, whitespace."""
        payload, _ = json.JSONDecoder().raw_decode(raw.lstrip())
        if isinstance(payload.get("data"), dict):
            return payload["data"]
        return payload

    def choose(self, *, goal: str, state: str, options: Sequence[Option],
               timeout: Optional[float] = None) -> RawAnswer:
        try:
            build_criteria(options)  # rejects sentinel collisions before spending a call
        except ValueError as exc:
            return RawAnswer(error=str(exc))

        body = json.dumps(self._payload(goal, state, options)).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})},
        )
        started = time.perf_counter()
        try:
            raw = self.transport(request, float(timeout or 120)).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:  # surface the body: relays hide 402/429 behind 503
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            return RawAnswer(error=f"HTTP {exc.code}: {detail}",
                             latency_ms=self.elapsed_ms(started), model=self.model)
        except Exception as exc:  # noqa: BLE001
            return RawAnswer(error=f"{type(exc).__name__}: {exc}",
                             latency_ms=self.elapsed_ms(started), model=self.model)

        latency = self.elapsed_ms(started)
        try:
            payload = self.parse_payload(raw)
            content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        except Exception as exc:  # noqa: BLE001
            return RawAnswer(error=f"unparseable response: {exc}: {raw[:200]}",
                             latency_ms=latency, model=self.model)

        usage = payload.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        cost = None
        if input_tokens is not None and self.input_price_per_mtok is not None:
            cost = round(input_tokens * self.input_price_per_mtok / 1_000_000, 10)
        if output_tokens is not None and self.output_price_per_mtok is not None:
            cost = round((cost or 0.0) + output_tokens * self.output_price_per_mtok / 1_000_000, 10)

        ids = {str(opt.id) for opt in options} | {DONE, STUCK}
        match = re.search(r'"id"\s*:\s*"([^"]+)"', content)
        pick = match.group(1) if match else None
        if pick is None:  # last resort: the model answered with a bare id or a label
            for candidate in sorted(ids, key=len, reverse=True):
                if re.search(rf"(?<![\w-]){re.escape(candidate)}(?![\w-])", content):
                    pick = candidate
                    break
        if pick is None:
            return RawAnswer(error=f"no id in the answer: {content.strip()[:200]!r}",
                             latency_ms=latency, model=self.model,
                             input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost)

        return RawAnswer(pick=pick, confidence=None, probabilities={}, model=self.model,
                         input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost,
                         latency_ms=latency, raw=content.strip()[:400])

    def describe(self) -> str:
        return f"openai model={self.model} base_url={self.base_url}"
