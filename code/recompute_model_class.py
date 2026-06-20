#!/usr/bin/env python3
"""
FRESH recompute of Table tab:7-model-class (7-model classification).
Per model, on the x0.5 MAIN arm using each model's MAIN-arm temps:
  L = mean Delta-pull over low group {S1 Fortune, S2 Layperson}
  H = mean Delta-pull over high group {S4 Expert (avg GL5,G4), S5 Chief judge}
  Trend p = ordinal-trend paired test across tiers S1..S5 (only crossing models + Grok)

Metric defs (paper 3.5):
  pull = clip((parsed - blind)/(anchor - blind), 0, 1)
    blind = mode-matched no-anchor baseline, MEDIAN over reps per case.
  mode = think if condition (strip trailing #r\\d+) ends with "_T" OR thinking==True; else non.
  cell adoption a = mean(clipped_pull over cases) * 100.
  Delta-pull (pp) = a_think - a_non, paired per case (mean over cases of think-non).
  Tier map: GN=S1, G1=S2, E1=S3, {GL5,G4}=S4 (avg the two per case), G5=S5.
  low={S1,S2}, high={S4,S5}.
  Per-case aggregation: reps -> (cli,framing,mult) -> avg mults in arm -> avg framings within tier.

This script does NOT import/read any old analysis script.
It rebuilds pull from raw_data, then ALSO cross-checks against tables/per_case_pull.csv.
"""
import json, csv, re, os
from collections import defaultdict
from statistics import median, mean
from scipy import stats

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(BASE, "raw_data", "main_axis_30")
OUT = os.path.join(BASE, "tables", "model_class.csv")

# MAIN-arm temp files per model (paper Table 8)
MAIN_FILES = {
    "Gemini":   ["Gemini_N_0.json",   "Gemini_T_0.json"],
    "GLM":      ["GLM_N_0.json",      "GLM_T_0.json"],
    "MiMo":     ["MiMo_N_0.json",     "MiMo_T_0.json"],
    "Grok":     ["Grok_N_0.json",     "Grok_T_0.json"],
    "Doubao":   ["Doubao_N_1.0.json", "Doubao_T_1.0.json"],
    "DeepSeek": ["DeepSeek_N_0.json", "DeepSeek_T_0.7.json"],
    "Kimi":     ["Kimi_N_0.6.json",   "Kimi_T_1.0.json"],
}

FRAMING_TO_TIER = {"GN": "S1", "G1": "S2", "E1": "S3", "GL5": "S4", "G4": "S4", "G5": "S5"}
TIER_INDEX = {"S1": 1, "S2": 2, "S3": 3, "S4": 4, "S5": 5}
LOW = ["S1", "S2"]
HIGH = ["S4", "S5"]
ALL_TIERS = ["S1", "S2", "S3", "S4", "S5"]


def strip_rep(cond):
    return re.sub(r"#r\d+$", "", str(cond))


def get_mode(rec):
    cond = strip_rep(rec.get("condition", ""))
    if cond.endswith("_T"):
        return "think"
    if rec.get("thinking") is True:
        return "non" if not cond.endswith("_T") and not _think_cond(cond) else "think"
    return "non"


def _think_cond(cond):
    # condition forms: "blind_T", "GN_0.5x_T". think if ends with _T
    return cond.endswith("_T")


def mode_of(rec):
    cond = strip_rep(rec.get("condition", ""))
    if cond.endswith("_T"):
        return "think"
    if rec.get("thinking") is True:
        return "think"
    return "non"


def is_blind(rec):
    return str(rec.get("condition", "")).startswith("blind")


def load_model(model):
    recs = []
    for fn in MAIN_FILES[model]:
        with open(os.path.join(RAW, fn)) as f:
            recs.extend(json.load(f))
    return recs


