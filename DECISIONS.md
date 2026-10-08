# DECISIONS

Figures below are from `python overdue.py`, measured as of the export's last visit date, **29 Sep 2026**. Of 300 patients: **35 CALL**, 37 NOT_DUE, 19 REVIEW, 27 EXCLUDED, 182 NOT_DIABETIC. **42 diabetics are overdue: 35 can be called now, and 7 need their records fixed first** (§3). Every patient's status and reason is in `output/all_patients.csv`.

## 0. Decisions made before writing code
- **Ask only what changes the build.** The email to the hospital asks: who counts as diabetic, what "overdue" means, which visits count as follow-up, whether the export is complete, and how the list will be used. I didn't ask about things I could work out myself (formats, units, thresholds, drug classes, duplicates). No reply yet; §1 lists the working assumptions.
- **Profile before building** (`profile_export.py`, read-only). Raw export committed untouched; all cleaning is in code and logged.
- **Flag, don't merge, suspected duplicates.** A wrong merge sends a real call to the wrong person.
- **Three lists** (call / needs review / excluded), so uncertain cases go to a person. Output is CSVs for Excel plus one printable HTML page, run with two commands. `output/` is not committed: it holds names and phones.
- **Measure from the export's last date, not today** (decided after the first version). The same export then always gives the same list, whenever it's run. Measuring to today, 8 Oct, would add 3 people who may well have visited after the export was taken. `--as-of` still allows any date, and with a fresh weekly export the two dates are nearly the same.
- **Review list split by who acts on it** (decided after the first version): one list for a doctor, one for the records team. A double-registered person is shown once. `all_patients.csv` still has one row per hospital number.
- **Where PLAN.md was wrong** (it stays as committed): it counted any non-metformin diabetes drug as proof of diabetes. One gestational-diabetes patient was given insulin in pregnancy, so drugs prescribed at pregnancy visits are ignored.

## 1. Terms in the email
**"Diabetic"** means a doctor recorded diabetes (Type 1 or 2) in a visit note, or the patient is on a diabetes medicine other than metformin alone. Pregnancy visits don't count for either.
- *Why not metformin:* every patient on metformin alone without a diabetes note has PCOS (4) or gestational diabetes (1).
- *Notes are read clause by clause.* Clauses that negate diabetes or describe family history are dropped. Without this, 8 people would have been included because of phrases like "No h/o diabetes", "Denies diabetes" and "Father diabetic".
- *Excluded:*
  - gestational diabetes only (2)
  - prediabetes / borderline sugars (4)
  - one diabetic-range HbA1c that was normal on repeat (3). ADA requires two abnormal results.
- *Caught in review of the first version:* "Impaired fasting glucose" written out in full wasn't recognised as prediabetes, only the abbreviation "IFG". It's fixed, and that patient moved from NOT_DIABETIC to EXCLUDED.
- *Wrongly left out:* diabetics whose notes use none of our words and who take only metformin; anyone diagnosed elsewhere.
- *Wrongly included:* a note like "?DM" (query diabetes) would count. I saw none, but the check is a word match, not a reading.

**"Follow-up"** means a diabetes review: a diabetes or sugar discussion in Diabetology, General Medicine or Paediatrics, or diabetes medicine prescribed. A dental or orthopaedic visit doesn't count. Neither does a blood test on its own.

