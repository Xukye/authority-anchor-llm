#!/usr/bin/env python3
"""
FRESH recompute of tab:truth-anchor: "Outputs track the planted anchor, not the affirmed award."
Chief-judge (S5/G5) anchor, thinking arm, 3 crossing models (Gemini, GLM, MiMo).

Logic (paper §5.2 + table note):
  Per case (cli) for each model:
    - blind  = MEDIAN parsed_amount over think-blind reps for that case
    - true   = affirmed award (true_amount)
    - For each arm (x0.5, x2): take the G5 thinking output (parsed_amount), the planted anchor
  A value v is "within +/-5% of award"  if |v - true|  / |true|   <= 0.05
  A value v is "within +/-5% of anchor"  if |v - anchor|/ |anchor| <= 0.05
  (hug definition, eps=0.05)

  TOP ROWS (per model): cases where blind is OFF the award (|blind-true|/|true| > 0.05).
     n = count of such cases. Among those cases, for each arm count:
        award-hits  = outputs within +/-5% of award
        anchor-hits = outputs within +/-5% of anchor
     Cell printed as  award / anchor.  Total = sum over the two arms.

  BOTTOM ROW: the 9 cases (POOLED over the 3 models) where blind WAS within +/-5% of award.
     Per arm, count award-hits / anchor-hits across all such (model,case) pairs.

  Stars: binomial test of anchor-hits vs award-hits among the +/-5% landers.
"""
import json, os, statistics
from scipy.stats import binomtest

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(BASE, "raw_data", "main_axis_30")
OUT = os.path.join(BASE, "tables", "truth_anchor.csv")

MODELS = {"Gemini": "Gemini_T_0.json", "GLM": "GLM_T_0.json", "MiMo": "MiMo_T_0.json"}
EPS = 0.05


def load(fname):
    return json.load(open(os.path.join(RAW, fname)))


def near(v, target, eps=EPS):
    if v is None or target is None or target == 0:
        return False
    return abs(v - target) / abs(target) <= eps


def dedupe_first(records, keyfn):
    """Keep first record per key (dedupe the GLM 31-count duplicates)."""
    seen = {}
    for r in records:
        k = keyfn(r)
        if k not in seen:
            seen[k] = r
    return seen


def analyze_model(records):
    """Return per-case dict: cli -> {true, blind, x05_out, x05_anchor, x2_out, x2_anchor}."""
    # blind reps per case (median)
    blind_by_cli = {}
    for r in records:
        if r["condition"].startswith("blind"):
            blind_by_cli.setdefault(r["cli"], []).append(r["parsed_amount"])
    blind_med = {c: statistics.median([x for x in vs if x is not None]) for c, vs in blind_by_cli.items()
                 if any(x is not None for x in vs)}

    # G5 outputs per (cli, mult) -- dedupe, first rep
    g5 = {}  # (cli, mult) -> record
    for r in records:
        if r.get("framing") == "G5":
            k = (r["cli"], r["multiplier"])
            if k not in g5:
                g5[k] = r

    cases = {}
    clis = set(blind_med) | {c for (c, m) in g5}
    for cli in clis:
        b = blind_med.get(cli)
        # true_amount from any record for that cli
        true = None
        x05 = g5.get((cli, 0.5))
        x2 = g5.get((cli, 2.0))
        if x05:
            true = x05["true_amount"]
        elif x2:
            true = x2["true_amount"]
        cases[cli] = {
            "true": true,
            "blind": b,
            "x05_out": x05["parsed_amount"] if x05 else None,
            "x05_anchor": x05["anchor"] if x05 else None,
            "x2_out": x2["parsed_amount"] if x2 else None,
            "x2_anchor": x2["anchor"] if x2 else None,
        }
    return cases


