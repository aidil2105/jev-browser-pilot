"""Perception: turn a live surface into a candidate list the chooser can pick from.

Two producers ship here:

- `DomRules` / `serialize_js()` for a browser page (the JS runs inside the page and
  returns a snapshot the library parses with `parse_snapshot`);
- `elements_from_uia()` for a desktop window already read through an accessibility
  tree (the shape cua-driver's `get_window_state` returns).

Both end at `Element`, and `options_from_elements()` is the only place an `Option`
id is minted. Indices are snapshot-local by design: the browser stamps each kept
element with `data-jev-idx` while collecting, so the click step addresses the same
element that was described to the chooser.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from jev_pilot.types import Option

# Structure that is never a real choice: navigation chrome, tables, infoboxes,
# reference lists, thumbnails, edit affordances and screen-reader-only text.
DEFAULT_EXCLUDES = (
    "table",
    ".navbox",
    ".infobox",
    ".sidebar",
    ".metadata",
    ".reflist",
    ".reference",
    ".thumb",
    ".gallery",
    ".hatnote",
    ".shortdescription",
    ".mw-editsection",
    ".mw-cite-backlink",
    "sup",
    "style",
    "script",
    "noscript",
)

DEFAULT_SKIP_PATTERNS = (
    r"^\[(edit|update|citation needed)\]$",
    r"^\W*$",
)


@dataclass(frozen=True)
class Element:
    """One addressable thing the harness could act on."""

    id: str
    role: str
    name: str
    value: Optional[str] = None
    enabled: bool = True

    @property
    def clean_name(self) -> str:
        return " ".join(self.name.split())

    def label(self) -> str:
        """What the chooser sees. Only what an accessibility tree would show."""
        name = self.clean_name
        text = f"{self.role} {name!r}" if self.role else repr(name)
        if self.value not in (None, "") and self.value != name:
            text += f" value={self.value!r}"
        if not self.enabled:
            text += " (disabled)"
        return text

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"id": self.id, "role": self.role, "name": self.clean_name}
        if self.value not in (None, ""):
            out["value"] = self.value
        if not self.enabled:
            out["enabled"] = False
        return out


def options_from_elements(elements: Sequence[Element]) -> List[Option]:
    """Mint the candidate table. Ids are the element ids, labels are the tree's words."""
    return [Option(id=str(el.id), label=el.label()) for el in elements]


@dataclass(frozen=True)
class DomRules:
    """The serializer's rules. One source of truth for the JS and for the parser."""

    root_selectors: Sequence[str] = (
        "#mw-content-text",
        "main",
        "article",
        "[role=main]",
        "#content",
        "body",
    )
    interactive_selector: str = (
        "a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link]"
    )
    exclude_selectors: Sequence[str] = DEFAULT_EXCLUDES
    skip_patterns: Sequence[str] = DEFAULT_SKIP_PATTERNS
    cap: int = 200
    require_letter: bool = True
    max_text_chars: int = 70
    stamp_attribute: str = "data-jev-idx"

    def js(self) -> str:
        """The in-page serializer. Deterministic: same DOM in, same list out."""
        return _SERIALIZE_JS_TEMPLATE.replace(
            "__ROOTS__", json.dumps(list(self.root_selectors))
        ).replace(
            "__INTERACTIVE__", json.dumps(self.interactive_selector)
        ).replace(
            "__EXCLUDES__", json.dumps(", ".join(self.exclude_selectors))
        ).replace(
            "__SKIP__", json.dumps([re.compile(p, re.IGNORECASE).pattern for p in self.skip_patterns])
        ).replace(
            "__CAP__", str(int(self.cap))
        ).replace(
            "__REQUIRE_LETTER__", "true" if self.require_letter else "false"
        ).replace(
            "__MAX_TEXT__", str(int(self.max_text_chars))
        ).replace(
            "__STAMP__", json.dumps(self.stamp_attribute)
        )


@dataclass
class Snapshot:
    """A parsed observation. `matched_total` is what the rules found, kept is what fit."""

    url: Optional[str] = None
    title: Optional[str] = None
    text: str = ""
    elements: List[Element] = field(default_factory=list)
    matched_total: Optional[int] = None

    @property
    def truncated(self) -> bool:
        return self.matched_total is not None and self.matched_total > len(self.elements)

    def options(self) -> List[Option]:
        return options_from_elements(self.elements)


