#!/usr/bin/env python3
"""
Recompute tab:clip-robust (Clipped vs. unclipped) FRESH from Database data.

For each of the 7 models, on the x0.5 arm, using per_case_pull.csv (authoritative
per-case pull on the 30 main cases):

  Per-case Delta_pull(tier) = pull_think(case,tier) - pull_non(case,tier)
  where pull is either clipped_pull or raw_pull (unclipped).

  Tier rank: Fortune=1, Layperson=2, Law student=3, Expert=4, Chief judge=5
  (Expert already = avg of GL5,G4 per case, baked into per_case_pull.csv).

  Trend (pp/tier): per-case OLS slope of Delta_pull on tier rank, averaged over
                   30 cases, x100; paired t-test over the 30 per-case slopes (df=29).
  Contrast (L-H) : per case, mean Delta_pull over {S1,S2} minus mean over {S4,S5},
                   x100; paired t-test over 30 per-case contrasts (df=29).
  Crossing (tier): interpolated tier where the MEAN-over-cases Delta_pull(tier)
                   changes sign (cell-level adjacency), x0.5 arm.
  Clipped cells  : among the 30*5*2 = 300 per-case framed cells (x0.5 arm),
                   count raw_pull<0, raw_pull>1, and all-clipped; report as counts
                   and as % of 300.

p-stars: dagger p<.10, * p<.05, ** p<.01, *** p<.001 (two-tailed).
"""
import csv
import os
import math
import os
from collections import defaultdict
from scipy import stats

HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PCP = HERE + "/tables/per_case_pull.csv"
OUT = HERE + "/tables/clip_robust.csv"

MODELS = ["Gemini", "GLM", "MiMo", "Grok", "Doubao", "DeepSeek", "Kimi"]
TIER_RANK = {"Fortune": 1, "Layperson": 2, "Law student": 3, "Expert": 4, "Chief judge": 5}
LOW = {1, 2}      # S1, S2
HIGH = {4, 5}     # S4, S5
ARM = "x05"


def load():
    # data[model][cli][tier_index][mode] = {"raw":..., "clip":...}
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    with open(PCP) as f:
        for r in csv.DictReader(f):
            if r["arm"] != ARM:
                continue
            m = r["model"]
            cli = r["cli"]
            ti = int(r["tier_index"])
            mode = r["mode"]
            data[m][cli][ti][mode] = {
                "raw": float(r["raw_pull"]),
                "clip": float(r["clipped_pull"]),
            }
    return data


