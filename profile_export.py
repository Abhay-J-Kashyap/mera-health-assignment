"""Profile the raw hospital export. Read-only: reports problems, changes nothing.

Run:  python profile_export.py
Writes the report to profiling/profile_report.txt and prints it.
"""
import re
from pathlib import Path

import pandas as pd

EXPORT = Path("export")
OUT = Path("profiling") / "profile_report.txt"

lines = []


def say(*parts):
    lines.append(" ".join(str(p) for p in parts))


def section(title):
    say("")
    say("=" * 78)
    say(title)
    say("=" * 78)


def show(df, cols=None, max_rows=60):
    if df.empty:
        say("  (none)")
        return
    text = df[cols].to_string(index=False) if cols else df.to_string(index=False)
    for row in text.splitlines()[: max_rows + 1]:
        say("  " + row)
    if len(df) > max_rows:
        say(f"  ... {len(df) - max_rows} more")


# Read everything as text so nothing is silently coerced.
patients = pd.read_csv(EXPORT / "patients.csv", dtype=str, keep_default_na=False)
visits = pd.read_csv(EXPORT / "visits.csv", dtype=str, keep_default_na=False)
labs = pd.read_csv(EXPORT / "lab_results.csv", dtype=str, keep_default_na=False)
rx = pd.read_csv(EXPORT / "prescriptions.csv", dtype=str, keep_default_na=False)

known_mrns = set(patients["mrn"])

# ---------------------------------------------------------------------------
section("1. SHAPE")
for name, df in [("patients", patients), ("visits", visits), ("lab_results", labs), ("prescriptions", rx)]:
    blanks = {c: int((df[c].str.strip() == "").sum()) for c in df.columns}
    blanks = {c: n for c, n in blanks.items() if n}
    say(f"{name:14s} rows={len(df):4d}  exact-duplicate rows={int(df.duplicated().sum())}  blanks={blanks}")

# ---------------------------------------------------------------------------
section("2. PATIENTS")
say("Duplicate MRNs:", int(patients["mrn"].duplicated().sum()))

dob = pd.to_datetime(patients["dob"], format="%Y-%m-%d", errors="coerce")
reg = pd.to_datetime(patients["registered_on"], format="%Y-%m-%d", errors="coerce")
say("Unparseable dob:", int(dob.isna().sum()), " unparseable registered_on:", int(reg.isna().sum()))
say("Born after registration:")
show(patients[dob > reg])

say("Missing phone:")
show(patients[patients["phone"].str.strip() == ""])

say("Phone numbers shared by more than one MRN:")
has_phone = patients[patients["phone"].str.strip() != ""]
shared = has_phone[has_phone.duplicated("phone", keep=False)].sort_values(["phone", "mrn"])
show(shared)

say("Same DOB + same phone (suspected same person, different MRN):")
same_person = has_phone[has_phone.duplicated(["dob", "phone"], keep=False)].sort_values(["phone", "mrn"])
show(same_person)

say("Same name, different MRN (must NOT be merged on name alone):")
show(patients[patients.duplicated("name", keep=False)].sort_values(["name", "mrn"]))

# ---------------------------------------------------------------------------
section("3. VISITS")
vdate = pd.to_datetime(visits["visit_date"], format="%Y-%m-%d", errors="coerce")
nappt_raw = visits["next_appointment"].str.strip()
nappt = pd.to_datetime(nappt_raw.where(nappt_raw != ""), format="%Y-%m-%d", errors="coerce")
say("Duplicate visit_id:", int(visits["visit_id"].duplicated().sum()))
say("Unparseable visit_date:", int(vdate.isna().sum()))
show(visits[vdate.isna()], ["visit_id", "mrn", "visit_date"])
say(f"visit_date range: {vdate.min().date()} .. {vdate.max().date()}")
say(f"next_appointment filled: {int((nappt_raw != '').sum())} of {len(visits)}; unparseable: {int(((nappt_raw != '') & nappt.isna()).sum())}")
say("next_appointment on or before its own visit_date:")
show(visits[nappt <= vdate], ["visit_id", "mrn", "visit_date", "next_appointment"])
say("Visits whose MRN is not in patients.csv:")
show(visits[~visits["mrn"].isin(known_mrns)], ["visit_id", "mrn", "visit_date", "department"])
say("Same MRN, same date, more than one visit:")
show(visits[visits.duplicated(["mrn", "visit_date"], keep=False)], ["visit_id", "mrn", "visit_date", "department", "notes"])
say("Departments:")
for dept, n in visits["department"].value_counts().items():
    say(f"  {n:4d}  {dept!r}")
