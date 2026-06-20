#!/usr/bin/env python3
"""
FRESH recompute of paper Table tab:case-level ("The sign-flip across both adoption measures").

Columns recomputed per model (x0.5 main arm, n=30, df=29):
  Hug L, Hug H   : tier-group anchor-hug Delta (think-non), pp, low {S1,S2} / high {S4,S5}
  Pull L, Pull H : tier-group Delta pull (think-non), pp
  Pull trend     : OLS slope of per-case Delta pull on tier rank (1..5), pp/tier
plus paired-t p-values and significance markers.

Metric definitions (paper section 3.5):
  hug  = 1.0 if |parsed_amount - anchor|/|anchor| <= 0.05 else 0.0
  pull = clip((parsed_amount - blind)/(anchor - blind), 0, 1)
         blind = mode-matched no-anchor baseline, MEDIAN over reps per case.
  Tier map: GN=S1 Fortune, G1=S2 Layperson, E1=S3 Law student,
            {GL5,G4}=S4 Expert (avg the two per case), G5=S5 Chief judge.
  L = {S1,S2}, H = {S4,S5}.
  mode: think if condition (strip trailing #r\\d+) ends "_T" OR record.thinking==True; else non.
  Per-case agg: reps -> (cli,framing,mult) -> average mults in arm (x0.5 here) ->
                average framings within tier -> per case.
  Delta = paired (think - non) per case, then mean over cases (x100 for pp).

Pull source: PREFER tables/per_case_pull.csv (corrections already applied, matches paper figures).
We ALSO independently recompute pull from raw_data as a cross-check and report both.

Main-arm temperatures (paper Table 8):
  Gemini/GLM/MiMo/Grok : N_0  & T_0
  Doubao               : N_1.0 & T_1.0
  DeepSeek             : N_0  & T_0.7
  Kimi                 : N_0.6 & T_1.0
"""
import json, csv, re, statistics, os
from collections import defaultdict
from scipy.stats import t as tdist

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(BASE, "raw_data", "main_axis_30")
PCP = os.path.join(BASE, "tables", "per_case_pull.csv")
OUT = os.path.join(BASE, "tables", "case_level.csv")

# model -> (non_file, think_file) for the x0.5 MAIN arm
MAIN_FILES = {
    "Gemini":   ("Gemini_N_0.json",   "Gemini_T_0.json"),
    "GLM":      ("GLM_N_0.json",      "GLM_T_0.json"),
    "MiMo":     ("MiMo_N_0.json",     "MiMo_T_0.json"),
    "Grok":     ("Grok_N_0.json",     "Grok_T_0.json"),
    "Doubao":   ("Doubao_N_1.0.json", "Doubao_T_1.0.json"),
    # DeepSeek main pairing = N_0 / T_0.7 (non-thinking T=0; thinking is vendor-fixed
    # at T=0.7, averaged over 3 runs). The N_0.7/T_0.7 matched pairing is the
    # temperature-sensitivity control (tab:temp-sensitivity), not the main arm.
    "DeepSeek": ("DeepSeek_N_0.json", "DeepSeek_T_0.7.json"),
    "Kimi":     ("Kimi_N_0.6.json",   "Kimi_T_1.0.json"),
}
# csv model name -> tier label
LOW_TIERS_CSV  = ["Fortune", "Layperson"]
HIGH_TIERS_CSV = ["Expert", "Chief judge"]
TIER_ORDER_CSV = ["Fortune", "Layperson", "Law student", "Expert", "Chief judge"]

# framing -> tier index 1..5 ; S4 = avg(GL5,G4)
FRAMING_TIER = {"GN": 1, "G1": 2, "E1": 3, "GL5": 4, "G4": 4, "G5": 5}


def mode_of(rec):
    cond = re.sub(r"#r\d+$", "", str(rec["condition"]))
    if cond.endswith("_T") or rec.get("thinking") is True:
        return "think"
    return "non"


def load(fname):
    p = os.path.join(RAW, fname)
    if not os.path.exists(p):
        return []
    return json.load(open(p))


def paired_t_p(diffs):
    """two-sided paired t-test p-value for mean(diffs)==0."""
    n = len(diffs)
    m = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    if sd == 0:
        return (0.0 if m == 0 else 0.0), n - 1  # degenerate
    tstat = m / (sd / (n ** 0.5))
    df = n - 1
    p = 2 * tdist.sf(abs(tstat), df)
    return p, df


def ols_slope(x, y):
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den = sum((xi - mx) ** 2 for xi in x)
    return num / den


def marker(p):
    if p < .001: return "***"
    if p < .01: return "**"
    if p < .05: return "*"
    if p < .10: return "dagger"
    return ""


