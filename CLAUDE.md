# CLAUDE.md

Instructions for the coding agent working in this repo. Read before changing anything.

## What this is
mera.health engineering-intern take-home (`brief.md`). A hospital asked: "which diabetic patients are overdue for follow-up so the front desk can call them". The data is the messy export in `export/`. The brief grades **process and care**, not code: how "diabetic" and "overdue" are defined, how data problems are handled, what goes to a person instead of being decided, and a reasoning trail that can be explained. Time budget: about 4 hours.

## Hard rules
1. **Never edit `PLAN.md`.** It was committed before any code, and the brief says not to change it. If the plan turns out wrong, record that in `DECISIONS.md` §0.
2. **Log every critical decision in `DECISIONS.md` when it's made**, in the right section (§0 pre-code, §1 terms, §2 data problems, §3 flagged for review, §4 can't be trusted for, §5 looked up). The brief says 2 pages max, but the user's call is: **going over is fine; losing important information is not.** Trim repetition only, never specifics (names, counts, cases).
3. **Never modify `export/`.** All cleaning happens in code, and every change is logged via `log_fix()` to `output/data_fixes.csv`. A silent change, merge or drop is a rejection criterion in the brief.
4. **Never merge suspected duplicate patients.** Flag both records to REVIEW and combine their history only to compute the due date. A wrong merge means a call to the wrong person.
5. **Never match people on name alone.** Same-name different-people exist (Lakshmi Devi, Ravi Kumar, Sunitha Rao).
6. **Every patient gets exactly one status with a written reason.** Statuses: CALL, NOT_DUE, REVIEW, EXCLUDED, NOT_DIABETIC. The counts must sum to the number of rows in `patients.csv` (300).
7. **Uncertain means REVIEW, not CALL.** Lab-only diabetic-range results go to a doctor, not the front desk.
8. **Never commit `output/`** (names and phone numbers; regenerated each run) or `.venv/`.
9. **Don't state numbers you haven't produced.** Figures in `DECISIONS.md`, `reply.txt` and the README come from an actual **bare** run (`python overdue.py`, as of the export's last date, 2026-09-29). If a rule changes, re-run and update every figure.
10. **Commit as you go, never squash.** The git history is graded. End commit messages with the Co-Authored-By line used in earlier commits.
11. **Health-data care beats convenience.** Before a change that alters who is on the call list, re-run and diff the call list and say who moved and why.

## Working definitions (details and reasons in DECISIONS.md §1)
- **Diabetic:** a diabetes mention in a note clause (negations and family history removed; prediabetes and gestational clauses excluded), or a non-metformin glucose-lowering drug. Evidence from pregnancy visits is ignored.
- **Follow-up visit:** diabetes or sugar content in Diabetology, General Medicine or Paediatrics, or a glucose-lowering drug prescribed. A lab test alone doesn't count.
- **Overdue:** more than 14 days past the due date, measured by default as of the export's last visit date. The due date comes from `next_appointment` (shown alongside the note when they disagree), else the interval written in the note, else 3 months.
- **Borderline:** a CALL row that wouldn't survive a 6-month default, a 30-day grace, or measuring from the export date gets "check the appointment book first". It must match `check_assumptions.py`.
- These are working assumptions until the hospital answers the 5-question email (see DECISIONS §0). If they answer, update the constants at the top of `overdue.py` and DECISIONS.

## Files
| Path | Role |
|---|---|
| `brief.md`, `email.txt`, `export/` | Inputs as received (do not edit) |
| `PLAN.md` | Pre-code plan (frozen) |
| `profile_export.py` → `profiling/profile_report.txt` | Read-only data profiling (committed) |
| `overdue.py` | The tool: load and clean, read notes, classify, follow-up, outputs |
| `check_assumptions.py` | Re-runs `overdue.py` under alternative assumptions and diffs the call list |
| `output/` | call_list.csv/.html, review_for_doctor.csv, review_for_records_team.csv, exclusions.csv, all_patients.csv, data_fixes.csv, summary.txt (not committed) |
| `DECISIONS.md` | Graded deliverable. The brief says max 2 pages; the user chose to exceed it rather than lose specifics (see rule 2) |
| `reply.txt` | Graded deliverable: email to Meenakshi, max 200 words, non-technical, not a doctor |

## Commands (Windows, PowerShell)
```
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python overdue.py                        # reference run: as of export end (2026-09-29)
.\.venv\Scripts\python overdue.py --as-of 2026-10-08    # measure to another date
.\.venv\Scripts\python check_assumptions.py
.\.venv\Scripts\python profile_export.py
```

## Status
- [x] PLAN.md committed before code
- [x] Profiling
- [x] overdue.py, with hand checks: exclusions, review list, duplicate pairs, call-list spot checks against raw CSVs
- [x] DECISIONS.md (first full version)
- [x] User sent the 5-question email. **No reply yet.** When it arrives, update definitions/constants, re-run, update DECISIONS, reply.txt and figures.
- [x] reply.txt (197 words, signed by the user; as of 29 Sep: 42 overdue / 35 callable / 4 borderline; 8 for a doctor, 7 for the records team)
- [x] Iteration 3: export-date default; review split by who acts (pairs shown once); borderline flag; Outcome and Other-visits columns; DECISIONS §6 "What I'd do next"; README "How I worked with the agent" (wording confirmed and edited by the user; reviews described as partly the user's own and partly a separate agent session, as the user stated)
- [x] Doctor list shows every diabetic-range result (4 of 8 have two or more); print rows don't split across pages
- [x] README.md with run instructions (tested on pandas 3.0.6 and 2.3.3)
- [x] Review fixes: "impaired fasting glucose" → prediabetes; booking-vs-note disagreement shown; caller flag for "overdue only after export end"; `--default-months` / `--grace-days` flags; `check_assumptions.py`; current ADA 2026 citations
- [x] Final pass: re-ran the bare command; every figure in DECISIONS, reply and README matches (21 checks). DECISIONS stays over 2 pages by the user's choice.
- [ ] **Before submitting:** user exports the agent transcripts, unedited, to `transcripts/`. The README already says they're there, so this must happen.