say("Doctors (department):")
for (doc, dept), n in visits.groupby(["doctor", "department"]).size().items():
    say(f"  {n:4d}  {doc!r} ({dept})")

# ---------------------------------------------------------------------------
section("4. WHAT THE NOTES SAY ABOUT DIABETES")
notes = visits["notes"].str.lower()

# Every distinct phrase that looks diabetes-related, so the classifier can be
# built from what is actually written rather than what we expect.
DIAB_TOKEN = re.compile(r"\b(t1dm|t2dm|dm2|dm|niddm|iddm|ohas?|dka|gdm|igt|ifg|\w*diabet\w*)\b")
token_counts = notes.str.findall(DIAB_TOKEN).explode().dropna().value_counts()
say("Diabetes-like tokens in notes (token: count):")
for tok, n in token_counts.items():
    say(f"  {n:4d}  {tok}")

CATEGORIES = {
    "gestational": r"\bgdm\b|gestational",
    "prediabetes / igt / borderline": r"pre-?diabet|\bigt\b|\bifg\b|borderline",
    "type 1 / juvenile": r"\bt1dm\b|type 1|juvenile",
    "deceased": r"expired|deceased|\bdied\b|death|could not be revived",
    "transferred / relocated": r"transfer|relocat|shifted to (?!icu)|another hospital|native place",
}
for label, pattern in CATEGORIES.items():
    hit = visits[notes.str.contains(pattern, regex=True)]
    say(f"Notes matching [{label}]: {len(hit)} visits, {hit['mrn'].nunique()} patients")
    show(hit, ["visit_id", "mrn", "visit_date", "department", "notes"])

# ---------------------------------------------------------------------------
section("5. HOW FOLLOW-UP INTENT IS WRITTEN")
# Rough net for "review in N units" phrasing; the real parser comes later.
INTERVAL = re.compile(
    r"(review|r/v|rpt|repeat|f/u)\D{0,12}(\d+)\s*(/12|/52|/7|months?|mths?|wks?|weeks?|days?|yrs?|years?)"
    r"|review (yearly|tomorrow|sos)"
)
diab_visit = notes.str.contains(r"\b(?:t1dm|t2dm|dm2|dm|niddm)\b|diabet", regex=True) & ~notes.str.contains(
    CATEGORIES["gestational"] + "|" + CATEGORIES["prediabetes / igt / borderline"], regex=True
)
has_interval = notes.map(lambda n: bool(INTERVAL.search(n)))
has_nappt = nappt_raw != ""
dv = pd.DataFrame({"interval": has_interval[diab_visit], "next_appt": has_nappt[diab_visit]})
say(f"Diabetes-mention visits: {int(diab_visit.sum())}")
say(pd.crosstab(dv["interval"], dv["next_appt"]).to_string())
say("Interval phrases found (all visits):")
phrases = visits["notes"].str.lower().str.extract(INTERVAL)
joined = (phrases[0].fillna("") + " " + phrases[1].fillna("") + " " + phrases[2].fillna("") + phrases[3].fillna("")).str.strip()
for p, n in joined[joined != ""].value_counts().head(40).items():
    say(f"  {n:4d}  {p}")
say("Diabetes-mention visits with neither an interval phrase nor next_appointment (sample):")
show(visits[diab_visit & ~has_interval & ~has_nappt], ["visit_id", "mrn", "visit_date", "notes"], max_rows=25)

