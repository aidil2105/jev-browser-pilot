"""State construction: the exact text a chooser sees.

Two rules from the failures that produced this library:

1. the state carries only what an accessibility tree would show (role, visible name,
   value, enabled). No link targets, no element ids that encode the answer, no
   filenames. A label must never hint at where the action leads;
2. the state is complete about *what the harness did so far*. UIA and DOM trees are
   both lossy about mode (an armed operator, a pending selection), and a model that
   cannot see its own history repeats it.

Anything the caller wants the model to know beyond that belongs in the goal, in the
perception rules, or in `extra_lines` for a task-specific fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from jev_pilot.perception import Element
from jev_pilot.types import Option


@dataclass(frozen=True)
class SerializerOptions:
    include_url: bool = True
    include_title: bool = True
    text_chars: int = 400
    history_items: int = 20
    max_label: int = 120
    header: str = "CANDIDATE ACTIONS"

    def normalize(self, value: Optional[str]) -> str:
        return re.sub(r"\s+", " ", value or "").strip()


def build_state(
    *,
    options: Sequence[Option] = (),
    elements: Sequence[Element] = (),
    url: Optional[str] = None,
    title: Optional[str] = None,
    text: Optional[str] = None,
    history: Iterable[str] = (),
    matched_total: Optional[int] = None,
    extra_lines: Sequence[str] = (),
    scroll: Optional[str] = None,
    opts: Optional[SerializerOptions] = None,
) -> str:
    """Render the observation. Deterministic for identical inputs."""
    opts = opts or SerializerOptions()
    if not options and elements:
        options = [Option(id=str(el.id), label=el.label()) for el in elements]

    lines = []
    if opts.include_url and url:
        lines.append(f"URL: {url}")
    if opts.include_title and title:
        lines.append(f"TITLE: {opts.normalize(title)}")
    if text:
        clipped = opts.normalize(text)[: opts.text_chars]
        suffix = " ..." if len(opts.normalize(text)) > opts.text_chars else ""
        lines.append(f"VISIBLE PAGE TEXT: {clipped}{suffix}")

    history = list(history)[-opts.history_items:]
    lines.append(f"ACTIONS ALREADY TAKEN THIS EPISODE: {', '.join(history) if history else '(none)'}")

    for line in extra_lines:
        if line:
            lines.append(str(line))

    if matched_total is not None:
        kept = len(options)
        if matched_total > kept:
            lines.append(
                f"NOTE: {kept} of {matched_total} candidates are shown; the rest were "
                "dropped by the perception cap and are not selectable."
            )
    if scroll:
        lines.append(f"PAGE POSITION: {scroll}")

    lines.append(f"{opts.header} (answer with one id from this list):")
    if not options:
        lines.append("(none)")
    else:
        for opt in options:
            label = opt.label[: opts.max_label]
            lines.append(f"[{opt.id}] {label}")
    return "\n".join(lines)
