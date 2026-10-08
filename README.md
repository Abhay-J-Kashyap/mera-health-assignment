# Diabetes follow-up call list

Finds diabetic patients who are overdue for follow-up in the hospital's export (`export/`) and builds a call list for the front desk. Every patient gets a status and a written reason.

## Run
Tested on Python 3.14 (Windows) with pandas 3.0.6 and pandas 2.3.3; both give identical output. pandas 3 itself needs Python 3.11+. Older Pythons are untested.

```
pip install -r requirements.txt
python overdue.py
```

By default, "overdue" is measured as of the export's last visit date (29 Sep 2026), so the same export always gives the same list. To measure to another date, e.g. today: `python overdue.py --as-of 2026-10-08`.

To keep the install separate, create a virtual environment first: `python -m venv .venv`, then activate it (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on Mac/Linux).

## Output (`output/`)
| File | For | Contents |
|---|---|---|
| `call_list.html` | Front desk | Printable list (landscape): who to call, most overdue first, with a caller note and other visits since. The two review lists below are included. Each row has an **Outcome dropdown** (see below). |
| `call_list.csv` | Front desk / Excel | Same call list, plus the diabetes evidence for each patient and an empty `outcome` column |
| `review_for_doctor.csv` | Doctor | High blood-sugar results with no diabetes diagnosis recorded. Not for the front desk to call. |
| `review_for_records_team.csv` | Records team | Records to fix before anyone calls: registered twice (shown once), no phone, impossible date of birth |
| `exclusions.csv` | Audit | Patients who looked diabetic but are not called, and why |
| `all_patients.csv` | Audit | Every patient's status and reason, one row per hospital number |
| `data_fixes.csv` | Audit | Every change made to the data, with its csv line |
| `summary.txt` | Audit | Counts per status (they add up to the 300 patients), review counts, borderline calls |

### Recording call outcomes
After each call, pick an outcome in `call_list.html`:
- Booked follow-up appointment
- Already has an appointment
- No answer: try again
- Asked to call back later
- Declined follow-up
- Wrong / not-working number (tell records team)
- Treated elsewhere or moved away (tell records team)
- Patient has died (tell records team)
- Other (tell records team)

Choices are kept in that browser on that computer only (per list date). **Export outcomes (CSV)** saves them as a file to send to the records team. On a printout, a chosen outcome prints as text and a blank one leaves space to write. These choices are provisional until the hospital says how it records calls.

## Other files
- `PLAN.md`: the plan, committed before any code.
- `DECISIONS.md`: definitions, data problems, what was flagged for a person, and limits.
- `reply.txt`: the email back to the hospital.
- `profile_export.py`: read-only data profiling. Its report is in `profiling/`.
- `check_assumptions.py`: which call-list names change if the assumptions change.
- `CLAUDE.md`: the rules I set for the coding agent.

## Changing the assumptions
Two assumptions await the hospital's answer, and both can be changed without editing code:

```
python overdue.py --default-months 6 --grace-days 30
```

- `--default-months` (default 3) is the follow-up gap when the doctor wrote no date.
- `--grace-days` (default 14) is how many days past due before a patient counts as overdue.

`python check_assumptions.py` shows which call-list names change under different as-of dates, default gaps and grace periods. The rows that would change are marked "borderline" in the call list. Diagnostic thresholds are constants at the top of `overdue.py`.

## What I'd do next
1. **Apply the hospital's answers** when they arrive: the definitions, `--default-months` and `--grace-days`, then re-run and update every figure.
2. **Check the appointment book.** Matching the call list against the real booking system would remove the biggest wrong-call risk (DECISIONS §4).
3. **A merge workflow for duplicate records,** confirmed by a person, so merged patients go back into the normal flow.
4. **Record call outcomes properly,** once the hospital says how they'll use the list (question 5). The Outcome dropdown is a stand-in.
5. **Reach patients last seen before Oct 2023** from an older export.
6. **Let doctors set priority.** Ordering by clinical risk (e.g. HbA1c) is a clinical judgement. I'd offer it as an option for doctors to choose, not a default.
7. **Eye, foot and kidney checks** ("fundus check due", "urine microalbumin adv") as separate overdue items.
8. **A small test set for the note reader:** the phrases that fooled it (negations, "impaired fasting glucose"), so later changes can't bring those mistakes back.

## How I worked with the agent
I used Claude Code throughout; the transcripts are in `transcripts/`, unedited. Where I steered or corrected it:

- **Plan before code.** I stopped the agent from writing `PLAN.md` until I had reviewed it and iterated on it. I decided what went in the email to the hospital, and the plan was committed before any code. I also reiterated the plan multiple times before writing the code. 
- **Decisions logged as they happen.** I created the `DECISIONS.md`. I then set a standing rule that every critical decision is logged when it's made, and had a project `CLAUDE.md` written so the rules survive across sessions.
- **Specifics over length.** To fit 2 pages, the agent cut the names of the patients whose status depends on assumptions. I ruled that losing specifics is worse than going over the length limit. Later I set a firm 2-page limit. It was met by moving "What I'd do next" into this README and removing repetition, with every definition, name and count kept.
- **An independent review of the first version found 6 issues the agent had missed.** I ran the review in a separate agent session; that session's transcript is included. I checked each point and decided what to change, and I also checked the data myself, e.g. looking up SVH026167 in `visits.csv`. The 6 issues:
  1. "Impaired fasting glucose" written out wasn't recognised as prediabetes.
  2. An appointment date silently overrode a conflicting interval in the doctor's note.
  3. The reply undercounted overdue patients, counting only the callable ones.
  4. Two limits weren't stated: the export starts in Oct 2023, and future appointment dates *are* in it.
  5. The ADA sources were old summaries.
  6. Nothing showed how much the list depends on the assumptions.

  This agent verified each one against the data before changing anything; for #6 it found one more name than the review had. Further rounds from the separate session, each checked and decided by me, led to:
  - the export-date default
  - the split review lists
  - the borderline flag
  - showing doctors every diabetic-range result

  They also pointed out places where my documents had fallen out of step with the outputs, or claimed more than the data supports (e.g. treating `next_appointment` as a confirmed booking).
- **What the agent caught or corrected itself:** profiling disproved the plan's drug rule (insulin given in pregnancy). It also claimed a pandas 2 bug, then tested it and withdrew the claim.
- **Agreements:** when the agent asked me to choose (stack, output, the 3-month default, flagging duplicates instead of merging), I picked its recommended option each time. I agreed with its reasons; I didn't overrule it on those.
