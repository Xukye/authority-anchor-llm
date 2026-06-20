#!/usr/bin/env python3
"""
Recompute Table S5 (per-tier adoption metrics, all seven models) from raw data.

Metrics (paper section 3.5):
  - adoption a = mean(clipped_pull over 30 cases) * 100  (0-100 scale)
  - a_non  : non-thinking arm adoption
  - a_think: thinking arm adoption
  - Delta pull (pp) = a_think - a_non = mean over cases of paired diff
  - 95% CI on Delta over the 30 per-case differences (paired t, scipy.stats.t)
  - c (normalized change) = Delta/(1 - a_non) if Delta >= 0 else Delta/a_non,
        with a in [0,1] fraction (so Delta also a fraction here).

Arm: x0.5 main arm.
Tier map: S1=Fortune, S2=Layperson, S3=Law student, S4=Expert, S5=Chief judge.

Source of truth for per-case clipped pull on the 30 main cases:
  Database/tables/per_case_pull.csv (corrections already applied, arm=x05).
"""

import csv
import math
import os
from collections import defaultdict

import scipy.stats as st

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PULL_CSV = os.path.join(BASE, "tables", "per_case_pull.csv")
OUT_CSV = os.path.join(BASE, "tables", "S5_adoption.csv")

# tier label in csv -> (tier code, display order)
TIER_ORDER = [
    ("Fortune", "S1"),
    ("Layperson", "S2"),
    ("Law student", "S3"),
    ("Expert", "S4"),
    ("Chief judge", "S5"),
]
TIER_CODE = {lab: code for lab, code in TIER_ORDER}

MODEL_ORDER = ["Gemini", "GLM", "MiMo", "Grok", "Doubao", "DeepSeek", "Kimi"]


def load_pull():
    # data[(model, tier_label)][cli][mode] = clipped_pull
    data = defaultdict(lambda: defaultdict(dict))
    with open(PULL_CSV) as f:
        rd = csv.DictReader(f)
        for row in rd:
            if row["arm"] != "x05":
                continue
            model = row["model"]
            tier = row["tier"]
            cli = row["cli"]
            mode = row["mode"]  # non | think
            cp = float(row["clipped_pull"])
            data[(model, tier)][cli][mode] = cp
    return data


def compute():
    data = load_pull()
    results = []
    for model in MODEL_ORDER:
        for tier_label, code in TIER_ORDER:
            cases = data[(model, tier_label)]
            non_vals = []
            think_vals = []
            diffs = []
            for cli, modes in sorted(cases.items()):
                if "non" not in modes or "think" not in modes:
                    continue
                non_vals.append(modes["non"])
                think_vals.append(modes["think"])
                diffs.append(modes["think"] - modes["non"])
            n = len(diffs)
            a_non = sum(non_vals) / n * 100.0
            a_think = sum(think_vals) / n * 100.0
            mean_diff = sum(diffs) / n * 100.0  # pp
            # 95% CI on paired diff (pp scale)
            sd = (sum((d * 100.0 - mean_diff) ** 2 for d in diffs) / (n - 1)) ** 0.5
            se = sd / math.sqrt(n)
            tcrit = st.t.ppf(0.975, n - 1)
            lo = mean_diff - tcrit * se
            hi = mean_diff + tcrit * se
            # c on fraction scale
            a_non_f = a_non / 100.0
            delta_f = mean_diff / 100.0
            if delta_f >= 0:
                denom = 1.0 - a_non_f
                c = delta_f / denom if denom != 0 else float("nan")
            else:
                c = delta_f / a_non_f if a_non_f != 0 else float("nan")
            results.append(
                {
                    "model": model,
                    "tier": code,
                    "n": n,
                    "a_non": a_non,
                    "a_think": a_think,
                    "delta": mean_diff,
                    "ci_lo": lo,
                    "ci_hi": hi,
                    "c": c,
                }
            )
    return results


def fmt_signed_int(x):
    r = round(x)
    # avoid -0
    if r == 0:
        r = 0
    return f"{r:+d}"


def main():
    results = compute()
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["model", "tier", "n", "a_non", "a_think", "delta_pp", "ci_lo", "ci_hi", "c"]
        )
        for r in results:
            w.writerow(
                [
                    r["model"],
                    r["tier"],
                    r["n"],
                    f"{r['a_non']:.3f}",
                    f"{r['a_think']:.3f}",
                    f"{r['delta']:.3f}",
                    f"{r['ci_lo']:.3f}",
                    f"{r['ci_hi']:.3f}",
                    f"{r['c']:.4f}",
                ]
            )

    print(
        f"{'model':<10} {'tier':<4} {'n':>3} {'a_non':>7} {'a_think':>8} "
        f"{'Dpull':>7} {'CIlo':>7} {'CIhi':>7} {'c':>7}"
    )
    for r in results:
        print(
            f"{r['model']:<10} {r['tier']:<4} {r['n']:>3} "
            f"{round(r['a_non']):>7d} {round(r['a_think']):>8d} "
            f"{fmt_signed_int(r['delta']):>7} {fmt_signed_int(r['ci_lo']):>7} "
            f"{fmt_signed_int(r['ci_hi']):>7} {r['c']:>+7.2f}"
        )
    print(f"\nWrote {OUT_CSV}")


if __name__ == "__main__":
    main()
