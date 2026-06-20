#!/usr/bin/env python3
"""
FRESH recompute of tab:demand-characteristic (CLI.C.569614162).

The LaTeX table is a qualitative single-case trace of the THINKING arm for
Grok-4.3, DeepSeek-V4-Pro, and Doubao. The only recomputable numeric content
is:
  - blind (think) estimate per model  -> printed 4,444 for all three
  - S1 (fortune teller) adopted amount -> printed 5,522 (= anchor)
  - S5 (chief judge)    adopted amount -> printed 5,522 (= anchor)
  - Grok S2 (layperson) amount         -> printed 4,444 (= blind baseline)
  - the anchor on the x0.5 arm         -> 5,522
  - affirmed / true award              -> printed 11,044
  - DeepSeek "2 of 3 reps adopt the anchor at S1"

We pull each from raw_data/main_axis_30. Per metric defs, the blind baseline is
the MEDIAN over reps of the mode-matched blind condition (think arm -> think blind).
The table reports the *adopted output amount* (parsed_amount), not pull, so we
report the per-condition parsed amounts directly. For multi-rep cells (DeepSeek
think) we report the rep breakdown and the majority/median.

Only stdlib + raw json used; no old analysis script imported.
"""

import json
import os
import re
import statistics
import csv

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(BASE, "raw_data", "main_axis_30")
OUT_CSV = os.path.join(BASE, "tables", "demand_char.csv")

CASE = "CLI.C.569614162"

# THINKING-arm main files per the case's three models.
# Grok main think = T_0 ; DeepSeek main think = T_0.7 (vendor-fixed) ; Doubao main think = T_1.0
THINK_FILES = {
    "Grok": "Grok_T_0.json",
    "DeepSeek": "DeepSeek_T_0.7.json",
    "Doubao": "Doubao_T_1.0.json",
}


def load(fn):
    with open(os.path.join(RAW, fn)) as f:
        return json.load(f)


def is_blind(rec):
    return str(rec.get("condition", "")).startswith("blind")


def base_cond(rec):
    # strip trailing #r\d+ replication suffix
    return re.sub(r"#r\d+$", "", str(rec.get("condition", "")))


def amounts_for(recs, framing=None, mult=None, blind=False):
    """Return list of parsed_amount for matching records of this case."""
    out = []
    for r in recs:
        if r["cli"] != CASE:
            continue
        if blind:
            if is_blind(r):
                out.append(r["parsed_amount"])
            continue
        if is_blind(r):
            continue
        if framing is not None and r.get("framing") != framing:
            continue
        if mult is not None and r.get("multiplier") != mult:
            continue
        out.append(r["parsed_amount"])
    return out


def main():
    rows = []  # cell, model, computed_amount, detail

    results = {}
    for model, fn in THINK_FILES.items():
        results[model] = load(fn)

    # --- Affirmed / true award (case-level, same across models) ---
    true_amt = None
    for model, recs in results.items():
        for r in recs:
            if r["cli"] == CASE:
                true_amt = r["true_amount"]
                break
        if true_amt is not None:
            break
    rows.append(("affirmed_true_amount", "(case)", round(true_amt), f"raw true_amount={true_amt}"))

    # --- Anchor on x0.5 arm (S1/S5 use mult 0.5) ---
    anchor_x05 = None
    for r in results["Grok"]:
        if r["cli"] == CASE and not is_blind(r) and r.get("multiplier") == 0.5:
            anchor_x05 = r["anchor"]
            break
    rows.append(("anchor_x0.5", "(case)", anchor_x05, f"anchor at mult=0.5 = {anchor_x05}"))

    # --- Per-model: blind(think), S1 (GN, x0.5), S5 (G5, x0.5) ---
    # framing map: GN=S1 fortune teller ; G5=S5 chief judge ; G1=S2 layperson
    for model, recs in results.items():
        # blind (think) median over reps
        bl = amounts_for(recs, blind=True)
        bl_med = statistics.median(bl) if bl else None
        rows.append((f"{model}_blind_think", model, round(bl_med) if bl_med is not None else None,
                     f"reps={bl} median={bl_med}"))

        # S1 fortune teller (GN), x0.5 arm
        s1 = amounts_for(recs, framing="GN", mult=0.5)
        # majority value
        if s1:
            s1_mode = statistics.mode(s1)
            n_anchor = sum(1 for a in s1 if abs(a - anchor_x05) / abs(anchor_x05) <= 0.05)
            detail = f"reps={s1} majority={s1_mode} n_at_anchor={n_anchor}/{len(s1)}"
        else:
            s1_mode = None
            detail = "no reps"
        rows.append((f"{model}_S1_fortune", model, round(s1_mode) if s1_mode is not None else None, detail))

        # S5 chief judge (G5), x0.5 arm
        s5 = amounts_for(recs, framing="G5", mult=0.5)
        if s5:
            s5_mode = statistics.mode(s5)
            n_anchor5 = sum(1 for a in s5 if abs(a - anchor_x05) / abs(anchor_x05) <= 0.05)
            detail5 = f"reps={s5} majority={s5_mode} n_at_anchor={n_anchor5}/{len(s5)}"
        else:
            s5_mode = None
            detail5 = "no reps"
        rows.append((f"{model}_S5_chiefjudge", model, round(s5_mode) if s5_mode is not None else None, detail5))

    # --- Grok S2 layperson (G1), x0.5 arm (printed 4,444 = blind) ---
    grok = results["Grok"]
    s2 = amounts_for(grok, framing="G1", mult=0.5)
    s2_mode = statistics.mode(s2) if s2 else None
    rows.append(("Grok_S2_layperson", "Grok", round(s2_mode) if s2_mode is not None else None,
                 f"reps={s2} majority={s2_mode}"))

    # write CSV
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell", "model", "computed_amount", "detail"])
        for r in rows:
            w.writerow(r)

    print(f"CASE = {CASE}")
    print(f"{'cell':28s} {'model':10s} {'computed':>10s}  detail")
    for cell, model, val, detail in rows:
        print(f"{cell:28s} {model:10s} {str(val):>10s}  {detail}")
    print(f"\nWrote {OUT_CSV}")


if __name__ == "__main__":
    main()
