#!/usr/bin/env python3
"""
FRESH recompute of Table tab:per-tier (Per-tier reasoning effect).

Each cell = Delta-pull (pp) and c (normalized change), for tiers S1..S5 (rows)
x models {Gemini, GLM, MiMo, Grok-4.3} (columns), on the x0.5 main arm, n=30.

Metric definitions (paper section 3.5):
  - pull (per case, per mode): clipped_pull, already in tables/per_case_pull.csv
    (corrections applied; blind = mode-matched median baseline already baked in).
  - cell adoption a = mean(clipped_pull over cases) (0..1 fraction).
  - Delta-pull (pp) = (a_think - a_non) * 100, paired per case.
  - c (normalized change) = Delta/(1 - a_non) if Delta>=0 else Delta/a_non,
    with a in [0,1] fraction. (Delta here as fraction, not pp.)

Tier map: S1=Fortune, S2=Layperson, S3=Law student, S4=Expert (GL5+G4 already
averaged in the CSV), S5=Chief judge.

We use tables/per_case_pull.csv (authoritative, corrections applied) for the
x0.5 arm. No old analysis script is imported.
"""
import csv
import os

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PER_CASE = os.path.join(BASE, "tables", "per_case_pull.csv")
OUT = os.path.join(BASE, "tables", "per_tier.csv")

TIER_BY_INDEX = {1: "S1", 2: "S2", 3: "S3", 4: "S4", 5: "S5"}
TIER_NAME = {
    "Fortune": 1,
    "Layperson": 2,
    "Law student": 3,
    "Expert": 4,
    "Chief judge": 5,
}
MODELS = ["Gemini", "GLM", "MiMo", "Grok"]
ARM = "x05"


def load():
    rows = list(csv.DictReader(open(PER_CASE)))
    return rows


def cell_delta_c(rows, model, tier_name):
    """Return (delta_pp, c) for one model x tier cell on the x05 arm."""
    sub = [
        r
        for r in rows
        if r["model"] == model and r["arm"] == ARM and r["tier"] == tier_name
    ]
    # build per-case paired think/non
    by_case_think = {}
    by_case_non = {}
    for r in sub:
        v = float(r["clipped_pull"])
        if r["mode"] == "think":
            by_case_think[r["cli"]] = v
        else:
            by_case_non[r["cli"]] = v
    clis = sorted(set(by_case_think) & set(by_case_non))
    n = len(clis)
    think_vals = [by_case_think[c] for c in clis]
    non_vals = [by_case_non[c] for c in clis]
    a_think = sum(think_vals) / n  # fraction
    a_non = sum(non_vals) / n      # fraction
    # paired diff == diff of means
    delta_frac = a_think - a_non
    delta_pp = delta_frac * 100.0
    # normalized change c
    if delta_frac >= 0:
        denom = 1.0 - a_non
    else:
        denom = a_non
    c = delta_frac / denom if denom != 0 else float("nan")
    return delta_pp, c, n, a_non, a_think


def main():
    rows = load()
    results = []  # (tier_label, model, delta_pp, c)
    print(f"{'Tier':<5} {'Model':<8} {'a_non':>7} {'a_think':>8} {'Dpull(pp)':>10} {'c':>8}  n")
    for ti in [1, 2, 3, 4, 5]:
        tier_label = TIER_BY_INDEX[ti]
        tier_name = [k for k, v in TIER_NAME.items() if v == ti][0]
        for model in MODELS:
            dpp, c, n, a_non, a_think = cell_delta_c(rows, model, tier_name)
            results.append((tier_label, model, dpp, c, n))
            print(
                f"{tier_label:<5} {model:<8} {a_non:7.4f} {a_think:8.4f} "
                f"{dpp:10.2f} {c:8.3f}  {n}"
            )

    # write csv
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tier", "model", "delta_pull_pp", "c", "n",
                    "delta_pull_round", "c_round"])
        for tier_label, model, dpp, c, n in results:
            w.writerow([tier_label, model, f"{dpp:.4f}", f"{c:.4f}", n,
                        round(dpp), round(c, 2)])
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
