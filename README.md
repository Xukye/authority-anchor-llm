# Reproduction Database — Authority-Rationalized Anchoring in LLM Legal Judgment

Data, code, prompts, and figures that reproduce every table and figure in the paper
*"When the Thinking Mode Strengthens the Anchor: Authority-Rationalized Anchoring in LLM Legal Judgment."*

One sentence: toggling a model's thinking mode on/off, the adoption of an authority-tagged numerical anchor in a Chinese personal-injury damages task changes **monotonically with the source's credibility** — three vendors' models **cross zero** (thinking debiases a fortune-teller anchor but amplifies a chief-judge anchor).

## Layout

| Path | What |
|---|---|
| `case_index.csv` | All **1,412** downloaded Beida Fabao (北大法宝) cases: `cli` (index handle), `judgment_date` (the newest-first selection key), `set` (`30` = canonical, `70` = high-end extension, blank = not used), `char_count` (desensitized 诉请+查明), `download_batch`. |
| `raw_data/` | Raw model-call records; the 21 parser corrections are already applied to `parsed_amount`. |
| `raw_data/main_axis_30/` | The 30 canonical cases — one JSON per **model × arm × temperature** (`<Model>_<N\|T>_<temp>.json`; N = non-thinking, T = thinking). Temperature roadmap in `main_axis_30/README.md` (paper Table 8). |
| `raw_data/supplements/` | The high-end **n = 100** extension, per crossing pole (`<Model>_<S1\|S5>.json`). |
| `raw_data/manipulation_check/` | Credibility self-rating responses, Gemini/GLM/MiMo (Supplementary Table S3). |
| `raw_data/wording_probe/` | Chief-judge paraphrase robustness probe (G5a/G5b), Gemini/GLM/MiMo (§5.4 wording-robustness check). |
| `raw_data/grok_demand_characteristic.json` | Grok-4.3 demand-characteristic boundary check (buy-fruit placebo + person×method probe), backing §6.3 / Table 13 / §S7. |
| `raw_data/parse_corrections.jsonl` | The 21 parser corrections (baked into `parsed_amount`). |
| `tables/` | Computed CSVs behind every paper table and figure. `per_case_pull.csv` is the authoritative per-case pull (the figure base). `prose_numbers.json` catalogs the standalone numeric claims in the running text. |
| `code/` | Python that recomputes each table/figure from `raw_data/` and `tables/per_case_pull.csv` (numpy + scipy only). |
| `figures/` | Paper figures — SVG sources plus the assembled PDFs the manuscript renders. |
| `Prompt/` | The 100 desensitized case texts (`cases_n30.json`, `cases_n70.json`) and the experiment prompt designs (Markdown). |
| `traces/` | Verbatim reasoning excerpts for the two worked cases (back the trace tables). |

The compiled manuscript is not deposited here; this repository hosts the data, code, prompts, and figures needed to reproduce every numerical claim in the paper.

## Metrics (paper §3.5)

- **pull** `= clip((output − blind) / (anchor − blind), 0, 1)`, scored against the **mode-matched** blind baseline (thinking vs thinking-blind, non-thinking vs non-thinking-blind).
- **adoption** `a = mean(clipped pull) × 100`; **Δpull** `= a_think − a_non` (paired per case).
- **c** (normalized change) `= Δ / (1 − a_non)` if Δ ≥ 0 else `Δ / a_non`.
- **anchor-hug** `= 1` if `|output − anchor| / |anchor| ≤ 0.05`.
- Tiers: S1 fortune teller (GN), S2 layperson (G1), S3 law student (E1), S4 expert (mean of GL5 lawyer & G4 professor), S5 chief judge (G5). Low = {S1,S2}, High = {S4,S5}. Main arm = ×0.5.

## Reproduce

```bash
cd code
python3 compute_main_axis.py      # tables/main_axis_points.csv  (triptych: hug / pull / c per model × tier × arm)
python3 compute_heatmap.py        # tables/heatmap_bins.csv      (per-case raw-pull histogram)
python3 compute_significance.py   # tables/significance_poles.csv (Table 9, crossing endpoints)
# recompute_<table>.py regenerates each individual paper table and compares to the manuscript.
```

All numbers derive from `raw_data/` (corrections applied). The deposited corpus is desensitized and omits full provider reasoning traces; each case keeps its `CLI.C.…` index as a credentialed verification handle only.