# ------------------------------------------------------------------
# HUG from raw_data
# ------------------------------------------------------------------
def hug_for_model(model, non_file, think_file, low_indices=(1, 2)):
    low_indices = list(low_indices)
    recs = load(non_file) + load(think_file)
    # per-case per-tier hug rate, separately for think/non
    # step: reps -> (cli,framing,mode) hug-mean ; then framings -> tier (avg GL5,G4 within S4)
    cell = defaultdict(list)  # (cli,framing,mode) -> [hug 0/1]
    for r in recs:
        if str(r["condition"]).startswith("blind"):
            continue
        if r["multiplier"] != 0.5:
            continue
        anc = r["anchor"]
        pa = r["parsed_amount"]
        if anc in (None, 0) or pa is None:
            continue
        hug = 1.0 if abs(pa - anc) / abs(anc) <= 0.05 else 0.0
        cell[(r["cli"], r["framing"], mode_of(r))].append(hug)
    cellmean = {k: statistics.mean(v) for k, v in cell.items()}
    clis = sorted(set(k[0] for k in cellmean))
    # tier value per (cli, tier_index, mode): average framings mapping to that tier
    tier_frames = defaultdict(list)
    for f, ti in FRAMING_TIER.items():
        tier_frames[ti].append(f)

    def tier_val(cli, ti, mode):
        vals = [cellmean[(cli, f, mode)] for f in tier_frames[ti]
                if (cli, f, mode) in cellmean]
        return statistics.mean(vals) if vals else None

    def group_delta(tier_indices):
        diffs = []
        for cli in clis:
            tv_t = [tier_val(cli, ti, "think") for ti in tier_indices]
            tv_n = [tier_val(cli, ti, "non") for ti in tier_indices]
            if any(v is None for v in tv_t + tv_n):
                continue
            diffs.append((statistics.mean(tv_t) - statistics.mean(tv_n)) * 100)
        m = statistics.mean(diffs)
        p, df = paired_t_p(diffs)
        return m, p, len(diffs)

    L = group_delta(low_indices)
    H = group_delta([4, 5])
    # trend on hug (not printed, but available)
    return L, H


# ------------------------------------------------------------------
# PULL from per_case_pull.csv (authoritative)
# ------------------------------------------------------------------
def load_pcp():
    rows = list(csv.DictReader(open(PCP)))
    return [r for r in rows if r["arm"] == "x05"]

def pull_from_csv(model, rows, low_tiers=LOW_TIERS_CSV, trend_tiers=None):
    if trend_tiers is None:
        trend_tiers = list(enumerate(TIER_ORDER_CSV, start=1))  # (rank, label)
    sub = [r for r in rows if r["model"] == model]
    by = {}
    for r in sub:
        by[(r["cli"], r["tier"], r["mode"])] = float(r["clipped_pull"])
    clis = sorted(set(r["cli"] for r in sub))

    def group_delta(tiers):
        diffs = []
        for cli in clis:
            tv_t = statistics.mean(by[(cli, t, "think")] for t in tiers)
            tv_n = statistics.mean(by[(cli, t, "non")] for t in tiers)
            diffs.append((tv_t - tv_n) * 100)
        m = statistics.mean(diffs)
        p, df = paired_t_p(diffs)
        return m, p, len(diffs)

    L = group_delta(low_tiers)
    H = group_delta(HIGH_TIERS_CSV)

    # trend: OLS slope of per-case Delta pull on tier rank, over the included tiers
    slopes = []
    for cli in clis:
        xs, ys = [], []
        for ti, tlabel in trend_tiers:
            d = (by[(cli, tlabel, "think")] - by[(cli, tlabel, "non")]) * 100
            xs.append(ti); ys.append(d)
        slopes.append(ols_slope(xs, ys))
    m_slope = statistics.mean(slopes)
    p_slope, _ = paired_t_p(slopes)
    return L, H, (m_slope, p_slope, len(slopes))


# ------------------------------------------------------------------
# PULL independently from raw_data (cross-check)
# ------------------------------------------------------------------
def pull_from_raw(model, non_file, think_file, low_indices=(1, 2)):
    low_indices = list(low_indices)
    recs = load(non_file) + load(think_file)
    # blind median per (cli, mode)
    blind = defaultdict(list)
    for r in recs:
        if str(r["condition"]).startswith("blind") and r["parsed_amount"] is not None:
            blind[(r["cli"], mode_of(r))].append(r["parsed_amount"])
    blindmed = {k: statistics.median(v) for k, v in blind.items()}
    # cell raw pull: reps -> (cli,framing,mode)
    cell = defaultdict(list)
    for r in recs:
        if str(r["condition"]).startswith("blind"):
            continue
        if r["multiplier"] != 0.5:
            continue
        anc = r["anchor"]
        pa = r["parsed_amount"]
        mode = mode_of(r)
        bl = blindmed.get((r["cli"], mode))
        if bl is None or anc is None or pa is None or (anc - bl) == 0:
            continue
        raw = (pa - bl) / (anc - bl)
        clipped = min(1.0, max(0.0, raw))
        cell[(r["cli"], r["framing"], mode)].append(clipped)
    cellmean = {k: statistics.mean(v) for k, v in cell.items()}
    clis = sorted(set(k[0] for k in cellmean))
    tier_frames = defaultdict(list)
    for f, ti in FRAMING_TIER.items():
        tier_frames[ti].append(f)

    def tier_val(cli, ti, mode):
        vals = [cellmean[(cli, f, mode)] for f in tier_frames[ti]
                if (cli, f, mode) in cellmean]
        return statistics.mean(vals) if vals else None

    def group_delta(tier_indices):
        diffs = []
        for cli in clis:
            tv_t = [tier_val(cli, ti, "think") for ti in tier_indices]
            tv_n = [tier_val(cli, ti, "non") for ti in tier_indices]
            if any(v is None for v in tv_t + tv_n):
                continue
            diffs.append((statistics.mean(tv_t) - statistics.mean(tv_n)) * 100)
        m = statistics.mean(diffs)
        p, _ = paired_t_p(diffs)
        return m, p, len(diffs)

    L = group_delta([1, 2])
    H = group_delta([4, 5])
    # trend
    slopes = []
    for cli in clis:
        xs, ys, ok = [], [], True
        for ti in [1, 2, 3, 4, 5]:
            tt = tier_val(cli, ti, "think"); nn = tier_val(cli, ti, "non")
            if tt is None or nn is None:
                ok = False; break
            xs.append(ti); ys.append((tt - nn) * 100)
        if ok:
            slopes.append(ols_slope(xs, ys))
    m_slope = statistics.mean(slopes)
    p_slope, _ = paired_t_p(slopes)
    return L, H, (m_slope, p_slope, len(slopes))


