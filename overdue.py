"""Which diabetic patients are overdue for follow-up? Builds the front-desk call list.

Run:
    pip install -r requirements.txt
    python overdue.py                      # as of the export's last visit date
    python overdue.py --as-of 2026-10-08   # as of a given date, e.g. today

Reads export/*.csv (never modifies them) and writes everything to output/.
Every patient in patients.csv ends up with exactly one status and a reason:
    CALL          diabetic, overdue, safe to call
    NOT_DUE       diabetic, follow-up not yet overdue
    REVIEW        a person must check before anyone calls (see reason)
    EXCLUDED      looked diabetic on some signal but must not be called (see reason)
    NOT_DIABETIC  no evidence of diabetes
The rules are explained in DECISIONS.md.
"""
import argparse
import html
import re
from pathlib import Path

import pandas as pd

EXPORT = Path("export")
OUT = Path("output")

DEFAULT_INTERVAL_MONTHS = 3  # most common interval doctors write here; ADA: quarterly if not at goal
GRACE_DAYS = 14
ALT_DEFAULT_MONTHS = 6  # alternatives a call must survive to not be flagged borderline
ALT_GRACE_DAYS = 30  # (the same variations check_assumptions.py runs)
HBA1C_DIABETIC = 6.5  # %, ADA diagnostic threshold
FPG_DIABETIC = 126  # mg/dL fasting glucose, ADA diagnostic threshold
ADULT_AGE = 18
REVIEW_DEPARTMENTS = {"Diabetology", "General Medicine", "Paediatrics"}

# --- note vocabulary (matched per clause, lower case) ------------------------
DIABETES = re.compile(r"diabet|\bt1dm\b|\bt2dm\b|\bdm2?\b|\bniddm\b|\biddm\b|\bohas?\b|\bdka\b")
NEGATED_OR_FAMILY = re.compile(
    r"\bno h/o\b|\bdenies\b|non-?diabetic|\bf/h\b|family history|\bfather\b|\bmother\b|\bparents?\b|\bbrother\b|\bsister\b"
)
PREDIABETES = re.compile(
    r"pre-?diabet|\bigt\b|\bifg\b|impaired (?:fasting glucose|glucose tolerance)"
    r"|sugars?\s+borderline|borderline\s+(?:high\s+)?sugars?"
)
GESTATIONAL = re.compile(r"\bgdm\b|gestational")
PREGNANCY = re.compile(r"\banc\b|\bpnc\b|\bgdm\b|gestational|pregnan")
TYPE_1 = re.compile(r"\bt1dm\b|type\s*1\b|juvenile")
GLYCAEMIC = re.compile(
    r"\bfbs\b|\bppbs\b|hba1c|\bgrbs\b|\bsmbg\b|\bsugars?\b|\bf \d+\s*/\s*pp|\binsulin\b|\bhypo\b|\bohas?\b|dose stepped up"
)
PCOS = re.compile(r"\bpco[sd]?\b|polycystic")
DECEASED = re.compile(r"expired|deceased|\bdied\b|could not be revived")
TRANSFERRED = re.compile(r"transfer(?:red)? (?:of )?care|transfer summary|relocat|another hospital|native place")

UNIT = r"(/12|/52|/7|months?|mths?|wks?|weeks?|days?|yrs?|years?)"
REVIEW_IN = re.compile(r"\b(?:review|r/v|f/u)\s*(?:after|in)?\s*(\d+)\s*" + UNIT + r"(?!\w)")
REPEAT_IN = re.compile(r"\b(?:rpt|repeat)\b[^.;,]{0,20}?(\d+)\s*" + UNIT + r"(?!\w)")

GLUCOSE_LOWERING = {
    "glimepiride": "other", "gliclazide": "other", "sitagliptin": "other", "vildagliptin": "other",
    "dapagliflozin": "other", "voglibose": "other", "insulin": "insulin", "mixtard": "insulin",
    "metformin": "metformin",
}

fixes = []  # every change made to the data, written to output/data_fixes.csv


def log_fix(file, row, field, old, new, reason):
    fixes.append({"file": file, "csv_line": row, "field": field, "old": old, "new": new, "reason": reason})