def parse_snapshot(payload: Dict[str, Any], rules: Optional[DomRules] = None) -> Snapshot:
    rules = rules or DomRules()
    raw = payload.get("elements") or []
    elements: List[Element] = []
    for position, item in enumerate(raw):
        name = str(item.get("text") or item.get("name") or "").strip()
        if not name:
            continue
        elements.append(Element(
            id=str(item.get("index", position)),
            role=str(item.get("role") or item.get("tag") or ""),
            name=name,
            value=item.get("value"),
            enabled=bool(item.get("enabled", not item.get("disabled", False))),
        ))
    return Snapshot(
        url=payload.get("url"),
        title=payload.get("title"),
        text=str(payload.get("text") or ""),
        elements=elements,
        matched_total=payload.get("matched_total"),
    )


def elements_from_uia(raw: Iterable[Dict[str, Any]], *, cap: int = 200) -> List[Element]:
    """Normalize an accessibility tree (cua-driver `get_window_state` shape)."""
    out: List[Element] = []
    for item in raw:
        name = str(item.get("label") or item.get("name") or "").strip()
        if not name:
            continue
        out.append(Element(
            id=str(item.get("element_index", len(out))),
            role=str(item.get("role") or ""),
            name=name,
            value=item.get("value"),
            enabled=bool(item.get("enabled", True)),
        ))
        if len(out) >= cap:
            break
    return out


_SERIALIZE_JS_TEMPLATE = r"""
(() => {
  const ROOTS = __ROOTS__;
  const INTERACTIVE = __INTERACTIVE__;
  const EXCLUDES = __EXCLUDES__;
  const SKIP = __SKIP__;
  const CAP = __CAP__;
  const REQUIRE_LETTER = __REQUIRE_LETTER__;
  const MAX_TEXT = __MAX_TEXT__;
  const STAMP = __STAMP__;

  let scope = document.body;
  for (const sel of ROOTS) {
    const found = document.querySelectorAll(sel);
    if (found.length) { scope = found[0]; break; }
  }

  const out = [];
  const seen = new Set();
  let matched = 0;
  const nodes = scope.querySelectorAll(INTERACTIVE);

  for (const el of nodes) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '')
      .trim().replace(/\s+/g, ' ');
    if (!text || text.length < 1) continue;
    if (REQUIRE_LETTER && !/[A-Za-z]/.test(text)) continue;
    let skip = false;
    for (const re of SKIP) { if (new RegExp(re, 'i').test(text)) { skip = true; break; } }
    if (skip) continue;
    if (EXCLUDES && el.closest(EXCLUDES)) continue;
    const key = text.toLowerCase() + '|' + (el.getAttribute('href') || '');
    if (seen.has(key)) continue;
    seen.add(key);
    matched++;
    if (out.length >= CAP) continue;
    const index = out.length;
    el.setAttribute(STAMP, String(index));
    out.push({
      index: index,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      text: text.slice(0, MAX_TEXT),
      value: (el.value || '').toString().slice(0, MAX_TEXT) || null,
      enabled: !el.disabled
    });
  }

  const bodyText = ((document.body && document.body.innerText) || '').replace(/\s+/g, ' ').trim();
  return {
    url: location.href,
    title: document.title,
    text: bodyText.slice(0, 4000),
    elements: out,
    matched_total: matched
  };
})()
"""


def stamp_selector(rules: DomRules, option_id: str) -> str:
    """CSS that addresses exactly the element the chooser was told about."""
    safe = str(option_id).replace('"', "")
    return f'[{rules.stamp_attribute}="{safe}"]'


def click_js(rules: DomRules, option_id: str) -> str:
    selector = json.dumps(stamp_selector(rules, option_id))
    return (
        "(() => { const el = document.querySelector(" + selector + ");"
        " if (!el) return {clicked: false, reason: 'element not found'};"
        " el.scrollIntoView({block: 'center'}); el.click();"
        " return {clicked: true, tag: el.tagName.toLowerCase()}; })()"
    )


def probe_js(selector: str) -> str:
    """Existence probe for a postcondition check, run in the page."""
    return f"(() => !!document.querySelector({json.dumps(selector)}))()"