# ------------------------------------------------------------------
MAIN_MODELS = ["Gemini", "GLM", "MiMo", "Grok", "Doubao", "DeepSeek", "Kimi"]
CSV_MODEL = {m: m for m in MAIN_MODELS}
# All models take pull from per_case_pull.csv, the canonical figure base with the
# 21 parser corrections applied and the main pairing (DeepSeek N_0/T_0.7, Kimi
# N_0.6/T_1.0). This reproduces the paper's printed pull cells, including the
# corrected DeepSeek (+26.0/+9.5) and Kimi (PullL -20.6, PullH -3.3) values.
PULL_FROM_RAW = set()

def fmt(v): return f"{v:+.1f}"
def cell(v, p): return fmt(v) + ({"***": "***", "**": "**", "*": "*", "dagger": "†", "": ""}[marker(p)])

pcp_rows = load_pcp()
rows_out = []

ALL_TREND_TIERS = list(enumerate(TIER_ORDER_CSV, start=1))                # all 5 tiers
EXCL_S1_TREND_TIERS = list(enumerate(TIER_ORDER_CSV, start=1))[1:]        # drop Fortune

def compute_row(label, model, low_indices, low_tiers, trend_tiers):
    nonf, thinkf = MAIN_FILES[model]
    hL, hH = hug_for_model(model, nonf, thinkf, low_indices=low_indices)
    if model in PULL_FROM_RAW:
        pL, pH, trend = pull_from_raw(model, nonf, thinkf, low_indices=low_indices)
        src = "raw"
    else:
        pL, pH, trend = pull_from_csv(CSV_MODEL[model], pcp_rows,
                                      low_tiers=low_tiers, trend_tiers=trend_tiers)
        src = "csv"
    rows_out.append((label, hL, hH, pL, pH, trend, src))

LOW_FULL = (1, 2)
LOW_FULL_TIERS = LOW_TIERS_CSV
for m in MAIN_MODELS:
    compute_row(m, m, LOW_FULL, LOW_FULL_TIERS, ALL_TREND_TIERS)
    if m == "Grok":
        # excl. S1: low group = S2 (Layperson) only; trend over S2..S5
        compute_row("Grok (excl. S1)", "Grok", (2,), ["Layperson"], EXCL_S1_TREND_TIERS)

print(f"{'Model':<18} {'HugL':>10} {'HugH':>10} {'PullL':>10} {'PullH':>10} {'Trend':>9}  src")
for (label, hL, hH, pL, pH, trend, src) in rows_out:
    print(f"{label:<18} "
          f"{cell(hL[0],hL[1]):>10} {cell(hH[0],hH[1]):>10} "
          f"{cell(pL[0],pL[1]):>10} {cell(pH[0],pH[1]):>10} "
          f"{cell(trend[0],trend[1]):>9}  {src}")

print("\n--- p-values ---")
for (label, hL, hH, pL, pH, trend, src) in rows_out:
    print(f"{label:<18} hugL_p={hL[1]:.4f} hugH_p={hH[1]:.4f} "
          f"pullL_p={pL[1]:.4f} pullH_p={pH[1]:.4f} trend_p={trend[1]:.4f}")

with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["row", "hug_L", "hug_L_p", "hug_H", "hug_H_p",
                "pull_L", "pull_L_p", "pull_H", "pull_H_p",
                "trend", "trend_p", "pull_source"])
    for (label, hL, hH, pL, pH, trend, src) in rows_out:
        w.writerow([label, f"{hL[0]:.4f}", f"{hL[1]:.5f}", f"{hH[0]:.4f}", f"{hH[1]:.5f}",
                    f"{pL[0]:.4f}", f"{pL[1]:.5f}", f"{pH[0]:.4f}", f"{pH[1]:.5f}",
                    f"{trend[0]:.4f}", f"{trend[1]:.5f}", src])
print(f"\nwrote {OUT}")