# =============================================================================
# Load and clean
# =============================================================================
def read(name):
    df = pd.read_csv(EXPORT / name, dtype=str, keep_default_na=False)
    df["csv_line"] = df.index + 2  # header is line 1
    return df


def fix_year_typos(df, col, file):
    """Both files are in date order. A date out of order with BOTH neighbours (so a typo next
    to it doesn't implicate it) is corrected to the neighbours' year, if that puts it back in order."""
    dates = df[col].copy()
    month = pd.Timedelta(days=30)
    for i in range(1, len(df) - 1):
        d, before, after = dates.iloc[i], dates.iloc[:i].dropna(), dates.iloc[i + 1:].dropna()
        if pd.isna(d) or before.empty or after.empty:
            continue
        p, n = before.iloc[-1], after.iloc[0]
        too_early = d < p - month and d < n - month
        too_late = d > p + month and d > n + month
        if not (too_early or too_late):
            continue
        for year in sorted({p.year, n.year}):
            candidate = d.replace(year=year)
            if p <= candidate <= n:
                log_fix(file, df["csv_line"].iloc[i], col, d.date(), candidate.date(),
                        f"year typo: row sits between {p.date()} and {n.date()} in a date-ordered file")
                dates.iloc[i] = candidate
                break
        else:
            log_fix(file, df["csv_line"].iloc[i], col, d.date(), d.date(), "out of date order; left unchanged")
    df[col] = dates


def load():
    patients = read("patients.csv")
    for c in ["dob", "registered_on"]:
        patients[c] = pd.to_datetime(patients[c], format="%Y-%m-%d")

    visits = read("visits.csv")
    visits["visit_date"] = pd.to_datetime(visits["visit_date"], format="%Y-%m-%d")
    # Blank means no appointment. (.where, not .replace("", None): on pandas 2.x that fills blanks
    # with the previous row's date.)
    nappt = visits["next_appointment"]
    visits["next_appointment"] = pd.to_datetime(nappt.where(nappt != ""), format="%Y-%m-%d")
    fix_year_typos(visits, "visit_date", "visits.csv")

    labs = read("lab_results.csv")
    dup = labs.duplicated(subset=["mrn", "test_name", "value", "unit", "reference_range", "collected_on"])
    for line in labs.loc[dup, "csv_line"]:
        log_fix("lab_results.csv", line, "(row)", "duplicate", "dropped", "exact duplicate of an earlier row")
    labs = labs[~dup].reset_index(drop=True)
    labs["collected_on"] = labs["collected_on"].map(parse_lab_date)
    fix_year_typos(labs, "collected_on", "lab_results.csv")
    labs = normalise_labs(labs)

    rx = read("prescriptions.csv")
    rx["drug_class"] = rx["drug"].map(drug_class)
    return patients, visits, labs, rx


