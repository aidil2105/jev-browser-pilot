"""Where each chooser wins and loses, per category, from a bench report JSON."""

import json
import sys
from collections import defaultdict
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
fixture = json.loads(
    (Path(__file__).resolve().parents[1] / "examples" / "bench-decisions.json")
    .read_text(encoding="utf-8")
)
cases = {c["name"]: c for c in fixture["cases"]}
results = report.get("results", [])

per_chooser = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for r in results:
    kind = "abstain" if (cases.get(r["case"], {}).get("expect", "") or "").startswith("__") else "pick"
    chooser = r["chooser"]
    per_chooser[chooser][kind][1] += 1
    if r.get("correct"):
        per_chooser[chooser][kind][0] += 1

print(f"{'chooser':52s} {'picks':>9s} {'abstentions':>13s}")
for chooser, kinds in per_chooser.items():
    picks, abst = kinds["pick"], kinds["abstain"]
    print(f"{chooser:52s} {picks[0]:>4}/{picks[1]:<4} {abst[0]:>6}/{abst[1]:<6}")

print()
print("per case, the Jev arm: expect -> got")
for r in results:
    if not r["chooser"].startswith("jev"):
        continue
    case = cases.get(r["case"], {})
    mark = "ok " if r.get("correct") else "MISS"
    print(f"  {mark} {r['case'][:34]:34s} expect={str(case.get('expect')):>9s} "
          f"got={str(r.get('pick')):>9s} {r.get('outcome')}")

misses = [r["case"] for r in results if r["chooser"].startswith("jev") and not r.get("correct")]
print()
print(f"jev misses ({len(misses)}): {misses}")
for name in misses:
    case = cases.get(name, {})
    print(f"  - {name}: goal={case.get('goal')!r} expect={case.get('expect')} "
          f"label={case.get('expect_label')!r} notes={case.get('notes')!r}")
