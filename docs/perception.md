# Perception

Perception, not model quality, is what decides whether a bounded loop works. Every failure in the
project this library came from looked like a model failure and was a perception failure.

## Rules (`DomRules`)

The serializer runs inside the page. It picks the first matching root, walks the interactive
selector, and keeps an element only if:

| rule | reason |
|---|---|
| visible (`display`, `visibility`, `opacity`) | hidden controls are not choices |
| has text (inner text, value, aria-label, title) | an unlabeled control cannot be described |
| contains at least one letter | drops bare footnote markers like `[12]` |
| does not match the skip patterns | drops `[edit]`, `[update]`, punctuation-only labels |
| not inside an excluded container | tables, navboxes, infoboxes, reference lists, thumbnails, superscripts, edit links |
| unique by `text + href` | de-duplicates repeated calls to action |

Then the list is **capped** (default 200; the model's choice space tops out at 255 with the two
sentinels). The cap is reported to the model as a note, and to the log as
`matched_total` versus kept, which is the number that tells you whether to raise it.

## Index fidelity

Each kept element is stamped with `data-jev-idx` **while collecting**. The click step addresses
that attribute, so the element clicked is exactly the element described. The alternative,
re-querying the DOM with the same selector, re-derives a different order on a live page and clicks
the wrong element.

Indices are snapshot-local and must never be persisted. The same target was index 107 on one page
load and 139 on the next, because the page rendered slightly differently.

## What never reaches the model

- link targets, filenames and URLs of the candidates (they leak the answer: an early version
  labelled a link `Open the Alpha report -> alpha.html`);
- element handles, tokens, ids from the driver;
- screenshots. Text only, by design: it is cheaper, auditable and diffable.

## What must always reach the model

Anything the page does not say. UI Automation trees and DOMs are both lossy about mode: after
clicking `Plus`, a calculator's display still reads `5` and nothing in the tree exposes the armed
operator, so a model without a history clicks `Plus` again. The state therefore carries
`ACTIONS ALREADY TAKEN THIS EPISODE`, and callers can add facts with `extra_lines`.

## Accessibility trees (`elements_from_uia`)

The desktop surface normalizes a UI Automation tree into the same `Element` shape: role, visible
name, value, enabled. Labels keep the tree's own words (`Button 'Five'`, not `5`), which is why
test expectations and goals must match the interface language rather than the intended meaning.

## Debugging recipe

1. `jev-pilot run ... --dump-state` prints the exact state the chooser would see, then exits.
2. If the goal's target is missing from the list, it is a rules problem: check `matched_total`,
   widen the cap, add an exclusion, or pick a different root.
3. If the target is present and the model still abstains, it is a state-completeness problem: add
   the missing fact (history, mode, units) to the state.
4. Only then is it worth questioning the model.

## Known blind spots

- long articles and virtualised lists: content past the cap is invisible;
- canvas and game surfaces: no accessible elements to describe;
- Electron and web apps that expose a thin tree: the vision path (screenshots plus OCR regions)
  is not included here, and would be a separate perception adapter.