def parse_lab_date(text):
    # DD/MM/YYYY, not MM/DD: read as MM/DD, 238 of these dates are impossible (see profiling).
    for pattern, fmt in [(r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"), (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
                         (r"^\d{1,2} [A-Za-z]{3} \d{2}$", "%d %b %y")]:
        if re.match(pattern, text.strip()):
            return pd.to_datetime(text.strip(), format=fmt)
    return pd.NaT


TEST_ALIASES = {
    "a1c": "hba1c", "hba1c": "hba1c", "glycated hb": "hba1c",
    "fbs": "fasting_glucose", "glucose (f)": "fasting_glucose", "fasting glucose": "fasting_glucose",
    "ppbs": "pp_glucose", "glucose (pp)": "pp_glucose", "post prandial glucose": "pp_glucose",
}


def normalise_labs(labs):
    """Glycaemic tests only, in one name and one unit each: HbA1c in %, glucose in mg/dL."""
    labs["test"] = labs["test_name"].str.strip().str.lower().map(TEST_ALIASES)
    labs = labs[labs["test"].notna()].copy()
    std = []
    for _, r in labs.iterrows():
        v, unit = float(r["value"]), r["unit"].strip().lower()
        if r["test"] == "hba1c":
            if unit == "" :
                unit = "mmol/mol" if v > 20 else "%"
                log_fix("lab_results.csv", r["csv_line"], "unit", "", unit,
                        f"HbA1c {v} with no unit; >20 is impossible as %, so mmol/mol")
            std.append(round(0.09148 * v + 2.152, 1) if unit == "mmol/mol" else v)  # IFCC -> NGSP
        else:
            std.append(round(v * 18.0) if unit == "mmol/l" else v)
    labs["std_value"] = std
    return labs


def drug_class(drug):
    d = drug.lower()
    classes = {cls for name, cls in GLUCOSE_LOWERING.items() if name in d}
    if "insulin" in classes:
        return "insulin"
    if "other" in classes:
        return "other"  # includes glimepiride + metformin combinations
    return "metformin" if classes else ""


# =============================================================================
# Read each visit note
# =============================================================================
def clauses(note):
    return [c.strip() for c in re.split(r"[.;,]", note) if c.strip()]


def read_note(note, department):
    """Facts about diabetes in one visit note, matched clause by clause."""
    facts = {"diabetes": [], "negated": [], "prediabetes": False, "gestational": False, "type_1": False}
    for clause in clauses(note):
        c = clause.lower()
        if PREDIABETES.search(c):
            facts["prediabetes"] = True
        elif GESTATIONAL.search(c):
            facts["gestational"] = True
        elif DIABETES.search(c):
            if NEGATED_OR_FAMILY.search(c):
                facts["negated"].append(clause)
            else:
                facts["diabetes"].append(clause)
        if TYPE_1.search(c):
            facts["type_1"] = True
    low = note.lower()
    facts["pregnancy"] = department == "OBG" or bool(PREGNANCY.search(low))
    facts["glycaemic"] = bool(GLYCAEMIC.search(low))
    facts["deceased"] = bool(DECEASED.search(low))
    facts["transferred"] = bool(TRANSFERRED.search(low))
    facts["pcos"] = bool(PCOS.search(low))
    return facts


def stated_interval(note):
    """The follow-up interval the doctor wrote, e.g. 'review 3 months', 'r/v 6/12'."""
    low = note.lower()
    if re.search(r"review\s+yearly", low):
        return pd.DateOffset(years=1), "review yearly"
    if re.search(r"review\s+tomorrow", low):
        return pd.DateOffset(days=1), "review tomorrow"
    for regex in (REVIEW_IN, REPEAT_IN):
        m = regex.search(low)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            if unit == "/12" or unit.startswith(("month", "mth")):
                return pd.DateOffset(months=n), m.group(0)
            if unit == "/52" or unit.startswith("w"):
                return pd.DateOffset(weeks=n), m.group(0)
            if unit == "/7" or unit.startswith("day"):
                return pd.DateOffset(days=n), m.group(0)
            return pd.DateOffset(years=n), m.group(0)
    return None, None


def annotate_visits(visits, rx):
    facts = [read_note(n, d) for n, d in zip(visits["notes"], visits["department"])]
    for key in facts[0]:
        visits[key] = [f[key] for f in facts]
    gl = rx[rx["drug_class"] != ""].groupby("visit_id")["drug_class"].agg(set)
    visits["gl_drugs"] = visits["visit_id"].map(gl).apply(lambda s: s if isinstance(s, set) else set())
    # A diabetes review: a diabetes or sugar discussion in a clinic that manages diabetes,
    # or glucose-lowering medicine prescribed. Pregnancy visits never count.
    visits["is_review"] = ~visits["pregnancy"] & (
        (visits["department"].isin(REVIEW_DEPARTMENTS) & (visits["diabetes"].map(bool) | visits["glycaemic"]))
        | visits["gl_drugs"].map(bool)
    )
    return visits


# =============================================================================
# Decide each patient's status
# =============================================================================
def latest_lab(labs, test):
    rows = labs[labs["test"] == test].sort_values("collected_on")
    return None if rows.empty else rows.iloc[-1]


def diabetes_evidence(v, labs):
    """Evidence that this patient has diabetes, excluding pregnancy-only evidence."""
    outside_pregnancy = v[~v["pregnancy"]]
    noted = outside_pregnancy[outside_pregnancy["diabetes"].map(bool)]
    drugs = set().union(*outside_pregnancy["gl_drugs"]) if len(outside_pregnancy) else set()
    strong_drug = bool(drugs & {"insulin", "other"})
    parts = []
    if len(noted):
        first = noted.iloc[0]
        parts.append(f"doctor's notes say \"{first['diabetes'][0]}\" ({first['department']}, "
                     f"{first['visit_date'].date()}; {len(noted)} visits mention diabetes)")
    if drugs:
        parts.append("on " + ", ".join(sorted("insulin" if d == "insulin" else
                                              "metformin" if d == "metformin" else "other diabetes tablets"
                                              for d in drugs)))
    a1c = latest_lab(labs, "hba1c")
    if a1c is not None:
        parts.append(f"latest HbA1c {a1c['std_value']}% ({a1c['collected_on'].date()})")
    is_diabetic = len(noted) > 0 or strong_drug
    return is_diabetic, "; ".join(parts)


def follow_up(v, lab, as_of, export_end):
    """Due date from the last diabetes review visit, and whether it's overdue."""
    reviews = v[v["is_review"]].sort_values("visit_date")
    basis_note = ""
    if reviews.empty:
        reviews = v[v["diabetes"].map(bool) & ~v["pregnancy"]].sort_values("visit_date")
        basis_note = " (no diabetes review visit found; last visit mentioning diabetes used)"
    last = reviews.iloc[-1]
    offset, phrase = stated_interval(last["notes"])
    note_due = last["visit_date"] + offset if offset is not None else None
    if pd.notna(last["next_appointment"]):
        # A booked date wins over the interval in the note: the patient holds that booking.
        # When they disagree by over a month, say so rather than choosing silently.
        due, basis = last["next_appointment"], "next appointment date set by doctor"
        if note_due is not None and abs((due - note_due).days) > 30:
            basis += f"; note said \"{phrase}\" (due {note_due.date()}), booked date used"
    elif note_due is not None:
        due, basis = note_due, f"doctor wrote \"{phrase}\""
    else:
        due = last["visit_date"] + pd.DateOffset(months=DEFAULT_INTERVAL_MONTHS)
        basis = f"no date in note; default {DEFAULT_INTERVAL_MONTHS} months"
    days_overdue = (as_of - due).days
    overdue = days_overdue > GRACE_DAYS
    # Borderline: overdue now, but not under one of the alternatives check_assumptions.py tries.
    # Such a call is the likeliest to be unnecessary, so the caller checks the appointment book.
    fragile = []
    if overdue:
        if (export_end - due).days <= GRACE_DAYS:
            fragile.append(f"only became overdue after the export ends ({export_end.date()})")
        if basis.startswith("no date in note"):
            alt_due = last["visit_date"] + pd.DateOffset(months=ALT_DEFAULT_MONTHS)
            if (as_of - alt_due).days <= GRACE_DAYS:
                fragile.append(f"due date is our {DEFAULT_INTERVAL_MONTHS}-month estimate, not the doctor's")
        if days_overdue <= ALT_GRACE_DAYS:
            fragile.append(f"less than {ALT_GRACE_DAYS} days overdue")
    later = v[v["visit_date"] > last["visit_date"]]
    other = "; ".join(f"seen in {r.department} on {r.visit_date.date()} (not a diabetes review)"
                      for r in later.itertuples())
    # Sugar tests done after the last review: the patient came in, but no doctor has
    # seen the results. Still overdue, but the caller needs to know.
    tested = lab[lab["collected_on"] > last["visit_date"]].sort_values("collected_on")
    caller_flags = ""
    if len(tested):
        t = tested.iloc[-1]
        caller_flags = (f"had sugar tests on {t['collected_on'].date()} but no doctor review since: "
                      f"book a review to go over results")
    if fragile:
        caller_flags = "; ".join(filter(None, [caller_flags, (
            f"borderline ({', '.join(fragile)}): check the appointment book first")]))
    return {
        "last_diabetes_visit": last["visit_date"].date(), "last_doctor": last["doctor"],
        "last_visit_note": last["notes"], "due_date": due.date(), "due_basis": basis + basis_note,
        "days_overdue": int(days_overdue), "overdue": overdue, "later_visits": other,
        "caller_flags": caller_flags,
    }


def classify(patients, visits, labs, as_of, export_end):
    phone_owners = patients[patients["phone"] != ""].groupby("phone")["mrn"].agg(list)
    same_person = patients[(patients["phone"] != "") & patients.duplicated(["dob", "phone"], keep=False)]
    pair_of = {}
    for _, grp in same_person.groupby(["dob", "phone"]):
        for m in grp["mrn"]:
            pair_of[m] = list(grp["mrn"])

    evidence_of = {m: diabetes_evidence(visits[visits["mrn"] == m], labs[labs["mrn"] == m])
                   for m in patients["mrn"]}

    rows = []
    for p in patients.itertuples():
        v = visits[visits["mrn"] == p.mrn].sort_values("visit_date")
        lab = labs[labs["mrn"] == p.mrn]
        age = (as_of - p.dob).days // 365
        mrns = sorted(pair_of.get(p.mrn, [p.mrn]))
        others = [m for m in mrns if m != p.mrn]
        # Worded the same for every record of the person, so review lists can show them once.
        same_as = (f"Registered twice: {' and '.join(mrns)} (same date of birth and phone); "
                   f"merge the records. " if others else "")
        row = {"mrn": p.mrn, "name": p.name, "dob": p.dob.date(), "age": age, "phone": p.phone,
               "status": "", "reason": "", "action_by": "", "person_key": "|".join(mrns),
               "diabetes_evidence": "", "caller_note": ""}
        # If any record of this person is diabetic, all of them are treated as diabetic.
        diabetic = any(evidence_of[m][0] for m in mrns)
        row["diabetes_evidence"] = evidence_of[p.mrn][1]

        died = v[v["deceased"]]
        moved = v[v["transferred"]]
        a1c, fpg = latest_lab(lab, "hba1c"), latest_lab(lab, "fasting_glucose")
        lab_high = (a1c is not None and a1c["std_value"] >= HBA1C_DIABETIC) or (
            fpg is not None and fpg["std_value"] >= FPG_DIABETIC)
        ever_high = ((lab["test"] == "hba1c") & (lab["std_value"] >= HBA1C_DIABETIC)).any()

        def done(status, reason, action_by=""):
            row["status"], row["reason"], row["action_by"] = status, reason, action_by
            rows.append(row)

        if len(died):
            done("EXCLUDED", f"deceased: \"{died.iloc[-1]['notes']}\" ({died.iloc[-1]['visit_date'].date()})")
            continue
        if len(moved):
            when = moved.iloc[-1]["visit_date"]
            if (v["visit_date"] > when).any():
                done("REVIEW", f"care transferred on {when.date()} but visited again later; check if back",
                     "records team")
            else:
                done("EXCLUDED", f"care transferred to another hospital: \"{moved.iloc[-1]['notes']}\" ({when.date()})")
            continue

        if not diabetic:
            if lab_high:
                history = ("Had gestational diabetes. " if v["gestational"].any() else
                           "Previously recorded as borderline/prediabetes. " if v["prediabetes"].any() else "")
                # Every diabetic-range result across all of this person's records, so the doctor
                # can see whether there is the second result a diagnosis needs (ADA Rec 2.1b).
                person_labs = labs[labs["mrn"].isin(mrns)]
                high = person_labs[
                    ((person_labs["test"] == "hba1c") & (person_labs["std_value"] >= HBA1C_DIABETIC))
                    | ((person_labs["test"] == "fasting_glucose") & (person_labs["std_value"] >= FPG_DIABETIC))
                ].sort_values("collected_on")
                results = ", ".join(
                    f"{'HbA1c' if r.test == 'hba1c' else 'fasting glucose'} {r.std_value:g}"
                    f"{'%' if r.test == 'hba1c' else ' mg/dL'} ({r.collected_on.date()})" for r in high.itertuples())
                count = (f"{len(high)} diabetic-range results" if len(high) > 1
                         else "1 diabetic-range result, not yet repeated")
                done("REVIEW", f"{same_as}No diabetes diagnosis recorded, but {count}: {results}. {history}"
                               f"Doctor to decide; not for the front desk", "doctor")
            elif ever_high:
                done("EXCLUDED", f"one HbA1c in diabetic range, not confirmed on repeat (latest {a1c['std_value']}%)")
            elif v["gestational"].any():
                done("EXCLUDED", "gestational diabetes only (in pregnancy), no diabetes since")
            elif v["prediabetes"].any():
                done("EXCLUDED", "prediabetes / borderline sugars, not diabetes")
            elif v["pcos"].any() and v["gl_drugs"].map(lambda s: "metformin" in s).any():
                done("EXCLUDED", "on metformin for PCOS, not diabetes")
            elif v["negated"].map(bool).any():
                said = v[v["negated"].map(bool)].iloc[0]["negated"][0]
                done("EXCLUDED", f"notes mention diabetes only as absent or family history: \"{said}\"")
            else:
                done("NOT_DIABETIC", "no diabetes in notes, prescriptions or labs")
            continue

        # Diabetic. Work out follow-up across every record that may be this person.
        fu = follow_up(visits[visits["mrn"].isin(mrns)], labs[labs["mrn"].isin(mrns)], as_of, export_end)
        row.update(fu)
        notes = [fu["caller_flags"]] if fu["caller_flags"] else []
        if v["type_1"].any():
            notes.append("Type 1 diabetes")
        if age < ADULT_AGE:
            notes.append(f"child aged {age}: speak to parent/guardian")
        sharers = [m for m in phone_owners.get(p.phone, []) if m != p.mrn and m not in mrns]
        if sharers:
            names = patients.set_index("mrn").loc[sharers, "name"].tolist()
            notes.append(f"phone shared with {', '.join(names)}: ask for {p.name} by name")
        if (patients["name"] == p.name).sum() > 1:
            notes.append("another patient has the same name: confirm date of birth")
        row["caller_note"] = "; ".join(notes)

        if others:
            done("REVIEW", f"{same_as}Then call if needed. Combined records: last diabetes visit "
                           f"{fu['last_diabetes_visit']}, due {fu['due_date']}, "
                           f"{'OVERDUE ' + str(fu['days_overdue']) + ' days' if fu['overdue'] else 'not overdue'}",
                 "records team")
        elif not fu["overdue"]:
            done("NOT_DUE", f"follow-up due {fu['due_date']} ({fu['due_basis']})")
        elif p.phone == "":
            done("REVIEW", f"overdue {fu['days_overdue']} days but no phone number on record", "records team")
        elif p.dob > p.registered_on:
            done("REVIEW", f"overdue {fu['days_overdue']} days but date of birth on record ({p.dob.date()}) is after "
                           f"registration ({p.registered_on.date()}); fix before calling so identity can be checked",
                 "records team")
        else:
            done("CALL", f"overdue {fu['days_overdue']} days: follow-up was due {fu['due_date']} "
                         f"({fu['due_basis']})")
    return pd.DataFrame(rows)


# =============================================================================
# Output
# =============================================================================
CALL_COLUMNS = ["name", "mrn", "dob", "age", "phone", "caller_note", "days_overdue", "due_date", "due_basis",
                "last_diabetes_visit", "last_doctor", "later_visits", "diabetes_evidence", "outcome"]
REVIEW_COLUMNS = ["name", "mrn", "phone", "reason", "diabetes_evidence"]

# Choices for the Outcome dropdown on the printed call list. Provisional until the hospital
# says how it records calls (question 5 of the email).
OUTCOMES = [
    "Booked follow-up appointment",
    "Already has an appointment",
    "No answer: try again",
    "Asked to call back later",
    "Declined follow-up",
    "Wrong / not-working number (tell records team)",
    "Treated elsewhere or moved away (tell records team)",
    "Patient has died (tell records team)",
    "Other (tell records team)",
]


def per_person(review):
    """One row per person: a double-registered person's records collapse into a single row.
    (all_patients.csv keeps one row per MRN.)"""
    return (review.groupby("person_key", sort=False)
            .agg(name=("name", " / ".join), mrn=("mrn", " / ".join),
                 phone=("phone", lambda s: " / ".join(sorted(set(s) - {""}))),
                 reason=("reason", "first"), action_by=("action_by", "first"),
                 diabetes_evidence=("diabetes_evidence", " | ".join))
            .reset_index(drop=True))


def write_outputs(result, as_of, export_end):
    OUT.mkdir(exist_ok=True)
    call = result[result["status"] == "CALL"].sort_values("days_overdue", ascending=False)
    call = call.astype({"days_overdue": int})  # only diabetic rows have it, so it was read as float
    call["outcome"] = ""  # for the caller to fill in: booked, wrong number, moved, died...
    review = per_person(result[result["status"] == "REVIEW"].sort_values("mrn"))
    for_doctor = review[review["action_by"] == "doctor"]
    for_records = review[review["action_by"] == "records team"]
    excluded = result[result["status"] == "EXCLUDED"].sort_values("mrn")

    call[CALL_COLUMNS].to_csv(OUT / "call_list.csv", index=False)
    for_doctor[REVIEW_COLUMNS].to_csv(OUT / "review_for_doctor.csv", index=False)
    for_records[REVIEW_COLUMNS].to_csv(OUT / "review_for_records_team.csv", index=False)
    excluded[["name", "mrn", "reason"]].to_csv(OUT / "exclusions.csv", index=False)
    result[["mrn", "name", "status", "reason"]].to_csv(OUT / "all_patients.csv", index=False)
    pd.DataFrame(fixes, columns=["file", "csv_line", "field", "old", "new", "reason"]).to_csv(
        OUT / "data_fixes.csv", index=False)

    counts = result["status"].value_counts()
    summary = [
        f"As of {as_of.date()}. The export's latest visit is {export_end.date()}; anything after that is not seen.",
        f"Overdue = no diabetes review visit for more than {GRACE_DAYS} days past the due date.",
        "",
        *[f"{s:13s} {counts.get(s, 0):4d}" for s in ["CALL", "NOT_DUE", "REVIEW", "EXCLUDED", "NOT_DIABETIC"]],
        f"{'TOTAL':13s} {len(result):4d}  (patients.csv has {len(result)} rows)",
        "",
        f"REVIEW, per person: {len(for_doctor)} for a doctor, {len(for_records)} for the records team",
        f"Borderline calls (check the appointment book first): {int(call['caller_note'].str.contains('borderline').sum())}",
        f"Data fixes applied: {len(fixes)} (see data_fixes.csv)",
    ]
    (OUT / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    write_html(call, for_doctor, for_records, as_of, export_end)
    print("\n".join(summary))
    print(f"\nWritten to {OUT}/")


def table(df, cols, headers, cells=None):
    """cells maps a column to a function that renders that cell's HTML itself."""
    cells = cells or {}
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cells[c](r) if c in cells else html.escape(str(r[c]))}</td>"
                                    for c in cols) + "</tr>"
                   for _, r in df.iterrows())
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def outcome_select(r):
    options = '<option value=""></option>' + "".join(f"<option>{html.escape(o)}</option>" for o in OUTCOMES)
    attrs = " ".join(f'data-{k}="{html.escape(str(r[k]), quote=True)}"' for k in ("mrn", "name", "phone"))
    return f'<select class="outcome" {attrs}>{options}</select>'


