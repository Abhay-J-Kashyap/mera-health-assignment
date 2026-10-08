# PLAN

**Goal.** Turn "which diabetic patients are overdue for follow-up" into a call list the front desk can trust. Every name on it comes with a reason. Anything uncertain goes to a separate list for a person to check.

**First, find out (before building):**
1. Profile each CSV: row counts, duplicates, date and unit formats, orphan IDs (visit_ids in prescriptions with no visit; MRNs in visits/labs with no patient).
2. How diabetes is recorded: note phrases, drugs, lab names and units. Who looks diabetic on one signal but not another?
3. How follow-up intent is recorded: the `next_appointment` column vs. intervals written in notes.
4. Who must never be called: deceased, transferred, duplicate records, missing or shared phones.

**Working definitions (provisional; the email may change them):**
- *Diabetic* = a clinician documented diabetes (Type 1 or 2) in a visit note, or the patient is on a diabetes-only drug (not metformin alone). Gestational diabetes, prediabetes and metformin-for-PCOS are excluded. Lab-only evidence goes to doctor review, not the call list.
- *Overdue* = as of the run date, no diabetes-related visit since the follow-up date the doctor set. That date comes from `next_appointment`, else from the interval in the last note, else a default interval (from guidelines or the hospital's answer).

**Build:** one Python script that reads the export and writes (a) a call list sorted by days overdue, with phone, last visit, due date and the evidence for inclusion, (b) a needs-review list, and (c) a count of who was excluded and why.

**Unsure about:** whether non-diabetes visits reset the clock; what default interval to use; whether the export includes future bookings; whether Type 1 children belong on the same list; how to treat records I suspect are the same person.

**Check by:** hand-tracing about 10 patients end-to-end, including every trap case above.