def compute_clipped_pull_per_case(model):
    """
    Returns nested dict: clipped[mode][framing][cli] = clipped pull (fraction 0..1)
    Built from raw_data with mode-matched MEDIAN blind baseline.
    Only x0.5 arm (multiplier == 0.5).
    """
    recs = load_model(model)

    # 1) blind baselines: median parsed_amount per (mode, cli) over reps
    blind_vals = defaultdict(list)  # (mode, cli) -> [parsed]
    for r in recs:
        if not is_blind(r):
            continue
        m = mode_of(r)
        pa = r.get("parsed_amount")
        if pa is None:
            continue
        blind_vals[(m, r["cli"])].append(pa)
    blind_base = {k: median(v) for k, v in blind_vals.items()}

    # 2) aggregate non-blind x0.5 records: reps -> (mode,framing,cli) mean parsed_amount
    cell_parsed = defaultdict(list)   # (mode, framing, cli) -> [parsed]
    cell_anchor = {}                  # (mode, framing, cli) -> anchor (should be const)
    for r in recs:
        if is_blind(r):
            continue
        if r.get("multiplier") != 0.5:
            continue
        fr = r.get("framing")
        if fr not in FRAMING_TO_TIER:
            continue
        m = mode_of(r)
        pa = r.get("parsed_amount")
        if pa is None:
            continue
        key = (m, fr, r["cli"])
        cell_parsed[key].append(pa)
        cell_anchor[key] = r.get("anchor")

    clipped = {"non": defaultdict(dict), "think": defaultdict(dict)}
    for (m, fr, cli), parsed_list in cell_parsed.items():
        anchor = cell_anchor[(m, fr, cli)]
        blind = blind_base.get((m, cli))
        if blind is None or anchor is None:
            continue
        denom = anchor - blind
        if denom == 0:
            continue
        parsed = mean(parsed_list)  # average reps per cell
        pull = (parsed - blind) / denom
        cp = max(0.0, min(1.0, pull))
        clipped[m][fr][cli] = cp
    return clipped


def tier_pull_per_case(clipped, mode):
    """
    Returns dict tier -> {cli: clipped_pull}, averaging the two framings within S4.
    """
    out = {}
    for tier in ALL_TIERS:
        framings = [fr for fr, t in FRAMING_TO_TIER.items() if t == tier]
        # collect per-cli values across framings, average
        per_cli = defaultdict(list)
        for fr in framings:
            for cli, v in clipped[mode].get(fr, {}).items():
                per_cli[cli].append(v)
        out[tier] = {cli: mean(vs) for cli, vs in per_cli.items()}
    return out


def delta_per_tier(clipped):
    """tier -> list of (cli, delta) paired per case."""
    tn = tier_pull_per_case(clipped, "non")
    tt = tier_pull_per_case(clipped, "think")
    out = {}
    for tier in ALL_TIERS:
        clis = sorted(set(tn[tier]) & set(tt[tier]))
        out[tier] = [(c, tt[tier][c] - tn[tier][c]) for c in clis]
    return out


def group_mean_delta(dpt, tiers):
    """Mean Delta-pull (pp) over given tier group: per case avg over tiers, then mean over cases.
    Following table caption: L/H = mean Delta-pull over the tiers in the group."""
    # build per-case delta averaged across the tiers in the group, then mean over cases
    per_cli = defaultdict(list)
    for tier in tiers:
        for cli, d in dpt[tier]:
            per_cli[cli].append(d)
    case_deltas = [mean(v) for v in per_cli.values() if len(v) == len(tiers)]
    return mean(case_deltas) * 100.0  # pp


def trend_p(dpt):
    """Ordinal-trend test across S1..S5 per case.
    Per case: slope of delta vs tier-index (1..5). Paired t-test of slopes vs 0.
    Returns p (two-sided)."""
    # per case collect (tier_index, delta)
    per_cli = defaultdict(list)
    for tier in ALL_TIERS:
        ti = TIER_INDEX[tier]
        for cli, d in dpt[tier]:
            per_cli[cli].append((ti, d))
    slopes = []
    for cli, pts in per_cli.items():
        if len(pts) < 5:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        # linear regression slope
        mx = mean(xs); my = mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = sum((x - mx) ** 2 for x in xs)
        slopes.append(num / den)
    t, p = stats.ttest_1samp(slopes, 0.0)
    return mean(slopes), p, len(slopes)


