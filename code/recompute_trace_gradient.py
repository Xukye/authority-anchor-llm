#!/usr/bin/env python3
"""
FRESH recompute of tab:trace-gradient (main.tex ~line 822).

One worked case: Gemini-2.5-flash, CLI.C.574655575.
The table is a per-tier trace for the THINKING arm (it shows thinking traces),
plus a blind (no-anchor) row and a final x2 chief-judge row.

We recompute, per row, the printed numeric cells:
  - Anchor (2,237 on x0.5 ; 8,949 on x2)
  - Output (parsed_amount of the thinking record for that tier/arm)
  - Pull   = clip((parsed - blind)/(anchor - blind), 0, 1),
             blind = think-blind parsed_amount (median over reps).

Data: raw_data/main_axis_30/Gemini_T_0.json (think arm) and Gemini_N_0.json
      (only to confirm blind structure; the table is the think arm).
Cross-check pull against tables/per_case_pull.csv (authoritative, corrections baked in).

Tier map (CONTEXT):
  GN  = S1 Fortune teller
  G1  = S2 Layperson
  E1  = S3 Law student
  GL5 = S4a Lawyer  (expert sub-role)
  G4  = S4b Professor (expert sub-role)
  G5  = S5 Chief judge

NOTE: the table labels its third trace row "Law student (S3)" with output 3,572.
In the data, 3,572 is the G1 (Layperson / S2) record; the E1 (true S3 law
student) record parses to 2,237. This is recorded as a potential label mismatch.
"""
import json, csv, os, statistics

DB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(DB, "raw_data", "main_axis_30")
TABLES = os.path.join(DB, "tables")
CASE = "CLI.C.574655575"

def load(fn):
    return [r for r in json.load(open(os.path.join(RAW, fn))) if r.get("cli") == CASE]

think = load("Gemini_T_0.json")
non   = load("Gemini_N_0.json")

def get(records, framing, mult):
    for r in records:
        if r.get("framing") == framing and r.get("multiplier") == mult:
            return r
    return None

def blind_parsed(records):
    vals = [r["parsed_amount"] for r in records
            if str(r.get("condition", "")).startswith("blind")]
    return statistics.median(vals) if vals else None

blind_think = blind_parsed(think)   # 5322
blind_non   = blind_parsed(non)

def pull(parsed, anchor, blind):
    if anchor is None or blind is None or anchor == blind:
        return None
    p = (parsed - blind) / (anchor - blind)
    return max(0.0, min(1.0, p))

# Rows of the table, in printed order. (label, framing, mult)
ROWS = [
    ("No anchor (blind)", None,  None),
    ("Fortune teller S1", "GN",  0.5),
    ("Law student S3*",   "E1",  0.5),   # printed label; 3,572 actually = G1
    ("Lawyer S4a",        "GL5", 0.5),
    ("Professor S4b",     "G4",  0.5),
    ("Chief judge S5 x0.5","G5", 0.5),
    ("Chief judge S5 x2", "G5",  2.0),
]

out_rows = []
print(f"think blind (median) = {blind_think}")
print(f"non   blind (median) = {blind_non}")
print()
for label, fr, mult in ROWS:
    if fr is None:
        rec = next((r for r in think if str(r.get("condition","")).startswith("blind")), None)
        anchor = None
        parsed = rec["parsed_amount"] if rec else None
        pl = None
    else:
        rec = get(think, fr, mult)
        anchor = rec["anchor"] if rec else None
        parsed = rec["parsed_amount"] if rec else None
        pl = pull(parsed, anchor, blind_think)
    out_rows.append({
        "row": label, "framing": fr, "mult": mult,
        "anchor": anchor, "output": parsed,
        "pull": None if pl is None else round(pl, 4),
    })
    print(f"{label:22} fr={str(fr):4} mult={str(mult):4} anchor={str(anchor):6} "
          f"output={str(parsed):8} pull={'---' if pl is None else round(pl,2)}")

# Also report the data value that the printed "Law student" row (3,572) really is:
g1 = get(think, "G1", 0.5)
print()
print(f"[note] G1 (Layperson/S2) x0.5 think parsed = {g1['parsed_amount']}, "
      f"pull = {round(pull(g1['parsed_amount'], g1['anchor'], blind_think),4)}")
e1 = get(think, "E1", 0.5)
print(f"[note] E1 (Law student/S3) x0.5 think parsed = {e1['parsed_amount']}, "
      f"pull = {round(pull(e1['parsed_amount'], e1['anchor'], blind_think),4)}")

# Cross-check pulls against per_case_pull.csv (x05 arm, think mode)
print("\n[cross-check per_case_pull.csv, Gemini x05 think]")
pcp = {}
with open(os.path.join(TABLES, "per_case_pull.csv")) as f:
    for r in csv.DictReader(f):
        if r["cli"] == CASE and r["model"].lower().startswith("gemini") \
           and r["arm"] == "x05" and r["mode"] == "think":
            pcp[r["tier"]] = float(r["clipped_pull"])
for t, v in pcp.items():
    print(f"  {t:12} clipped_pull = {round(v,4)}")

# Write CSV
os.makedirs(TABLES, exist_ok=True)
csv_path = os.path.join(TABLES, "trace_gradient.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["row", "framing", "mult", "anchor", "output", "pull"])
    w.writeheader()
    for r in out_rows:
        w.writerow(r)
print(f"\nWROTE {csv_path}")
