#!/usr/bin/env python3
"""
FRESH recompute of tab:temp-sensitivity (latex_v2/main.tex ~line 649).

For each model, recompute the Delta-pull (Low / High) under the SENSITIVITY run.
SENSITIVITY = the *_0.7 re-run for T=0 models; vendor-fixed temps for Doubao/Kimi;
DeepSeek moves non-thinking arm to 0.7 too.

Metric definitions (paper §3.5):
  pull = clip((parsed - blind)/(anchor - blind), 0, 1)
    blind = mode-matched no-anchor baseline, MEDIAN over reps, per case.
    (think arm uses think-blind, non arm uses non-blind)
  mode: think if thinking==True else non.
  adoption a = mean over cases of clipped_pull * 100
  Delta-pull (pp) = paired-per-case mean(clipped_pull_think - clipped_pull_non) * 100
  Tier map: GN=S1, G1=S2, E1=S3, {GL5,G4}=S4 (avg the two), G5=S5
    low group = {S1,S2}, high group = {S4,S5}
  Arm: MAIN arm = x0.5 (multiplier 0.5). Delta-pull uses the x0.5 arm.
  Per-case aggregation order: reps -> (cli,framing,mult) -> average framings within tier.

The Low / High cells = mean over the cases of (clipped_pull_think - clipped_pull_non),
averaged within the low tier set {S1,S2} and high tier set {S4,S5}, then averaged
across tiers and cases (pp).
"""
import json
import os
import statistics
from collections import defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(BASE, "raw_data", "main_axis_30")
OUT = os.path.join(BASE, "tables", "temp_sensitivity.csv")

FRAMING_TIER = {"GN": "S1", "G1": "S2", "E1": "S3", "GL5": "S4", "G4": "S4", "G5": "S5"}
LOW_TIERS = ["S1", "S2"]
HIGH_TIERS = ["S4", "S5"]

# Sensitivity-run file pairs: (model, non_file, think_file)
SENS_FILES = {
    "Gemini":   ("Gemini_N_0.7.json",   "Gemini_T_0.7.json"),
    "MiMo":     ("MiMo_N_0.7.json",     "MiMo_T_0.7.json"),
    "Grok":     ("Grok_N_0.7.json",     "Grok_T_0.7.json"),
    "Doubao":   ("Doubao_N_1.0.json",   "Doubao_T_1.0.json"),
    "DeepSeek": ("DeepSeek_N_0.7.json", "DeepSeek_T_0.7.json"),
    "Kimi":     ("Kimi_N_0.6.json",     "Kimi_T_1.0.json"),
    # GLM has no T_0.7 sensitivity run -> Not run
}

MULT_MAIN = 0.5  # x0.5 main arm


def load(fn):
    return json.load(open(os.path.join(RAW, fn)))


def is_blind(rec):
    return str(rec.get("condition", "")).startswith("blind")


def clip01(v):
    return max(0.0, min(1.0, v))


def blind_baseline_per_case(records):
    """median parsed_amount over blind reps, per cli."""
    bycli = defaultdict(list)
    for r in records:
        if is_blind(r) and r.get("parsed_amount") is not None:
            bycli[r["cli"]].append(float(r["parsed_amount"]))
    return {cli: statistics.median(v) for cli, v in bycli.items()}


def cell_pull_by_case_tier(records, blind):
    """
    Return dict: tier -> {cli: clipped_pull}
    Aggregation: reps -> (cli,framing) at mult=0.5 -> average framings within tier.
    """
    # step1: per (cli, framing) average pull over reps (mult==0.5 main arm only)
    bucket = defaultdict(list)  # (cli, framing) -> list of pulls
    for r in records:
        if is_blind(r):
            continue
        if r.get("multiplier") != MULT_MAIN:
            continue
        fr = r.get("framing")
        if fr not in FRAMING_TIER:
            continue
        cli = r["cli"]
        if cli not in blind:
            continue
        anchor = r.get("anchor")
        pa = r.get("parsed_amount")
        if anchor is None or pa is None:
            continue
        denom = float(anchor) - blind[cli]
        if denom == 0:
            continue
        pull = clip01((float(pa) - blind[cli]) / denom)
        bucket[(cli, fr)].append(pull)

    # average reps
    cf_pull = {k: statistics.mean(v) for k, v in bucket.items()}

    # step2: average framings within tier per case
    # tier -> cli -> list of framing-level pulls
    tier_case = defaultdict(lambda: defaultdict(list))
    for (cli, fr), p in cf_pull.items():
        tier = FRAMING_TIER[fr]
        tier_case[tier][cli].append(p)

    out = {}
    for tier, cd in tier_case.items():
        out[tier] = {cli: statistics.mean(v) for cli, v in cd.items()}
    return out


def delta_for_group(non_tier, think_tier, tiers):
    """
    For each tier in `tiers`, paired per-case diff (think - non), then average
    over cases within the tier, then average the tier means. Return pp.
    Also return n cases used.
    """
    tier_means = []
    for tier in tiers:
        if tier not in non_tier or tier not in think_tier:
            continue
        nc = non_tier[tier]
        tc = think_tier[tier]
        clis = sorted(set(nc) & set(tc))
        diffs = [tc[c] - nc[c] for c in clis]
        if diffs:
            tier_means.append(statistics.mean(diffs))
    if not tier_means:
        return None
    return statistics.mean(tier_means) * 100.0


def compute_model(model, non_file, think_file, exclude_s1=False):
    non = load(non_file)
    think = load(think_file)
    non_blind = blind_baseline_per_case(non)
    think_blind = blind_baseline_per_case(think)
    non_tier = cell_pull_by_case_tier(non, non_blind)
    think_tier = cell_pull_by_case_tier(think, think_blind)

    low_tiers = LOW_TIERS[:]
    if exclude_s1:
        # treat S2 as the low tier (drop S1)
        low_tiers = ["S2"]
    dL = delta_for_group(non_tier, think_tier, low_tiers)
    dH = delta_for_group(non_tier, think_tier, HIGH_TIERS)
    return dL, dH


def fmt(v):
    if v is None:
        return "---"
    s = f"{v:+.1f}"
    return s.replace("+", "+").replace("-", "−")  # display minus


def main():
    rows = []
    header = ["model", "delta_pull_low", "delta_pull_high"]
    print(f"{'model':<22} {'Low':>8} {'High':>8}")
    for model, (nf, tf) in SENS_FILES.items():
        dL, dH = compute_model(model, nf, tf)
        rows.append([model, f"{dL:+.1f}" if dL is not None else "",
                     f"{dH:+.1f}" if dH is not None else ""])
        print(f"{model:<22} {dL:>+8.1f} {dH:>+8.1f}")
        if model == "Grok":
            dL2, dH2 = compute_model(model, nf, tf, exclude_s1=True)
            rows.append(["Grok (excl. S1)", f"{dL2:+.1f}", f"{dH2:+.1f}"])
            print(f"{'Grok (excl. S1)':<22} {dL2:>+8.1f} {dH2:>+8.1f}")
    # GLM not run
    rows.insert(1, ["GLM", "Not run", "Not run"])
    print(f"{'GLM':<22} {'Not run':>8} {'Not run':>8}")

    with open(OUT, "w") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(r) + "\n")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
