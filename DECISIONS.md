# DECISIONS

Figures below are from `python overdue.py --as-of 2026-10-08`. Of 300 patients: **38 CALL**, 34 NOT_DUE, 19 REVIEW, 26 EXCLUDED, 183 NOT_DIABETIC. Every patient's status and reason is in `output/all_patients.csv`.

## 0. Decisions made before writing code
- **Ask only what changes the build.** The email to the hospital asks:
  1. who counts as diabetic
  2. what "overdue" means
  3. which visits count as follow-up
  4. whether the export is complete, including future bookings
  5. how the list will be used

  I deliberately didn't ask about things I could work out and document myself: date and unit formats, test-name mapping, diagnostic thresholds, drug classes, duplicate detection, and whether to skip deceased or transferred patients (obviously yes). The tool runs on working assumptions until the hospital answers (§1).
- **Profile before building.** `profile_export.py` is read-only and counts every problem; its output is in `profiling/profile_report.txt`. Every rule below was written after seeing those counts.
- **Raw export committed untouched.** All cleaning happens in code and is logged, so every change can be traced.
- **Flag, don't merge, suspected duplicate patients.** A wrong merge sends a real phone call to the wrong person.
- **Three lists, not one:** call / needs review / excluded. Uncertain cases go to a person instead of being guessed.
- **Plain output:** CSVs for Excel and one printable HTML page; Python + pandas, run with two commands. `output/` is not committed, because it holds names and phone numbers.
- **Where PLAN.md was wrong** (it stays as committed): the plan counted any non-metformin diabetes drug as proof of diabetes. One gestational-diabetes patient was given insulin during pregnancy, so drugs prescribed at pregnancy visits are now ignored.

## 1. Terms in the email

**"Diabetic"** means a doctor recorded diabetes (Type 1 or 2) in a visit note, or the patient is on a diabetes medicine other than metformin alone. Pregnancy visits don't count for either.
- *Why not metformin:* every patient on metformin alone without a diabetes note has PCOS (4) or gestational diabetes (1).
- *Notes are read clause by clause.* Clauses that negate diabetes or describe family history are dropped. Without this, 8 people would have been included because of phrases like "No h/o diabetes", "Denies diabetes", "Non-diabetic" and "Father diabetic".
- *Excluded:*
  - gestational diabetes only (2)
  - prediabetes / borderline sugars (3)
  - one diabetic-range HbA1c that was normal on repeat (3). ADA requires a repeat test to confirm.
- *Wrongly left out:* diabetics whose notes use none of our words and who take only metformin; anyone diagnosed elsewhere and never written up here.
- *Wrongly included:* a note like "?DM" (query diabetes) would count. I saw none, but the check is a word match, not a reading.

**"Follow-up"** means a diabetes review: a diabetes or sugar discussion in Diabetology, General Medicine or Paediatrics, or diabetes medicine prescribed. A dental or orthopaedic visit doesn't reset the clock. Neither does a blood test on its own.

**"Overdue"** means more than 14 days past the due date, with no diabetes review since. The due date comes from the last review, in this order:
1. the doctor's `next_appointment`
2. else the interval written in the note ("review 3 months", "r/v 3/12" = 3 months)
3. else 3 months

The 3-month default is the interval doctors write most often here, and it matches ADA's quarterly testing when not at goal. The 14-day grace keeps people a few days late off the list.

**"Patient"** is one person, not one MRN: 4 people have two MRNs each. **"Front desk can call"** means a phone number exists and identity can be confirmed. Each call-list row has a date of birth to check and a note for the caller (child: speak to parent; shared phone; same name as another patient).

## 2. Data problems and what I did
Every change is logged to `output/data_fixes.csv` with its csv line.

| Problem | Action |
|---|---|
| Lab dates in 3 formats | Parsed each. Slash dates are DD/MM: read as MM/DD, 238 are impossible. |
| HbA1c under 3 names, in % and mmol/mol; glucose in mg/dL and mmol/L | One name each, converted to % and mg/dL (NGSP = 0.09148 × IFCC + 2.152; mmol/L × 18). |
| 3 HbA1c values (65, 65, 68) with no unit | Treated as mmol/mol, since >20 is impossible as %. Logged. |
| 4 exact duplicate lab rows | Second copy dropped. Logged. |
| 1 visit dated 2015; 2 labs dated in the future | Year corrected. Each row sits between neighbours from the corrected year in a date-ordered file. Logged. |
| 4 people registered twice (same DOB and phone, e.g. Joseph Dsouza / D'Souza) | Not merged. History combined to compute the due date; all 8 records go to REVIEW. |
| Same name, different people (Lakshmi Devi, Ravi Kumar, Sunitha Rao) | Never matched on name. Caller confirms date of birth. |
| 3 phones shared within families; 8 patients with no phone | Caller asks for the patient by name. If no phone and overdue: REVIEW. |
| 1 patient born after their registration date | If overdue: REVIEW. |
| Deaths (3) and transfers (3) recorded only in note text | Excluded, with the note quoted. |
| `next_appointment` blank on 582 of 815 visits | Written interval or default used. |
| 3 overdue diabetics had sugar tests in Sept 2026 but no visit since 2025 | Kept on the call list, with a caller note. Either they skipped review or the export is missing visits. |

## 3. Flagged for a person instead of deciding (19 records)
- **Diabetic-range blood results, no diagnosis recorded: 9 records, 8 people.** Examples: HbA1c 8.2% with "increased thirst"; 8.1% "reports to be collected, review SOS"; 6.6% after gestational diabetes. Telling someone they may have diabetes is a doctor's job. This is probably the most important output.
- **4 duplicate pairs (8 records):** merge, then call.
- **3 overdue patients with no phone; 1 with an impossible date of birth.**

## 4. What this can't be trusted for
- **Completeness.** It only sees this export (last visit 29 Sep 2026). Bookings in other systems and later visits are invisible, so someone already booked may be called.
- **Deaths and transfers not written in a note.** Those patients will be called.
- **Clinical priority.** Ordered by days overdue, not by how unwell anyone is.
- **Eye, foot and kidney checks.** "Fundus check due" and similar are not tracked.
- **The 3-month default and 14-day grace.** Both are assumptions until the hospital answers.

## 5. What I looked up
- ADA diagnostic criteria (HbA1c ≥ 6.5%, fasting glucose ≥ 126 mg/dL, repeat to confirm): https://www.aafp.org/afp/2010/0715/p206 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC2797382/
- ADA HbA1c frequency (twice yearly at goal, quarterly if not): https://www.aafp.org/pubs/afp/issues/2006/0901/p871.html
- HbA1c unit conversion: https://ngsp.org/ifccngsp.asp
- Not looked up (agent's knowledge of Indian clinical shorthand): k/c/o = known case of; r/v 3/12 = review in 3 months; OHA = oral hypoglycaemic agent; GRBS = random blood sugar; metformin is used for PCOS.
