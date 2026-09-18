"""A bounded decision layer for browser and desktop automation.

The loop shape this library implements:

    observe (your code)  ->  decide (a chooser)  ->  act (your code)  ->  verify (your code)

Only the second step is a model. Everything that can fail silently stays in code:
the observation is serialized by the library, the candidate list is built from what
the harness can actually execute, the sentinels (done / stuck) are checked before
the answer is trusted, the confidence floor is applied in code, and the
postcondition is verified without the model's involvement.
"""

from jev_pilot.loop import run_episode
from jev_pilot.perception import DomRules, Element, options_from_elements, parse_snapshot
from jev_pilot.policy import DONE, STUCK, build_criteria, build_instructions
from jev_pilot.providers.base import Chooser
from jev_pilot.safety import SafetyError, SafetyPolicy
from jev_pilot.serialize import SerializerOptions, build_state
from jev_pilot.types import Decision, Episode, Option, Step
from jev_pilot.verify import VerificationContext, parse_postcondition, verify_all

def _installed_version() -> str:
    """The version of the package that is actually installed.

    It was a literal, which drifted from `pyproject.toml` the first time the version was bumped:
    a wheel built as 0.1.1 still reported 0.1.0. Reading the installed metadata keeps the two in
    step, and the source-tree fallback is obviously not a release.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version as _version

        try:
            return _version("jev-browser-pilot")
        except PackageNotFoundError:
            return "0.0.0+source"
    except ImportError:  # pragma: no cover - importlib.metadata is present on 3.8+
        return "0.0.0+source"


__version__ = _installed_version()

__all__ = [
    "Chooser",
    "DONE",
    "Decision",
    "DomRules",
    "Element",
    "Episode",
    "Option",
    "STUCK",
    "SafetyError",
    "SafetyPolicy",
    "SerializerOptions",
    "Step",
    "VerificationContext",
    "build_criteria",
    "build_instructions",
    "build_state",
    "options_from_elements",
    "parse_postcondition",
    "parse_snapshot",
    "run_episode",
    "verify_all",
    "__version__",
]
