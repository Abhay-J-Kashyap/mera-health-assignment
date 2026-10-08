# DECISIONS

Figures are from `python overdue.py`, as of the export's last visit date, **29 Sep 2026**. Of 300 patients: **35 CALL**, 37 NOT_DUE, 19 REVIEW, 27 EXCLUDED, 182 NOT_DIABETIC. **42 diabetics are overdue: 35 can be called now, and 7 need their records fixed first** (§3). Every patient's status and reason is in `output/all_patients.csv`.

## 0. Approach
- **Ask the hospital only what changes the build:** who is diabetic, what "overdue" means, what counts as follow-up, whether the export is complete, and how the list will be used. No reply yet, so §1 holds the working assumptions.
- **Profile before building.** The raw export is committed untouched; all cleaning is in code and logged.
- **Flag suspected duplicates, never merge them.** A wrong merge means calling the wrong person.
- **Uncertain cases go to a person** (§3), not onto the call list.
- **Measure from the export's last date, not today,** so the same export always gives the same list (`--as-of` overrides).
- **PLAN.md was wrong once** (it stays as committed): it took any non-metformin drug as proof of diabetes, but a gestational-diabetes patient was given insulin.

## 1. Terms in the email
**"Diabetic"** means a doctor recorded diabetes (Type 1 or 2) in a visit note, or the patient takes a diabetes medicine other than metformin alone. Pregnancy visits don't count for either. Children with Type 1 diabetes stay on the same list, with a caller note to speak to a parent or guardian (PLAN.md's open question).
- *Metformin alone isn't enough:* every such patient without a diabetes note has PCOS (4) or gestational diabetes (1).
- *Notes are read clause by clause.* Negations and family history ("No h/o diabetes", "Denies diabetes", "Father diabetic") are dropped; otherwise 8 people would be wrongly included.
- *Excluded:* gestational diabetes only (2); prediabetes / borderline sugars (4); one diabetic-range HbA1c that was normal on repeat (3), since ADA requires two abnormal results. ("Impaired fasting glucose" in full was missed at first, then fixed.)
- *Wrongly left out:* diabetics whose notes use none of our words and who take only metformin; anyone diagnosed elsewhere. *Wrongly included:* a "?DM" (query diabetes) note would count. I saw none; the check is a word match, not a reading.

**"Follow-up"** means a diabetes review: diabetes or sugars discussed in Diabetology, General Medicine or Paediatrics, or diabetes medicine prescribed. Dental or orthopaedic visits don't count, and neither does a blood test on its own.

**"Overdue"** means more than 14 days past the due date, with no diabetes review since. The due date comes from the last review: the doctor's `next_appointment`, else the interval in the note ("r/v 3/12" = 3 months), else 3 months (ADA: check every 3 months when not at goal). `next_appointment` wins over the note. It's the date the doctor set, not a known booking (§4). Where the two disagree by more than a month, the reason shows both. That applies to 2 patients, both NOT_DUE: Rashmi G Menon (note says May, date set for 15 Oct) and U. Harish (note says June, date set for 7 Oct).

**Sensitivity** (`check_assumptions.py`): 31 of 35 names hold under every variation. The tool flags the other 4 as **borderline** ("check the appointment book first"):
- **6-month default:** K. Madhusudan and Vasantha Pillai drop off (their due date is our estimate).
- **30-day grace:** Manjula D (28 days overdue) and Rashmi Bhat (17) drop off.
- **Other way:** measuring to 8 Oct, or using no grace, adds Renuka Iyengar, Vimala P and Lakshmi Devi (SVH028218). A 2-month default adds Vimala P.

**"Patient"** is one person, not one hospital number. **"Can call"** means a phone exists and identity can be confirmed. Each row has a date of birth, a caller note and an Outcome dropdown (provisional until question 5 is answered).

## 2. Data problems and what I did
Every change is logged, with its csv line, in `output/data_fixes.csv`.

| Problem | Action |
|---|---|
| Lab dates in 3 formats | Parsed. Slash dates are DD/MM: read as MM/DD, 238 are impossible. |
| HbA1c in % and mmol/mol, glucose in mg/dL and mmol/L, under 3 names each | Converted to % (NGSP formula) and mg/dL (×18) |
| 3 HbA1c with no unit (65, 65, 68); 4 duplicate lab rows | Read as mmol/mol (>20 is impossible as %); copies dropped |
| 1 visit dated 2015; 2 labs dated in the future | Year corrected from neighbouring rows |
| 4 people registered twice | Not merged; history combined for the due date; REVIEW |
| Same name, different people (Lakshmi Devi, Ravi Kumar, Sunitha Rao) | Never matched on name; caller confirms date of birth |
| 3 phones shared within families; 8 patients with no phone | Ask for the patient by name; no phone and overdue: REVIEW |
| 1 patient born after registration | If overdue: REVIEW |
| Deaths (3) and transfers (3) only in note text | Excluded, with the note quoted |
| `next_appointment` blank on 582 of 815 visits | Note interval or default used |
| 3 overdue diabetics tested in Sept 2026, no visit since 2025 | Kept, with a caller note |

## 3. Flagged for a person instead of deciding (19 records, 15 people)
- **For a doctor (8):** diabetic-range blood results but no diagnosis recorded. Examples: HbA1c 8.2% with "increased thirst"; 8.1% with "reports to be collected"; 6.6% after gestational diabetes. Each row lists every such result: 4 people have two or more (the confirmation ADA asks for), and 4 have one. Md. Rafiq is also registered twice; his row combines both records. Probably the most important output.
- **For the records team (7):** 3 people registered twice (all overdue), 3 overdue patients with no phone, and 1 with an impossible date of birth.

## 4. What this can't be trusted for
- **Completeness.** Every patient in the export has a visit on or after 2 Oct 2023. Diabetics last seen before then, who would be the most overdue, aren't in the export at all. Anything after 29 Sep, or booked outside a visit, is invisible.
- **Appointment dates.** `next_appointment` is the date the doctor set, not a confirmed booking. Of the 206 such dates due by 29 Sep, only 17 were followed by a visit within 14 days (6 on or after the date; `profile_export.py`). 27 more fall after 29 Sep.
- **Deaths and transfers not written in a note.** Those patients will be called.
- **Clinical priority.** The list is ordered by days overdue, not by how unwell anyone is.
- **Eye, foot and kidney checks.** These aren't tracked.

## 5. What I looked up
- ADA *Standards of Care in Diabetes—2026*, *Diabetes Care* 49(Suppl 1):
  - §2: HbA1c ≥ 6.5%, FPG ≥ 126 mg/dL; Rec 2.1b, confirm with a second result. https://pmc.ncbi.nlm.nih.gov/articles/PMC12690183/
  - §6, Rec 6.2: assess at least twice a year, every 3 months if not at goal. https://pmc.ncbi.nlm.nih.gov/articles/PMC12690178/
- HbA1c unit conversion: https://ngsp.org/ifccngsp.asp
- Not looked up (agent's knowledge): k/c/o = known case of; r/v 3/12 = review in 3 months; OHA = oral diabetes tablet; GRBS = random sugar; metformin is used for PCOS.