def main():
    all_cases = {m: analyze_model(load(f)) for m, f in MODELS.items()}

    rows = []
    # Track bottom-row pooled cases (blind already on award)
    pooled_on_award = []  # list of (model, cli, case)

    # grand pooled counts for in-text 1 vs 149 / 162
    grand_award_hits = 0
    grand_anchor_hits = 0
    grand_cells = 0

    for m, cases in all_cases.items():
        off_cases = []
        on_cases = []
        for cli, c in cases.items():
            if c["true"] is None or c["blind"] is None:
                continue
            if not (c["x05_out"] is not None and c["x2_out"] is not None):
                continue
            blind_on_award = near(c["blind"], c["true"])
            if blind_on_award:
                on_cases.append((cli, c))
                pooled_on_award.append((m, cli, c))
            else:
                off_cases.append((cli, c))

        n = len(off_cases)
        # per-arm award / anchor hits among off cases
        def arm_counts(arm_out, arm_anchor):
            aw = an = 0
            for cli, c in off_cases:
                v = c[arm_out]
                if near(v, c["true"]):
                    aw += 1
                if near(v, c[arm_anchor]):
                    an += 1
            return aw, an

        x05_aw, x05_an = arm_counts("x05_out", "x05_anchor")
        x2_aw, x2_an = arm_counts("x2_out", "x2_anchor")
        tot_aw = x05_aw + x2_aw
        tot_an = x05_an + x2_an

        # stars: binomial of anchor vs award hits among +/-5% landers (per total)
        landers = tot_aw + tot_an
        if landers > 0:
            p = binomtest(tot_an, landers, 0.5, alternative="two-sided").pvalue
        else:
            p = None
        stars = star(p)

        grand_award_hits += tot_aw
        grand_anchor_hits += tot_an
        grand_cells += landers

        rows.append({
            "model": m, "n": n,
            "x05_award": x05_aw, "x05_anchor": x05_an,
            "x2_award": x2_aw, "x2_anchor": x2_an,
            "total_award": tot_aw, "total_anchor": tot_an,
            "p": p, "stars": stars,
        })
        print(f"{m}: n(off)={n}  x0.5 {x05_aw}/{x05_an}  x2 {x2_aw}/{x2_an}  "
              f"Total {tot_aw}/{tot_an}  p={p}")

    # Bottom row: pooled "blind on award" cases
    n_bottom = len(pooled_on_award)
    def bottom_arm(arm_out, arm_anchor):
        aw = an = 0
        for m, cli, c in pooled_on_award:
            v = c[arm_out]
            if near(v, c["true"]):
                aw += 1
            if near(v, c[arm_anchor]):
                an += 1
        return aw, an
    b_x05_aw, b_x05_an = bottom_arm("x05_out", "x05_anchor")
    b_x2_aw, b_x2_an = bottom_arm("x2_out", "x2_anchor")
    b_tot_aw, b_tot_an = b_x05_aw + b_x2_aw, b_x05_an + b_x2_an
    b_landers = b_tot_aw + b_tot_an
    b_p = binomtest(b_tot_an, b_landers, 0.5).pvalue if b_landers > 0 else None

    print(f"\nBLIND ON AWARD (pooled): n={n_bottom}  x0.5 {b_x05_aw}/{b_x05_an}  "
          f"x2 {b_x2_aw}/{b_x2_an}  Total {b_tot_aw}/{b_tot_an}  p={b_p}")

    rows.append({
        "model": "Blind on award (pooled)", "n": n_bottom,
        "x05_award": b_x05_aw, "x05_anchor": b_x05_an,
        "x2_award": b_x2_aw, "x2_anchor": b_x2_an,
        "total_award": b_tot_aw, "total_anchor": b_tot_an,
        "p": b_p, "stars": star(b_p),
    })

    # in-text pooled 3 top rows: award vs anchor of 162 cells
    print(f"\nIN-TEXT POOLED (3 top rows): {grand_award_hits} award-hits vs "
          f"{grand_anchor_hits} anchor-hits of {sum(r['n'] for r in rows[:3])*2} cells")

    # write CSV
    import csv
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "n", "x05_award", "x05_anchor", "x2_award", "x2_anchor",
                    "total_award", "total_anchor", "p", "stars"])
        for r in rows:
            w.writerow([r["model"], r["n"], r["x05_award"], r["x05_anchor"],
                        r["x2_award"], r["x2_anchor"], r["total_award"],
                        r["total_anchor"], f"{r['p']:.2e}" if r["p"] is not None else "",
                        r["stars"]])
    print("\nwrote", OUT)


def star(p):
    if p is None:
        return ""
    if p < .001:
        return "***"
    if p < .01:
        return "**"
    if p < .05:
        return "*"
    return ""


if __name__ == "__main__":
    main()