**"Overdue"** means more than 14 days past the due date as of 29 Sep 2026 (the export's last date), with no diabetes review since. The due date comes from the last review, in this order:
1. the doctor's `next_appointment`
2. else the interval written in the note ("r/v 3/12" = 3 months)
3. else 3 months (ADA: check every 3 months when not at goal)

A booked date wins over the note, because the patient holds that booking. Where the two disagree by more than a month, the reason shows both. There are 2 such cases, both NOT_DUE: Rashmi G Menon (note says May, booked 15 Oct) and U. Harish (note says June, booked 7 Oct).

**How much depends on these assumptions** (`python check_assumptions.py`): 31 of the 35 names hold under every variation tried. The 4 that don't are marked **borderline** in the caller note ("check the appointment book first"). The flag is computed by the tool, not hand-picked, and it marks exactly these 4:
- **6-month default instead of 3:** K. Madhusudan and Vasantha Pillai drop off. Their due date is our 3-month estimate, not the doctor's.
- **30-day grace instead of 14:** Manjula D (28 days overdue) and Rashmi Bhat (17) drop off.
- **The other way:** measuring to 8 Oct, or using no grace, adds Renuka Iyengar, Vimala P and Lakshmi Devi (SVH028218). A 2-month default adds Vimala P. If run for a later date, anyone overdue only because time has passed since the export is also flagged borderline.

**"Patient"** is one person, not one MRN. **"Can call"** means a phone exists and identity can be confirmed. Each row has a date of birth, a caller note, any non-diabetes visits since (e.g. "seen in Dental on 4 Aug"), and a blank Outcome column for the caller.

## 2. Data problems and what I did
Every change is logged to `output/data_fixes.csv` with its csv line.

| Problem | Action |
|---|---|
| Lab dates in 3 formats | Parsed each. Slash dates are DD/MM: read as MM/DD, 238 are impossible. |
| HbA1c in % and mmol/mol under 3 names; glucose in mg/dL and mmol/L | Converted to % and mg/dL (NGSP = 0.09148 × IFCC + 2.152; mmol/L × 18). |
| 3 unitless HbA1c (65, 65, 68); 4 duplicate lab rows | mmol/mol (>20 is impossible as %); second copies dropped. |
| 1 visit dated 2015; 2 labs dated in the future | Year corrected; each sits between neighbours from that year in a date-ordered file. |
| 4 people registered twice (same DOB and phone) | Not merged. History combined for the due date; all 8 records go to REVIEW. |
| Same name, different people (Lakshmi Devi, Ravi Kumar, Sunitha Rao) | Never matched on name. Caller confirms date of birth. |
| 3 family-shared phones; 8 patients with no phone | Caller asks for the patient by name. No phone and overdue: REVIEW. |
| 1 patient born after their registration date | If overdue: REVIEW. |
| Deaths (3) and transfers (3) only in note text | Excluded, with the note quoted. |
| `next_appointment` blank on 582 of 815 visits | Note interval or default used (§1). |
| 3 overdue diabetics had sugar tests in Sept 2026 but no visit since 2025 | Kept on the list, with a caller note. Either they skipped review or the export is missing visits. |

## 3. Flagged for a person instead of deciding (19 records, 15 people, two lists)
- **For a doctor (`review_for_doctor.csv`, 8 people):** diabetic-range blood results but no diagnosis recorded. Examples: HbA1c 8.2% with "increased thirst"; 8.1% "reports to be collected, review SOS"; 6.6% after gestational diabetes. A diagnosis needs a doctor (and, per ADA, a second abnormal result). Each row lists every diabetic-range result across the person's records. 4 of the 8 already have two or more; the other 4 have one result, not yet repeated. One of the 8, Md. Rafiq, is also registered twice; his row says so and combines both records' results. Probably the most important output.
- **For the records team (`review_for_records_team.csv`, 7 people):** 3 people registered twice (all overdue; merge, then call), 3 overdue patients with no phone, and 1 with an impossible date of birth.

## 4. What this can't be trusted for
- **Completeness.** Visits start in Oct 2023, so a diabetic last seen before then is not in this export at all, even though they would be the most overdue. Bookings made at a visit are included (27 fall after 29 Sep). Bookings made any other way, and anything after 29 Sep, are invisible.
- **Deaths and transfers not written in a note.** Those patients will be called.
- **Clinical priority.** Ordered by days overdue, not by how unwell anyone is.
- **Eye, foot and kidney checks.** "Fundus check due" and similar are not tracked.
- **The edges of the list.** 4 of the 35 depend on the default gap or grace period, and they're marked borderline (§1).

## 5. What I looked up
- ADA *Standards of Care in Diabetes—2026*, *Diabetes Care* 49(Suppl 1):
  - §2: HbA1c ≥ 6.5%, FPG ≥ 126 mg/dL; Rec 2.1b, confirm with a second result. https://pmc.ncbi.nlm.nih.gov/articles/PMC12690183/
  - §6, Rec 6.2: assess at least twice a year, every 3 months if not at goal. https://pmc.ncbi.nlm.nih.gov/articles/PMC12690178/
- HbA1c unit conversion: https://ngsp.org/ifccngsp.asp
- Not looked up (agent's knowledge): k/c/o = known case of; r/v 3/12 = review in 3 months; OHA = oral diabetes tablet; GRBS = random sugar; metformin is used for PCOS.

## 6. What I'd do next
1. **Apply the hospital's answers** when they arrive: the definitions, `--default-months` and `--grace-days`, then re-run and update every figure.
2. **Check the appointment book.** Matching the call list against the real booking system would remove the biggest wrong-call risk (§4).
3. **A merge workflow for duplicate records,** confirmed by a person, so merged patients go back into the normal flow.
4. **Record call outcomes,** once the hospital says how they'll use the list (question 5). The Outcome column is a paper stand-in.
5. **Reach patients last seen before Oct 2023** from an older export.
6. **Let doctors set priority.** Ordering by clinical risk (e.g. HbA1c) is a clinical judgement; I'd offer it as an option for doctors to choose, not a default.
7. **Eye, foot and kidney checks** ("fundus check due", "urine microalbumin adv") as separate overdue items.
8. **A small test set for the note reader:** the phrases that fooled it (negations, "impaired fasting glucose"), so later changes can't bring those mistakes back.
