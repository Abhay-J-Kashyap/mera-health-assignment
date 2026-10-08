"""Which call-list names depend on the assumptions? Runs overdue.py under variations and diffs."""
import subprocess
import sys

import pandas as pd

PY = sys.executable
BASE = ["--as-of", "2026-10-08"]
VARIANTS = {
    "as of export end (2026-09-29)": ["--as-of", "2026-09-29"],
    "default gap 6 months": BASE + ["--default-months", "6"],
    "default gap 2 months": BASE + ["--default-months", "2"],
    "grace 0 days": BASE + ["--grace-days", "0"],
    "grace 30 days": BASE + ["--grace-days", "30"],
}


def call_list(args):
    subprocess.run([PY, "overdue.py", *args], check=True, capture_output=True)
    return pd.read_csv("output/call_list.csv")


base = call_list(BASE)
dropped_any = set()
for label, args in VARIANTS.items():
    v = call_list(args)
    out = base[~base.mrn.isin(v.mrn)]
    dropped_any |= set(out.mrn)
    print(f"{label:32s} call={len(v):3d}  drop off: {out.name.tolist()}  "
          f"added: {v[~v.mrn.isin(base.mrn)].name.tolist()}")
print(f"\nNames that hold under every variation: {len(base) - len(dropped_any)} of {len(base)}")
call_list(BASE)  # leave output/ at the baseline