# Is next_appointment a booking the patient keeps? For dates that fell due by the end of the
# export, count those followed by a visit by the same patient within 14 days of the date. A match
# must come after the visit that set the date: SVH029235 had a second visit on the same day,
# which an earlier version of this check counted. (Raw dates; the one year typo in visits.csv
# belongs to a patient with no next_appointment, so fixing it changes nothing here.)
export_end = vdate.max()
due_by_end = visits[nappt.notna() & (nappt <= export_end)]
by_mrn = pd.DataFrame({"mrn": visits["mrn"], "d": vdate}).groupby("mrn")


def visits_near(row):
    """Days from the appointment date to each later visit by the patient within 14 days."""
    d = by_mrn.get_group(row["mrn"])["d"]
    days = (d[d > vdate[row.name]] - nappt[row.name]).dt.days
    return days[days.abs() <= 14]


near = [visits_near(row) for _, row in due_by_end.iterrows()]
n = len(due_by_end)
within = sum(len(x) > 0 for x in near)
on_or_after = sum((x >= 0).any() for x in near)
nearest_after = sum(len(x) > 0 and x.iloc[x.abs().argmin()] >= 0 for x in near)
say(f"next_appointment dates due by the export end ({export_end.date()}): {n}")
say(f"  followed by a visit within 14 days of the date: {within} of {n}; "
    f"with a visit on or after the date: {on_or_after} (nearest visit on or after: {nearest_after})")

# ---------------------------------------------------------------------------
section("6. LAB RESULTS")
say("Lab rows whose MRN is not in patients.csv:")
show(labs[~labs["mrn"].isin(known_mrns)])

say("Test name / unit / reference range combinations:")
for (t, u, r), n in labs.groupby(["test_name", "unit", "reference_range"]).size().items():
    say(f"  {n:4d}  {t!r:28s} unit={u!r:12s} ref={r!r}")

