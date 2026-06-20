#!/usr/bin/env python3
"""
FRESH recomputation of tab:power (Endpoint significance at the 2 poles of the crossing).

Poles: S1 = fortune teller (framing GN), S5 = chief judge (framing G5).
Arm: x0.5 only (multiplier == 0.5).
For each (model, pole) compute per-case, on the x0.5 arm:
  - pull = clip((parsed - blind)/(anchor - blind), 0, 1)
      blind = mode-matched MEDIAN no-anchor baseline per (model,cli,mode)
      mode: think if condition ends with _T (after stripping #r\\d+) or thinking==True; else non
  - hug  = 1.0 if |parsed - anchor|/|anchor| <= 0.05 else 0.0
  - per case: average reps -> (cli,framing,mult) ; here pole = single framing, single mult(0.5)
  - Delta(pull) = clipped_pull_think - clipped_pull_non  (paired per case)
  - Delta(hug)  = hug_think - hug_non                    (paired per case)
  - report mean(Delta)*100 (pp) and two-tailed paired-t p over cases.

n=100 poles combine main_axis_30 + supplements; n=30 poles use main only.
  Gemini S1 -> n=100 (main GN + Gemini_S1)
  Gemini S5 -> n=30  (main G5)
  MiMo  S1  -> n=100 (main GN + MiMo_S1)
  MiMo  S5  -> n=100 (main G5 + MiMo_S5)
  GLM   S1  -> n=30  (main GN)
  GLM   S5  -> n=100 (main G5 + GLM_S5)

Source of truth = Database/raw_data (parse_corrections already baked into parsed_amount).
"""
import json, re, csv, os
from statistics import median, mean
from scipy import stats

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(BASE, "raw_data")
MAIN = os.path.join(RAW, "main_axis_30")
SUPP = os.path.join(RAW, "supplements")
OUT = os.path.join(BASE, "tables", "power.csv")

# canonical MAIN-arm temperature files per model (paper Table 8)
MAIN_FILES = {
    "Gemini": ["Gemini_N_0.json", "Gemini_T_0.json"],
    "GLM":    ["GLM_N_0.json", "GLM_T_0.json"],
    "MiMo":   ["MiMo_N_0.json", "MiMo_T_0.json"],
}

POLE_FRAMING = {"S1": "GN", "S5": "G5"}

# (model, pole) -> (n_target_label, list of supplement files to add)
POLE_SPEC = {
    ("Gemini", "S1"): (100, ["Gemini_S1.json"]),
    ("Gemini", "S5"): (30,  []),
    ("MiMo",   "S1"): (100, ["MiMo_S1.json"]),
    ("MiMo",   "S5"): (100, ["MiMo_S5.json"]),
    ("GLM",    "S1"): (30,  []),
    ("GLM",    "S5"): (100, ["GLM_S5.json"]),
}


def mode_of(rec):
    cond = rec.get("condition", "") or ""
    base = re.sub(r"#r\d+$", "", cond)
    if base.endswith("_T"):
        return "think"
    if rec.get("thinking") is True:
        return "think"
    return "non"


def is_blind(rec):
    cond = rec.get("condition", "") or ""
    return cond.startswith("blind")


def load(path):
    with open(path) as f:
        return json.load(f)


def gather_records(model, pole):
    """Return list of raw records for this model from main canonical files + needed supplements."""
    recs = []
    for fn in MAIN_FILES[model]:
        recs += load(os.path.join(MAIN, fn))
    _, supp = POLE_SPEC[(model, pole)]
    for fn in supp:
        recs += load(os.path.join(SUPP, fn))
    return recs


def compute_pole(model, pole):
    framing = POLE_FRAMING[pole]
    recs = gather_records(model, pole)

    # 1) blind baselines: median parsed_amount per (cli, mode) over blind records
    blind_vals = {}  # (cli,mode) -> list
    for r in recs:
        if is_blind(r) and r.get("parsed_amount") is not None:
            blind_vals.setdefault((r["cli"], mode_of(r)), []).append(float(r["parsed_amount"]))
    blind = {k: median(v) for k, v in blind_vals.items()}

    # 2) framed x0.5 records for this pole framing
    # aggregate reps per (cli, mode): average parsed, keep anchor
    cell = {}  # (cli,mode) -> {'parsed':[...], 'anchor':a}
    for r in recs:
        if is_blind(r):
            continue
        if r.get("framing") != framing:
            continue
        if r.get("multiplier") != 0.5:
            continue
        if r.get("parsed_amount") is None or r.get("anchor") is None:
            continue
        key = (r["cli"], mode_of(r))
        d = cell.setdefault(key, {"parsed": [], "anchor": float(r["anchor"])})
        d["parsed"].append(float(r["parsed_amount"]))

    # per-case values: need both modes present and a blind for each mode
    clis = sorted({k[0] for k in cell})
    pull_pairs = []   # (cli, pull_think, pull_non)
    hug_pairs = []    # (cli, hug_think, hug_non)
    for cli in clis:
        ok = True
        vals = {}
        for mode in ("think", "non"):
            key = (cli, mode)
            if key not in cell:
                ok = False
                break
            if (cli, mode) not in blind:
                ok = False
                break
            parsed = mean(cell[key]["parsed"])
            anchor = cell[key]["anchor"]
            b = blind[(cli, mode)]
            denom = anchor - b
            if denom == 0:
                ok = False
                break
            raw_pull = (parsed - b) / denom
            clipped = min(1.0, max(0.0, raw_pull))
            hug = 1.0 if abs(parsed - anchor) / abs(anchor) <= 0.05 else 0.0
            vals[mode] = (clipped, hug)
        if not ok:
            continue
        pull_pairs.append((cli, vals["think"][0], vals["non"][0]))
        hug_pairs.append((cli, vals["think"][1], vals["non"][1]))

    n = len(pull_pairs)
    # Delta pull
    d_pull = [t - nn for (_, t, nn) in pull_pairs]
    d_hug = [t - nn for (_, t, nn) in hug_pairs]

    def paired(d):
        m = mean(d) * 100.0
        # paired t = one-sample t on the differences
        tstat, p = stats.ttest_1samp(d, 0.0)
        return m, p

    dp, pp = paired(d_pull)
    dh, ph = paired(d_hug)
    return n, dp, pp, dh, ph


def main():
    rows = []
    print(f"{'model':7} {'pole':3} {'n':>4} {'dpull':>8} {'p_pull':>9} {'dhug':>8} {'p_hug':>9}")
    for (model, pole), (ntarget, _) in POLE_SPEC.items():
        n, dp, pp, dh, ph = compute_pole(model, pole)
        rows.append({
            "model": model, "pole": pole, "n": n,
            "delta_pull": round(dp, 1), "p_pull": round(pp, 4),
            "delta_hug": round(dh, 1), "p_hug": round(ph, 4),
        })
        print(f"{model:7} {pole:3} {n:>4} {dp:>8.2f} {pp:>9.4f} {dh:>8.2f} {ph:>9.4f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "pole", "n", "delta_pull", "p_pull", "delta_hug", "p_hug"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
