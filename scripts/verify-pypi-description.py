"""Compare what PyPI shows for a release against the README in that release's own commit."""

import difflib
import json
import subprocess
import sys
import urllib.request

VERSION = sys.argv[1] if len(sys.argv) > 1 else "0.2.1"

with urllib.request.urlopen(f"https://pypi.org/pypi/jev-browser-pilot/{VERSION}/json", timeout=60) as r:
    info = json.load(r)["info"]

published = (info.get("description") or "")
local = subprocess.run(["git", "show", f"v{VERSION}:README.md"], capture_output=True, text=True,
                       encoding="utf-8", check=True).stdout

# normalise only line endings: anything else that differs is a real difference
def norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

pub, loc = norm(published), norm(local)
print(f"version:              {info['version']}")
print(f"published description: {len(pub)} chars, {pub.count(chr(10))} lines")
print(f"README at v{VERSION}:    {len(loc)} chars, {loc.count(chr(10))} lines")
print(f"identical after line-ending normalisation: {pub == loc}")
if pub != loc:
    print("\nfirst differences:")
    diff = list(difflib.unified_diff(loc.splitlines(), pub.splitlines(),
                                     fromfile=f"v{VERSION}:README.md", tofile="pypi description",
                                     lineterm="", n=1))
    for line in diff[:40]:
        print("  " + line)
else:
    # the two specific sentences that motivated this release must be the ones now published
    for needle in ["endpoint-failures.txt", "1000-request daily cap, exhausted",
                   "docs/findings.md section 10 rather than quietly"]:
        print(f"  published text contains {needle!r}: {needle in pub}")
