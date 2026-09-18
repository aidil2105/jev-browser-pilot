"""Capture frozen decision states from real pages, with the expected answer derived from the DOM.

Why this exists: a benchmark is only as good as its ground truth. Taking the answer from a model's
pick makes the set circular (the arm that made the pick scores perfectly), and labelling by hand is
slow and hard to check. Every case here is derived mechanically instead:

- one page load produces several cases, each with a different goal;
- the expected answer is the candidate whose link target is the article the goal names, which the
  harness knows (`Element.url`) and the chooser does not;
- where a page links the target more than once, the extra links are dropped, so the task has exactly
  one right answer;
- two abstention shapes are captured on purpose: the goal is already satisfied (expect `__done__`),
  and the goal names an article the page cannot reach (expect `__stuck__`).

Run:  .venv/Scripts/python.exe scripts/capture-bench.py --out examples/bench-decisions.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_pilot.browser import BrowserPilot                     # noqa: E402
from jev_pilot.perception import DomRules                      # noqa: E402
from jev_pilot.safety import SafetyPolicy                      # noqa: E402

WIKI = "https://en.wikipedia.org/wiki/"

# One entry per page load. `targets` are the articles the goals will name; each becomes a case.
PAGES: Sequence[Dict[str, Any]] = [
    {"page": WIKI + "Calculator", "targets": ["Slide_rule", "William_Oughtred"],
     "category": "wikipedia-calculator"},
    {"page": WIKI + "Slide_rule", "targets": ["William_Oughtred", "Richard_Delamaine"],
     "category": "wikipedia-slide-rule"},
    {"page": WIKI + "William_Oughtred", "targets": ["Richard_Delamaine", "Napier%27s_bones"],
     "category": "wikipedia-oughtred"},
    {"page": WIKI + "Logarithm", "targets": ["John_Napier", "Slide_rule"],
     "category": "wikipedia-logarithm"},
    {"page": WIKI + "Abacus", "targets": ["Slide_rule", "Roman_abacus"],
     "category": "wikipedia-abacus"},
    {"page": WIKI + "Mechanical_calculator", "targets": ["Slide_rule", "Difference_engine"],
     "category": "wikipedia-mechanical"},
    {"page": WIKI + "Nomogram", "targets": ["Slide_rule", "Logarithm"],
     "category": "wikipedia-nomogram"},
    {"page": WIKI + "Richter_scale", "targets": ["Seismometer", "Logarithm"],
     "category": "wikipedia-richter"},
]

UNREACHABLE = "https://example.invalid/wiki/Nonexistent_article_xyz"


def _path(url: str) -> str:
    """The comparable part of a link target: path only, no host, no fragment, no query."""
    parsed = urlparse(url or "")
    path = parsed.path if parsed.scheme or parsed.netloc else (url or "").split("#")[0]
    return path.rstrip("/")


def _expected_id(snapshot, target_path: str) -> Optional[str]:
    """The one candidate that links to the target path."""
    matches = [el for el in snapshot.elements if _path(el.url) == target_path]
    return matches[0].id if matches else None


def _options(excluding: Sequence[str] = ()) -> List[Dict[str, str]]:
    return []


def build_cases(pilot: BrowserPilot, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    page = spec["page"]
    page_title = page[len(WIKI):] if page.startswith(WIKI) else page
    pilot.go(page)
    snapshot = pilot.observe()
    rules = DomRules()
    options = [{"id": el.id, "label": el.label()} for el in snapshot.elements]
    state = rules_stub_state(snapshot)
    cases: List[Dict[str, Any]] = []

    for target in spec["targets"]:
        target_path = _path(WIKI + target)
        target_title = target.replace("_", " ").replace("%27", "'")
        expected = _expected_id(snapshot, target_path)
        if expected is None:
            print(f"  skip {page_title} -> {target}: not linked from this page")
            continue
        expected_element = next(el for el in snapshot.elements if el.id == expected)
        # If the page links the same article twice, keep only the first link: two right answers
        # would make the case unfair to a chooser that picked the other one.
        duplicates = [el.id for el in snapshot.elements if _path(el.url) == target_path][1:]
        case_options = [o for o in options if o["id"] not in duplicates] or options
        notes = "duplicate links to the same article were removed" if duplicates else ""
        # A link whose visible text does not contain the target's name is a harder case, and worth
        # marking: the chooser has to infer it from context rather than match the words.
        goal_words = set(re.findall(r"[a-z]{4,}", f"open the article about {target_title}".lower()))
        label_words = set(re.findall(r"[a-z]{4,}", expected_element.label().lower()))
        if not (goal_words & label_words):
            notes = ((notes + "; ") if notes else "") + (
                f"the link text {expected_element.label()!r} does not contain the target's name"
            )
        cases.append({
            "name": f"{page_title.lower()}->{target.lower()}",
            "category": spec.get("category", "wikipedia"),
            "goal": f"open the article about {target_title}",
            "state": state,
            "options": case_options,
            # `id:` is the bench's encoding for "an act on exactly this option". A bare id would be
            # read as a label to match, which is how a correct run first showed up as a total miss.
            "expect": f"id:{expected}",
            # auditability: which link decided the answer, and what the chooser sees for it
            "expect_label": expected_element.label(),
            "target": WIKI + target,
            "notes": notes,
        })

    # abstention 1: the article the goal names is already open
    cases.append({
        "name": f"{page_title.lower()}->already-open",
        "category": spec.get("category", "wikipedia") + "-abstain",
        "goal": f"make sure the article about {page_title.replace('_', ' ')} is the one being read",
        "state": state,
        "options": options,
        "expect": "__done__",
        "expect_label": "",
        "target": page,
        "notes": "the goal is satisfied by the current page; starting a click would be wrong",
    })

    # abstention 2: an article this page cannot reach
    cases.append({
        "name": f"{page_title.lower()}->unreachable",
        "category": spec.get("category", "wikipedia") + "-abstain",
        "goal": "open the article about Nonexistent article xyz",
        "state": state,
        "options": options,
        "expect": "__stuck__",
        "expect_label": "",
        "target": UNREACHABLE,
        "notes": "no candidate on this page links to that article",
    })
    return cases


def rules_stub_state(snapshot) -> str:
    """The state text exactly as the loop would build it, so the bench measures the real thing."""
    from jev_pilot.serialize import build_state

    return build_state(options=[_option_from(el) for el in snapshot.elements], url=snapshot.url,
                       title=snapshot.title, text=snapshot.text,
                       matched_total=snapshot.matched_total)


def _option_from(element):
    from jev_pilot.types import Option

    return Option(id=element.id, label=element.label())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="examples/bench-decisions.json")
    parser.add_argument("--chrome", default=None)
    args = parser.parse_args()

    host = urlparse(WIKI).hostname
    pilot = BrowserPilot(WIKI + "Calculator", chrome=args.chrome, headless=True,
                         rules=DomRules(),
                         safety=SafetyPolicy.for_hosts([host], allow_actions=("click",)))
    cases: List[Dict[str, Any]] = []
    try:
        pilot.start()
        for spec in PAGES:
            print(f"capturing {spec['page']}")
            try:
                cases.extend(build_cases(pilot, spec))
            except Exception as exc:                              # keep going on one bad page
                print(f"  page failed: {type(exc).__name__}: {exc}")
    finally:
        pilot.close()

    payload = {
        "source": ("captured from live Wikipedia pages and the local fixture site by "
                   "scripts/capture-bench.py; every expected answer is derived from a link target "
                   "in the DOM, never from a model's pick"),
        "cases": cases,
    }
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    by_category: Dict[str, int] = {}
    for case in cases:
        by_category[case["category"]] = by_category.get(case["category"], 0) + 1
    print(f"\nwrote {out} with {len(cases)} cases")
    for category, count in sorted(by_category.items()):
        print(f"  {category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
