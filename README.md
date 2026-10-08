# Diabetes follow-up call list

Finds diabetic patients who are overdue for follow-up in the hospital's export (`export/`) and builds a call list for the front desk. Every patient gets a status and a written reason.

## Run
Tested on Python 3.14 (Windows) with pandas 3.0.6 and pandas 2.3.3; both give identical output. pandas 3 itself needs Python 3.11+. Older Pythons are untested.

```
pip install -r requirements.txt
python overdue.py --as-of 2026-10-08
```

Leave out `--as-of` to measure from today. To keep the install separate, create a virtual environment first: `python -m venv .venv`, then activate it (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on Mac/Linux).

## Output (`output/`)
| File | For | Contents |
|---|---|---|
| `call_list.html` | Front desk | Printable list: who to call, most overdue first, with a note for the caller. Also the needs-review list. |
| `call_list.csv` | Front desk / Excel | Same call list, plus the diabetes evidence for each patient |
| `needs_review.csv` | Doctor / records team | Patients a person must check before anyone calls, and why |
| `exclusions.csv` | Audit | Patients who looked diabetic but are not called, and why |
| `all_patients.csv` | Audit | Every patient's status and reason |
| `data_fixes.csv` | Audit | Every change made to the data, with its csv line |
| `summary.txt` | Audit | Counts per status; they add up to the 300 patients |

## Other files
- `PLAN.md`: the plan, committed before any code.
- `DECISIONS.md`: definitions, data problems, what was flagged for a person, and limits.
- `reply.txt`: the email back to the hospital.
- `profile_export.py`: read-only data profiling. Its report is in `profiling/`.

Assumptions you may want to change are constants at the top of `overdue.py`: `DEFAULT_INTERVAL_MONTHS` (3), `GRACE_DAYS` (14), and the diagnostic thresholds.