FORMATS = {
    "YYYY-MM-DD": (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    "DD/MM/YYYY": (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
    "D Mon YY": (r"^\d{1,2} [A-Za-z]{3} \d{2}$", "%d %b %y"),
}
say("Date formats in collected_on:")
fmt_of = pd.Series("UNKNOWN", index=labs.index)
for label, (pat, _) in FORMATS.items():
    fmt_of[labs["collected_on"].str.match(pat)] = label
for label, n in fmt_of.value_counts().items():
    say(f"  {n:4d}  {label}")
show(labs[fmt_of == "UNKNOWN"])

# Is "03/04/2024" 3 April or 4 March? The file is in collection order, so the
# reading that keeps it sorted is the right one.
slash = labs[fmt_of == "DD/MM/YYYY"]["collected_on"]
for label, fmt in [("DD/MM", "%d/%m/%Y"), ("MM/DD", "%m/%d/%Y")]:
    parsed = pd.to_datetime(slash, format=fmt, errors="coerce")
    say(f"  slash dates read as {label}: unparseable={int(parsed.isna().sum())}, "
        f"out-of-order steps={int((parsed.diff().dt.days < 0).sum())}")

collected = pd.Series(pd.NaT, index=labs.index)
for label, (_, fmt) in FORMATS.items():
    mask = fmt_of == label
    collected[mask] = pd.to_datetime(labs.loc[mask, "collected_on"], format=fmt, errors="coerce")
collected = pd.to_datetime(collected)
say(f"collected_on range: {collected.min().date()} .. {collected.max().date()}")
say(f"Lab dates after the last visit date ({vdate.max().date()}):")
show(labs[collected > vdate.max()])

say("Exact duplicate lab rows:")
show(labs[labs.duplicated(keep=False)])

say("Rows with blank unit:")
show(labs[labs["unit"].str.strip() == ""])

# ---------------------------------------------------------------------------
section("7. PRESCRIPTIONS")
say("Prescription rows whose MRN is not in patients.csv:")
show(rx[~rx["mrn"].isin(known_mrns)])
merged = rx.merge(visits[["visit_id", "mrn", "visit_date"]], on="visit_id", how="left", suffixes=("", "_visit"))
say(f"Prescriptions whose visit_id is not in visits.csv: {int(merged['mrn_visit'].isna().sum())} rows, "
    f"{merged.loc[merged['mrn_visit'].isna(), 'visit_id'].nunique()} visit_ids")
show(merged[merged["mrn_visit"].isna()], ["mrn", "visit_id", "drug", "prescribed_on"], max_rows=20)
say("Prescriptions whose MRN differs from the MRN on its visit:")
show(merged[merged["mrn_visit"].notna() & (merged["mrn"] != merged["mrn_visit"])])
say("Prescriptions dated differently from their visit:")
show(merged[merged["mrn_visit"].notna() & (merged["prescribed_on"] != merged["visit_date"])],
     ["mrn", "visit_id", "drug", "prescribed_on", "visit_date"])


def base_drug(name):
    name = re.sub(r"^(tab\.?|t\.|inj\.?|syp|cap\.?)\s+", "", name.strip(), flags=re.I)
    return name.lower()


rx["drug_base"] = rx["drug"].map(base_drug)
say("Distinct drugs after stripping Tab./T./Inj. prefixes (count):")
for d, n in rx["drug_base"].value_counts().items():
    say(f"  {n:4d}  {d}")

# ---------------------------------------------------------------------------
section("8. WHO LOOKS DIABETIC, BY SIGNAL (rough; for finding disagreements only)")
GLUCOSE_LOWERING = r"metformin|glimepiride|gliclazide|sitagliptin|vildagliptin|dapagliflozin|voglibose|insulin|mixtard"
NON_METFORMIN = r"glimepiride|gliclazide|sitagliptin|vildagliptin|dapagliflozin|voglibose|insulin|mixtard"

by_note = set(visits.loc[diab_visit, "mrn"])
by_drug_any = set(rx.loc[rx["drug_base"].str.contains(GLUCOSE_LOWERING), "mrn"])
by_drug_nonmet = set(rx.loc[rx["drug_base"].str.contains(NON_METFORMIN), "mrn"])
metformin_only = by_drug_any - by_drug_nonmet


def hba1c_percent(row):
    """HbA1c as %, converting mmol/mol (IFCC -> NGSP: % = 0.0915 * mmol/mol + 2.15)."""
    try:
        v = float(row["value"])
    except ValueError:
        return None
    unit = row["unit"].strip().lower()
    if unit == "%":
        return v
    if unit == "mmol/mol" or (unit == "" and v > 20):
        return round(0.0915 * v + 2.15, 1)
    return None


is_a1c = labs["test_name"].str.lower().isin(["a1c", "hba1c", "glycated hb"])
a1c = labs[is_a1c].copy()
a1c["pct"] = a1c.apply(hba1c_percent, axis=1)
by_lab = set(a1c.loc[a1c["pct"] >= 6.5, "mrn"])

say(f"note-documented diabetes: {len(by_note)}   any glucose-lowering drug: {len(by_drug_any)}   "
    f"metformin-only: {len(metformin_only)}   any HbA1c >= 6.5%: {len(by_lab)}")
say(f"all three agree: {len(by_note & by_drug_any & by_lab)}")

name_of = patients.set_index("mrn")["name"].to_dict()


def listing(title, mrns):
    say(f"{title}: {len(mrns)}")
    for m in sorted(mrns):
        pt_notes = visits.loc[visits["mrn"] == m, "notes"].tolist()
        pt_drugs = sorted(set(rx.loc[rx["mrn"] == m, "drug_base"]))
        pt_a1c = a1c.loc[a1c["mrn"] == m, "pct"].dropna().tolist()
        say(f"  {m} {name_of.get(m, '?')!r}  a1c%={pt_a1c}  drugs={pt_drugs[:4]}")
        for n in pt_notes[:2]:
            say(f"      note: {n[:110]}")


listing("Lab says diabetic (HbA1c >= 6.5%), no diabetes note", by_lab - by_note)
listing("On a glucose-lowering drug, no diabetes note", by_drug_any - by_note)
listing("Metformin is their only glucose-lowering drug", metformin_only)
listing("Diabetes note but no glucose-lowering drug and no HbA1c >= 6.5%", by_note - by_drug_any - by_lab)

# ---------------------------------------------------------------------------
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nWritten to {OUT}")
