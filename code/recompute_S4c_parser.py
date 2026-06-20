#!/usr/bin/env python3
"""
Recompute Table S4c (parser-specification sensitivity on the crossing tests),
"main corrected parser" rows: Gemini (n=30), GLM (n=30), MiMo (n=30).

Metric chain (paper sec 3.5):
  - per-case clipped_pull is taken from tables/per_case_pull.csv (authoritative,
    corrections already baked in => this IS the "main corrected parser").
  - arm = x05 (main x0.5 arm).
  - tiers: 1=Fortune(S1) 2=Layperson(S2) 3=Law student(S3) 4=Expert(S4) 5=Chief judge(S5).
  - Delta_pull per case per tier = clipped_pull(think) - clipped_pull(non).
  - Low group = mean of Delta over tiers {1,2}; High group = mean of Delta over tiers {4,5}.
  - L-H contrast: per-case (low - high); paired t-test over the 30 cases.
    L-H est. reported in pp = mean * 100.
  - Linear trend: for EACH case, OLS-regress its 5-tier Delta_pull (pp) on
    tier_index (1..5) and recover the slope; then a one-sample t-test over the
    30 case-level slopes (df = n_cases - 1). This respects the case clustering
    (matching the paper's df=29 convention) rather than treating all 150
    case x tier observations as independent.

NOTE: positive slope means reasoning effect rises with credibility, so the table
prints +slope. The L-H contrast prints (low - high) which is NEGATIVE when the
effect rises with credibility.
"""

import csv
import os
import numpy as np
from scipy import stats

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PCP = os.path.join(BASE, "tables", "per_case_pull.csv")
OUT = os.path.join(BASE, "tables", "S4c_parser.csv")

TIER_INDEX = {
    "Fortune": 1,
    "Layperson": 2,
    "Law student": 3,
    "Expert": 4,
    "Chief judge": 5,
}
MODELS = ["Gemini", "GLM", "MiMo"]


def load():
    rows = []
    with open(PCP, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def build_delta(rows, model):
    """
    Returns dict: cli -> {tier_index -> delta_pull}
    using arm=x05 only, think - non.
    """
    # (cli, tier_index, mode) -> clipped_pull
    store = {}
    for r in rows:
        if r["model"] != model:
            continue
        if r["arm"] != "x05":
            continue
        ti = TIER_INDEX[r["tier"]]
        key = (r["cli"], ti, r["mode"])
        store[key] = float(r["clipped_pull"])

    cases = sorted({k[0] for k in store})
    delta = {}
    for cli in cases:
        d = {}
        for ti in range(1, 6):
            non = store.get((cli, ti, "non"))
            think = store.get((cli, ti, "think"))
            if non is None or think is None:
                d = None
                break
            d[ti] = think - non
        if d is not None:
            delta[cli] = d
    return delta


def compute(model, rows):
    delta = build_delta(rows, model)
    cases = sorted(delta)
    n = len(cases)

    # --- L-H contrast (paired t over cases) ---
    low = np.array([np.mean([delta[c][1], delta[c][2]]) for c in cases])
    high = np.array([np.mean([delta[c][4], delta[c][5]]) for c in cases])
    diff = low - high  # negative when effect rises with credibility
    lh_est_pp = diff.mean() * 100.0
    t_lh, p_lh = stats.ttest_rel(low, high)

    # --- Linear trend: per-case OLS slope, then one-sample t over cases ---
    xbar = np.mean([1, 2, 3, 4, 5])
    sxx = sum((ti - xbar) ** 2 for ti in range(1, 6))
    slopes = []
    for c in cases:
        b = sum((ti - xbar) * (delta[c][ti] * 100.0) for ti in range(1, 6)) / sxx
        slopes.append(b)
    slopes = np.array(slopes)
    slope = slopes.mean()
    t_slope, p_slope = stats.ttest_1samp(slopes, 0.0)

    return {
        "model": model,
        "n": n,
        "lh_est_pp": lh_est_pp,
        "lh_t": t_lh,
        "lh_p": p_lh,
        "slope": slope,
        "slope_t": t_slope,
        "slope_p": p_slope,
    }


def main():
    rows = load()
    results = [compute(m, rows) for m in MODELS]

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "cases", "lh_est_pp", "lh_t", "lh_p",
                    "lin_slope_pp_per_tier", "lin_t", "lin_p"])
        for r in results:
            w.writerow([r["model"], r["n"],
                        f"{r['lh_est_pp']:.4f}", f"{r['lh_t']:.4f}", f"{r['lh_p']:.6f}",
                        f"{r['slope']:.4f}", f"{r['slope_t']:.4f}", f"{r['slope_p']:.6f}"])

    print(f"{'model':<8} {'n':>3} {'L-H est(pp)':>12} {'L-H t':>8} {'L-H p':>10} "
          f"{'slope':>8} {'lin t':>8} {'lin p':>10}")
    for r in results:
        print(f"{r['model']:<8} {r['n']:>3} {r['lh_est_pp']:>12.2f} {r['lh_t']:>8.2f} "
              f"{r['lh_p']:>10.5f} {r['slope']:>+8.2f} {r['slope_t']:>8.2f} {r['slope_p']:>10.5f}")

    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