# ---- per_case_pull.csv cross-check ----
def from_csv():
    path = os.path.join(BASE, "tables", "per_case_pull.csv")
    rows = [r for r in csv.DictReader(open(path)) if r["arm"] == "x05"]
    tier_csv = {"Fortune": "S1", "Layperson": "S2", "Law student": "S3",
                "Expert": "S4", "Chief judge": "S5"}
    # model -> tier -> mode -> {cli: clipped_pull}
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for r in rows:
        t = tier_csv[r["tier"]]
        data[r["model"]][t][r["mode"]][r["cli"]] = float(r["clipped_pull"])
    return data


def csv_dpt(data, model):
    out = {}
    for tier in ALL_TIERS:
        non = data[model][tier]["non"]
        thk = data[model][tier]["think"]
        clis = sorted(set(non) & set(thk))
        out[tier] = [(c, thk[c] - non[c]) for c in clis]
    return out


def main():
    results = []
    print(f"{'model':<10} {'L(raw)':>9} {'H(raw)':>9} {'trendp(raw)':>12} | "
          f"{'L(csv)':>9} {'H(csv)':>9} {'trendp(csv)':>12}")
    csv_data = from_csv()
    for model in ["Gemini", "GLM", "MiMo", "Grok", "Doubao", "DeepSeek", "Kimi"]:
        clipped = compute_clipped_pull_per_case(model)
        dpt = delta_per_tier(clipped)
        L = group_mean_delta(dpt, LOW)
        H = group_mean_delta(dpt, HIGH)
        slope, p, n = trend_p(dpt)

        dpt_c = csv_dpt(csv_data, model)
        Lc = group_mean_delta(dpt_c, LOW)
        Hc = group_mean_delta(dpt_c, HIGH)
        slope_c, pc, nc = trend_p(dpt_c)

        print(f"{model:<10} {L:>+9.2f} {H:>+9.2f} {p:>12.4g} | "
              f"{Lc:>+9.2f} {Hc:>+9.2f} {pc:>12.4g}")
        results.append({
            "model": model,
            "L_delta_pull_raw": round(L, 2), "H_delta_pull_raw": round(H, 2),
            "trend_slope_raw": round(slope, 3), "trend_p_raw": p,
            "L_delta_pull_csv": round(Lc, 2), "H_delta_pull_csv": round(Hc, 2),
            "trend_slope_csv": round(slope_c, 3), "trend_p_csv": pc,
        })

    # Grok excl. S1: L = layperson tier (S2) alone, H unchanged, trend over S2..S5
    print("\n-- Grok excl. S1 (L = S2 layperson alone; trend over S2..S5) --")
    for src_name, dpt_src in [("raw", delta_per_tier(compute_clipped_pull_per_case("Grok"))),
                              ("csv", csv_dpt(csv_data, "Grok"))]:
        L2 = group_mean_delta(dpt_src, ["S2"])
        H2 = group_mean_delta(dpt_src, HIGH)
        # trend over S2..S5
        per_cli = defaultdict(list)
        for tier in ["S2", "S3", "S4", "S5"]:
            ti = TIER_INDEX[tier]
            for cli, d in dpt_src[tier]:
                per_cli[cli].append((ti, d))
        slopes = []
        for cli, pts in per_cli.items():
            if len(pts) < 4:
                continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            mx = mean(xs); my = mean(ys)
            num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            den = sum((x - mx) ** 2 for x in xs)
            slopes.append(num / den)
        t, p2 = stats.ttest_1samp(slopes, 0.0)
        print(f"  Grok({src_name}): L(S2)={L2:+.2f}  H={H2:+.2f}  slope={mean(slopes):+.2f}/tier  p={p2:.4g}")
        if src_name == "raw":
            results.append({"model": "Grok (excl. S1)",
                            "L_delta_pull_raw": round(L2, 2), "H_delta_pull_raw": round(H2, 2),
                            "trend_slope_raw": round(mean(slopes), 3), "trend_p_raw": p2,
                            "L_delta_pull_csv": "", "H_delta_pull_csv": "",
                            "trend_slope_csv": "", "trend_p_csv": ""})

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        for r in results:
            w.writerow(r)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
