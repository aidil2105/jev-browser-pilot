"""Tool schema for the jev_decide tool.

The schema is the contract with the calling model: every field here is something the
jev-pilot CLI's `decide` subcommand understands, and nothing here invents capability the
library does not have. `done` and `stuck` are not fields: the policy offers them as sentinels
on every decision, so a caller never has to ask for them.
"""

from __future__ import annotations

from typing import Any, Dict

JEV_DECIDE: Dict[str, Any] = {
    "name": "jev_decide",
    "description": (
        "Ask a decision-only model to pick the next step from a candidate list you have already "
        "built. Returns exactly one typed answer: a pick from your list, or __done__ (the goal is "
        "already achieved), __stuck__ (no candidate can advance the goal), escalate (the model is "
        "not confident enough to pick, with the pick it would have made attached), or error. It "
        "never invents an id, never acts, and never verifies: you execute the pick and check the "
        "result yourself. Costs about $0.0003 and 300 ms per call. Use it when the next step is a "
        "choice among visible options; use your own judgement when the work is open-ended."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": (
                    "What the episode is trying to achieve, in one sentence, with enough detail to "
                    "tell a right pick from a wrong one."
                ),
            },
            "options": {
                "type": "array",
                "description": (
                    "The candidates you can actually execute. The id is what you will receive back "
                    "and act on; the name is what the decision model sees, so describe the element "
                    "the way a person reading a screenshot would."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Your own identifier for this option."},
                        "name": {
                            "type": "string",
                            "description": "The visible label, for example a 'slide rule' or Button '7'.",
                        },
                        "detail": {
                            "type": "string",
                            "description": "Optional extra context shown after the name, e.g. a URL.",
                        },
                    },
                    "required": ["id", "name"],
                },
            },
            "state": {
                "type": "string",
                "description": (
                    "What the model can see, as text: the page or window you are on, the relevant "
                    "page text, and the actions already taken this episode. Plain text, no markup."
                ),
            },
            "confidence_floor": {
                "type": "number",
                "description": (
                    "Below this confidence the answer comes back as escalate instead of act, with "
                    "the pick attached. 0 accepts everything; 0.6 is a reasonable start."
                ),
            },
            "provider": {
                "type": "string",
                "description": "Decision provider: jev (default), or any OpenAI-compatible endpoint via openai.",
            },
            "model": {
                "type": "string",
                "description": "Model name, required when provider is openai.",
            },
        },
        "required": ["goal", "options"],
    },
}