# Keeps dropdown choices in this browser (per list date) and exports them as a CSV for the
# records team. Without this, choices would be lost when the page is closed.
OUTCOME_SCRIPT = """<script>
const KEY = "diabetes-call-outcomes-" + AS_OF;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
document.querySelectorAll("select.outcome").forEach(s => {
  if (saved[s.dataset.mrn]) s.value = saved[s.dataset.mrn];
  s.addEventListener("change", () => {
    saved[s.dataset.mrn] = s.value;
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
  });
});
document.getElementById("export-outcomes").addEventListener("click", () => {
  const q = v => '"' + String(v).replace(/"/g, '""') + '"';
  const rows = [["mrn", "name", "phone", "outcome"].map(q).join(",")];
  document.querySelectorAll("select.outcome").forEach(s =>
    rows.push([s.dataset.mrn, s.dataset.name, s.dataset.phone, s.value].map(q).join(",")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([rows.join("\\r\\n")], {type: "text/csv"}));
  a.download = "call_outcomes_" + AS_OF + ".csv";
  a.click();
});
</script>"""


def write_html(call, for_doctor, for_records, as_of, export_end):
    page = f"""<!doctype html><meta charset="utf-8"><title>Diabetes follow-up call list</title>
<style>
body{{font-family:Arial,sans-serif;font-size:13px;margin:24px;color:#111}}
table{{border-collapse:collapse;width:100%;margin-bottom:28px}}
th,td{{border:1px solid #999;padding:4px 6px;text-align:left;vertical-align:top}}
th{{background:#eee}} .note{{background:#fff8dc;padding:8px;border:1px solid #e0c060}}
th:last-child{{min-width:140px}} select.outcome{{width:100%;max-width:220px}}
@page{{size:landscape}}
@media print{{body{{margin:8mm}} h2{{page-break-before:always}} h2:first-of-type{{page-break-before:auto}}
tr{{page-break-inside:avoid}} thead{{display:table-header-group}} .no-print{{display:none}}
select.outcome{{appearance:none;-webkit-appearance:none;border:none;background:none;font:inherit;color:inherit}}}}
</style>
<h1>Diabetes follow-up call list</h1>
<p>As of <b>{as_of.date()}</b>. Built from the export up to {export_end.date()}; visits after that are not included.</p>
<p class="note">Before calling: confirm name and date of birth. If the patient already has a booking, or has died
or moved, record it in Outcome and tell the records team. Do not discuss test results on the phone.</p>
<p class="no-print">Choose an Outcome after each call. Choices are kept in this browser on this computer only.
When done, press <button id="export-outcomes" type="button">Export outcomes (CSV)</button> and send the file to the
records team. On paper, a blank Outcome is space to write in.</p>
<h2>Call ({len(call)}): most overdue first</h2>
{table(call, ["name", "mrn", "dob", "age", "phone", "caller_note", "days_overdue", "due_date",
              "last_diabetes_visit", "last_doctor", "due_basis", "later_visits", "outcome"],
       ["Name", "MRN", "Date of birth", "Age", "Phone", "Note for caller", "Days overdue", "Was due",
        "Last diabetes visit", "Doctor", "Why this due date", "Other visits since", "Outcome"],
       cells={"outcome": outcome_select})}
<h2>For a doctor to check ({len(for_doctor)}): not for the front desk to call</h2>
{table(for_doctor, ["name", "mrn", "phone", "reason"], ["Name", "MRN", "Phone", "What needs checking"])}
<h2>For the records team to fix before anyone calls ({len(for_records)})</h2>
{table(for_records, ["name", "mrn", "phone", "reason"], ["Name", "MRN", "Phone", "What needs fixing"])}
"""
    page += OUTCOME_SCRIPT.replace("AS_OF", f'"{as_of.date()}"')
    (OUT / "call_list.html").write_text(page, encoding="utf-8")


def main():
    global DEFAULT_INTERVAL_MONTHS, GRACE_DAYS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", default=None,
                        help="date to measure overdue from (YYYY-MM-DD). Default: the export's last visit date, "
                             "so the same export always gives the same list. Pass today's date to measure to today.")
    parser.add_argument("--default-months", type=int, default=DEFAULT_INTERVAL_MONTHS,
                        help="follow-up gap when the doctor wrote no date (default: %(default)s)")
    parser.add_argument("--grace-days", type=int, default=GRACE_DAYS,
                        help="days past due before someone counts as overdue (default: %(default)s)")
    args = parser.parse_args()
    DEFAULT_INTERVAL_MONTHS, GRACE_DAYS = args.default_months, args.grace_days

    patients, visits, labs, rx = load()
    visits = annotate_visits(visits, rx)
    export_end = visits["visit_date"].max()
    as_of = pd.Timestamp(args.as_of) if args.as_of else export_end
    result = classify(patients, visits, labs, as_of, export_end)
    write_outputs(result, as_of, export_end)


if __name__ == "__main__":
    main()
