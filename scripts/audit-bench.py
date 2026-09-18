import json
import re
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "examples" / "bench-decisions.json"
d = json.loads(path.read_text(encoding="utf-8"))
cases = d["cases"]
print(f"cases: {len(cases)}")
print(f"source: {d['source'][:80]}...")

problems = []
for c in cases:
    ids = {o["id"] for o in c["options"]}
    expect = c["expect"]
    if expect not in ("__done__", "__stuck__"):
        if expect.startswith("id:"):
            bare = expect[3:]
            if bare not in ids:
                problems.append((c["name"], f"expect names id {bare!r}, which is not among the options"))
        elif expect in ids:
            problems.append((c["name"], "expect is a bare option id: the bench reads that as a label, "
                                       "so it must be written as id:<id>"))
        else:
            labels = {o["label"] for o in c["options"]}
            if expect not in labels:
                problems.append((c["name"], f"expect {expect!r} is neither a sentinel, an id: value, "
                                            "nor one of the option labels"))
    if expect in ("__done__", "__stuck__"):
        continue
    goal_words = set(re.findall(r"[a-z]{4,}", c["goal"].lower()))
    label_words = set(re.findall(r"[a-z]{4,}", c["expect_label"].lower()))
    if not (goal_words & label_words):
        problems.append((c["name"], f"goal shares no word with the expected label: "
                                    f"{c['expect_label']!r}"))
print("structural problems:", problems or "none")

counts = {}
for c in cases:
    counts[c["category"]] = counts.get(c["category"], 0) + 1
print("categories:", json.dumps(counts, indent=1, sort_keys=True))

print()
for c in cases:
    kind = "abstain" if c["expect"].startswith("__") else "pick"
    print(f"{kind:8s} {c['name'][:32]:32s} expect={c['expect']:>9s} {c['expect_label'][:28]}")

lengths = sorted(len(c["state"]) for c in cases)
counts_opts = sorted(len(c["options"]) for c in cases)
print()
print(f"state chars: min {lengths[0]} median {lengths[len(lengths) // 2]} max {lengths[-1]}")
print(f"options per case: min {counts_opts[0]} median {counts_opts[len(counts_opts) // 2]} "
      f"max {counts_opts[-1]}")

# the invariant that matters: a case's expected answer must not be given away by the state text
leaks = [c["name"] for c in cases
         if c["expect"] not in ("__done__", "__stuck__")
         and c.get("target") and c["target"].rstrip("/") not in (c["state"] or "")]
print(f"cases where the state does not contain the target URL: {len(leaks)} of {len(cases)}")
leaky = [c["name"] for c in cases
         if c["expect"] not in ("__done__", "__stuck__")
         and c.get("target") and c["target"] in (c["state"] or "")]
print("cases where the state DOES contain the target URL:", leaky or "none")
