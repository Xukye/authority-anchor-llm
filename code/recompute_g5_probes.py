"""recompute_g5_probes.py — chief-judge probe robustness (§5.4 + RR-2).

Reads raw call records for the 3 crossing models on the ×0.5 main arm at the
chief-judge tier (S5/G5) under four framings:

  G5  : main-arm framing (从 raw_data/main_axis_30/<Model>_<N|T>_<temp>.json)
  G5a : credibility-matched paraphrase #1 (从 raw_data/wording_probe/<Model>.json)
  G5b : credibility-matched paraphrase #2 (同上)
  G5S : information-stripped variant — same 4 authority features but with two
        explicit locks on case-external information:
          "仅凭庭审信息" (only the hearing's exhibited materials) and
          "前来交流的任外省法院民庭庭长" (visiting out-of-province chief judge),
        which together cut access to (a) case-external材料 and
        (b) jurisdiction-specific latent priors. From raw_data/authority_strip/<Model>.jsonl.

For each cell, blind median (from main_axis_30, mode-matched) is used as the
denominator for the standard clipped pull metric (§3.5):

  pull = clip( (output - blind) / (anchor - blind), 0, 1 )

Adoption a = mean(clipped pull) × 100; Δa = a_think - a_non, paired per case.

The hug metric is mode-independent — a case is anchor-hugged when
|output - anchor| / |anchor| ≤ 0.05. Per-case Δhug = think_hug - non_hug
(∈ {−1, 0, +1}); we report the per-model mean of this difference (pp), the
paired t / two-tailed p, and the aggregate hug counts.

Output: tables/g5_probes.csv (one row per model × framing).

The framing keys, prompt sentences, and per-call audit fields are documented in
Prompt/01_credibility_framings.md and Prompt/02_chief_judge_paraphrases.md;
G5S is described in Prompt/03_authority_strip.md (if present) and inline in the
recomputed table's tabnote.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
TABLES = ROOT / "tables"

MODELS = ["Gemini", "MiMo", "GLM"]
FRAMINGS = ["G5", "G5a", "G5b", "G5S"]
HUG_THRESH = 0.05  # ±5% of anchor (§3.5)


# ----------------------------------------------------------------------
# Robust readers (the deposit's main_axis_30 stores JSON arrays;
# wording_probe stores JSON arrays; authority_strip stores JSONL).
# ----------------------------------------------------------------------
def _load_json(p: Path):
    with p.open() as f:
        d = json.load(f)
    return d if isinstance(d, list) else d.get("records", d)


def _load_jsonl(p: Path):
    with p.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _mode_of(rec) -> str:
    cond = re.sub(r"#r\d+$", "", str(rec.get("condition", "")))
    return "think" if cond.endswith("_T") or rec.get("thinking") is True else "non"


def _collect_framing(records, framing: str, multiplier: float = 0.5):
    """Group records by (cli, mode) → mean parsed_amount; carry anchor."""
    buckets: dict = defaultdict(list)
    anchors: dict = {}
    for r in records:
        if r.get("framing") != framing:
            continue
        try:
            mult = float(r.get("multiplier", -1))
        except (TypeError, ValueError):
            continue
        if mult != multiplier:
            continue
        amt = r.get("parsed_amount")
        if amt is None or r.get("error"):
            continue
        cli = r.get("cli")
        if cli is None:
            continue
        buckets[(cli, _mode_of(r))].append(amt)
        anchors[cli] = r.get("anchor")
    return {k: st.mean(v) for k, v in buckets.items()}, anchors


def _blind_medians(model: str) -> dict[str, dict[str, float]]:
    """Mode-matched blind output median per (cli, mode), from main_axis_30."""
    out: dict = defaultdict(lambda: defaultdict(list))
    for fn in sorted((RAW / "main_axis_30").iterdir()):
        if not (fn.name.startswith(f"{model}_") and fn.suffix == ".json"):
            continue
        for r in _load_json(fn):
            cond = re.sub(r"#r\d+$", "", str(r.get("condition", "")))
            if not cond.startswith("blind"):
                continue
            amt = r.get("parsed_amount")
            if amt is None:
                continue
            out[_mode_of(r)][r["cli"]].append(amt)
    return {m: {c: st.median(v) for c, v in d.items()} for m, d in out.items()}


# ----------------------------------------------------------------------
# Source-specific record loaders.
# ----------------------------------------------------------------------
def _records_main(model: str):
    recs: list = []
    for fn in sorted((RAW / "main_axis_30").iterdir()):
        if fn.name.startswith(f"{model}_") and fn.suffix == ".json":
            recs.extend(_load_json(fn))
    return recs


def _records_wording_probe(model: str):
    p = RAW / "wording_probe" / f"{model}.json"
    return _load_json(p) if p.exists() else []


def _records_authority_strip(model: str):
    p = RAW / "authority_strip" / f"{model}.jsonl"
    return _load_jsonl(p) if p.exists() else []


# ----------------------------------------------------------------------
# Stats.
# ----------------------------------------------------------------------
def _clipped_pull(output: float, blind: float | None, anchor: float | None) -> float | None:
    if output is None or blind is None or anchor is None or blind == anchor:
        return None
    return max(0.0, min(1.0, (output - blind) / (anchor - blind)))


def _t_p_two_sided(t: float, df: int) -> float:
    """Two-sided p, scipy if present; normal-approx fallback (df=29 is fine)."""
    if df <= 0 or not math.isfinite(t):
        return float("nan")
    try:
        from scipy.stats import t as student_t  # type: ignore

        return float(2 * (1 - student_t.cdf(abs(t), df)))
    except ImportError:
        return float(2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2)))))


def _stats(amts, anchors, blinds):
    """Return per-model summary for one framing."""
    rows = []
    for (cli, mode), out in amts.items():
        a = anchors.get(cli)
        b = blinds.get(mode, {}).get(cli)
        p = _clipped_pull(out, b, a)
        h = (abs(out - a) / abs(a) <= HUG_THRESH) if (a is not None and a != 0) else None
        rows.append((cli, mode, out, a, p, h))

    by_cli: dict = defaultdict(dict)
    for cli, mode, out, a, p, h in rows:
        by_cli[cli][mode] = (out, a, p, h)

    pulls_n, pulls_t = [], []
    hug_n_count = hug_t_count = 0
    delta_hug = []  # 1 / 0 / -1 per case
    n_paired = 0
    for cli, modes in by_cli.items():
        if "non" not in modes or "think" not in modes:
            continue
        _, _, pn, hn = modes["non"]
        _, _, pt, ht = modes["think"]
        if pn is None or pt is None or hn is None or ht is None:
            continue
        n_paired += 1
        pulls_n.append(pn)
        pulls_t.append(pt)
        if hn:
            hug_n_count += 1
        if ht:
            hug_t_count += 1
        delta_hug.append(int(ht) - int(hn))

    if n_paired == 0:
        return None

    a_non = st.mean(pulls_n) * 100
    a_think = st.mean(pulls_t) * 100
    delta_pull = [pt - pn for pn, pt in zip(pulls_n, pulls_t)]
    da_pp = st.mean(delta_pull) * 100
    if n_paired > 1:
        se_pull = st.stdev(delta_pull) / math.sqrt(n_paired) * 100
        t_pull = da_pp / se_pull if se_pull > 0 else float("nan")
        p_pull = _t_p_two_sided(t_pull, n_paired - 1)
        dh_mean_pp = st.mean(delta_hug) * 100
        se_hug = st.stdev(delta_hug) / math.sqrt(n_paired) * 100
        t_hug = dh_mean_pp / se_hug if se_hug > 0 else float("nan")
        p_hug = _t_p_two_sided(t_hug, n_paired - 1)
    else:
        t_pull = p_pull = t_hug = p_hug = float("nan")
        dh_mean_pp = float(delta_hug[0]) * 100 if delta_hug else float("nan")

    return {
        "n_paired": n_paired,
        "a_non": a_non,
        "a_think": a_think,
        "delta_a_pp": da_pp,
        "t_pull": t_pull,
        "p_pull": p_pull,
        "hug_n_count": hug_n_count,
        "hug_t_count": hug_t_count,
        "delta_hug_cases": hug_t_count - hug_n_count,
        "delta_hug_mean_pp": dh_mean_pp,
        "t_hug": t_hug,
        "p_hug": p_hug,
    }


# ----------------------------------------------------------------------
# Main.
# ----------------------------------------------------------------------
def main() -> None:
    TABLES.mkdir(exist_ok=True)
    rows = []
    for model in MODELS:
        main_recs = _records_main(model)
        wp_recs = _records_wording_probe(model)
        as_recs = _records_authority_strip(model)
        blinds = _blind_medians(model)
        framing_sources = {"G5": main_recs, "G5a": wp_recs, "G5b": wp_recs, "G5S": as_recs}
        for fr in FRAMINGS:
            amts, anchors = _collect_framing(framing_sources[fr], fr)
            res = _stats(amts, anchors, blinds)
            if res is None:
                continue
            rows.append(
                {
                    "model": model,
                    "framing": fr,
                    "n_paired": res["n_paired"],
                    "a_non": round(res["a_non"], 1),
                    "a_think": round(res["a_think"], 1),
                    "delta_a_pp": round(res["delta_a_pp"], 1),
                    "t_pull": round(res["t_pull"], 3),
                    "p_pull": round(res["p_pull"], 5),
                    "hug_n_count": res["hug_n_count"],
                    "hug_t_count": res["hug_t_count"],
                    "delta_hug_cases": res["delta_hug_cases"],
                    "delta_hug_mean_pp": round(res["delta_hug_mean_pp"], 1),
                    "t_hug": round(res["t_hug"], 3),
                    "p_hug": round(res["p_hug"], 5),
                }
            )

    fields = list(rows[0].keys())
    out = TABLES / "g5_probes.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # Stdout summary, format matches deposit's other recompute_*.py scripts.
    print(f"\nwrote {out} ({len(rows)} rows)\n")
    hdr = f"{'Model':<8}{'Framing':<6}{'n':>4}  | {'a_non':>7}{'a_think':>9}{'Δa':>8}{'p_pull':>10}  | "
    hdr += f"{'hugN':>6}{'hugT':>6}{'Δhug_cases':>12}{'Δhug_pp':>10}{'p_hug':>10}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(
            f"{r['model']:<8}{r['framing']:<6}{r['n_paired']:>4}  | "
            f"{r['a_non']:>+7.1f}{r['a_think']:>+9.1f}{r['delta_a_pp']:>+8.1f}{r['p_pull']:>10.5f}  | "
            f"{r['hug_n_count']:>4}/{r['n_paired']:<2}{r['hug_t_count']:>4}/{r['n_paired']:<2}"
            f"{r['delta_hug_cases']:>+12d}{r['delta_hug_mean_pp']:>+10.1f}{r['p_hug']:>10.5f}"
        )


if __name__ == "__main__":
    main()