def ols_slope(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den


def star(p):
    if p < .001:
        return "***"
    if p < .01:
        return "**"
    if p < .05:
        return "*"
    if p < .10:
        return "dagger"
    return ""


def crossing_tier(mean_delta):
    """Interpolated tier rank where mean Delta_pull changes sign.
    mean_delta: dict tier_index -> mean over cases. Find first adjacent pair
    (t, t+1) bracketing a sign change (from <=0 to >0 ascending) and linearly
    interpolate the zero. Low tiers negative, high tiers positive expected."""
    ranks = sorted(mean_delta.keys())
    for i in range(len(ranks) - 1):
        a, b = ranks[i], ranks[i + 1]
        ya, yb = mean_delta[a], mean_delta[b]
        if (ya <= 0 and yb > 0) or (ya < 0 and yb >= 0):
            if yb == ya:
                return float(a)
            frac = (0 - ya) / (yb - ya)
            return a + frac * (b - a)
    return None


def metric(data, model, kind):
    """kind = 'clip' or 'raw'. Returns dict of computed cells."""
    cases = sorted(data[model].keys())
    per_case_slope = []
    per_case_contrast = []
    mean_delta = defaultdict(list)  # tier -> list of per-case delta

    for cli in cases:
        tiers = data[model][cli]
        # per-case delta by tier
        delta = {}
        for ti in TIER_RANK.values():
            cell = tiers.get(ti)
            if cell is None or "think" not in cell or "non" not in cell:
                continue
            d = cell["think"][kind] - cell["non"][kind]
            delta[ti] = d
            mean_delta[ti].append(d)
        # slope over the 5 tiers for this case
        xs = sorted(delta.keys())
        ys = [delta[t] for t in xs]
        if len(xs) >= 2:
            per_case_slope.append(ols_slope(xs, ys))
        # contrast low - high
        low_vals = [delta[t] for t in delta if t in LOW]
        high_vals = [delta[t] for t in delta if t in HIGH]
        if low_vals and high_vals:
            c = sum(low_vals) / len(low_vals) - sum(high_vals) / len(high_vals)
            per_case_contrast.append(c)

    n = len(per_case_slope)
    # Trend
    slope_mean = sum(per_case_slope) / n * 100
    t_s, p_s = stats.ttest_1samp(per_case_slope, 0.0)
    # Contrast
    contrast_mean = sum(per_case_contrast) / len(per_case_contrast) * 100
    t_c, p_c = stats.ttest_1samp(per_case_contrast, 0.0)
    # Crossing: mean over cases per tier
    md = {t: sum(v) / len(v) for t, v in mean_delta.items()}
    cross = crossing_tier(md)

    return {
        "n": n,
        "trend": slope_mean,
        "trend_p": p_s,
        "trend_star": star(p_s),
        "contrast": contrast_mean,
        "contrast_p": p_c,
        "contrast_star": star(p_c),
        "crossing": cross,
        "mean_delta": md,
    }


def clipped_cells(data, model):
    """Count raw_pull<0, raw_pull>1, all over the 300 per-case framed cells
    (30 cases x 5 tiers x 2 modes), x0.5 arm."""
    below = above = total = ncells = 0
    for cli in data[model]:
        for ti in data[model][cli]:
            for mode in ("non", "think"):
                cell = data[model][cli][ti].get(mode)
                if cell is None:
                    continue
                ncells += 1
                rp = cell["raw"]
                b = rp < 0
                a = rp > 1
                if b:
                    below += 1
                if a:
                    above += 1
                if b or a:
                    total += 1
    return below, above, total, ncells


def main():
    data = load()
    rows = []
    print(f"{'Model':9} {'Metric':9} {'Trend':>9} {'p':>9} {'Contrast':>10} {'p':>9} {'Cross':>6}  ClipCells(<0/>1/all of N)")
    for m in MODELS:
        below, above, total, ncells = clipped_cells(data, m)
        pct_b = below / ncells * 100
        pct_a = above / ncells * 100
        pct_t = total / ncells * 100
        for kind, label in (("clip", "clipped"), ("raw", "unclipped")):
            r = metric(data, m, kind)
            if label == "clipped":
                cellstr = f"{below}/{above}/{total} (N={ncells})"
            else:
                cellstr = f"{pct_b:.1f}%/{pct_a:.1f}%/{pct_t:.1f}%"
            crossstr = f"{r['crossing']:.2f}" if r["crossing"] is not None else "---"
            print(f"{m:9} {label:9} {r['trend']:+9.1f} {r['trend_p']:9.4f} "
                  f"{r['contrast']:+10.1f} {r['contrast_p']:9.4f} {crossstr:>6}  {cellstr}")
            rows.append({
                "model": m, "metric": label,
                "trend_pp_per_tier": round(r["trend"], 2),
                "trend_p": round(r["trend_p"], 5),
                "trend_star": r["trend_star"],
                "contrast_L_minus_H": round(r["contrast"], 2),
                "contrast_p": round(r["contrast_p"], 5),
                "contrast_star": r["contrast_star"],
                "crossing_tier": round(r["crossing"], 3) if r["crossing"] is not None else "",
                "clip_below0_count": below, "clip_above1_count": above, "clip_all_count": total,
                "n_cells": ncells,
                "clip_below0_pct": round(pct_b, 2),
                "clip_above1_pct": round(pct_a, 2),
                "clip_all_pct": round(pct_t, 2),
                "n_cases": r["n"],
            })
        # mean-delta diagnostics
        for kind in ("clip", "raw"):
            r = metric(data, m, kind)
            md = r["mean_delta"]
            mdstr = " ".join(f"S{t}:{md[t]*100:+.1f}" for t in sorted(md))
            print(f"    [{kind:9} mean-delta by tier (pp)] {mdstr}")
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
