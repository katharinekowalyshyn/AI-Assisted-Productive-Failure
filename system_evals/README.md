# `system_evals/`

Offline evaluation suite for the AI-Assisted Productive Failure tutoring system. Every script reads from `backend/sessions/sess_*.json` and `backend/pf_learning_logs.csv`, performs analysis with Python stdlib only (no API calls, no third-party dependencies), and writes results to `system_evals/results/`.

## What's evaluated

| File | What it measures | Key output |
|---|---|---|
| `eval_pf_fidelity.py` | Whether tutor messages obey the four PF system-prompt rules: no answer leak, generative question, brevity, motivational opener | Per-criterion pass rate + overall fidelity |
| `eval_struggle_index.py` | A derived continuous Struggle Index per problem, plus distribution across the jury's "too easy / productive / too hard" buckets | Mean struggle index, productive-zone share |
| `eval_consolidation_timing.py` | How faithfully consolidation fires per the `attempts ≥ MAX_ATTEMPTS` rule and how often timing matches student stuck-signals | Rule-fidelity, false positives/negatives, latency |
| `eval_jury_simulation.py` | Offline replay of each juror's documented stance (Melchior / Casper / Balthazar) on real attempt sequences | Agreement rate, verdict distribution, alignment with Struggle Index buckets |
| `eval_misconception_detection.py` | A heuristic detector benchmarked against silver labels parsed from consolidation messages | Per-tag P/R/F1, micro & macro F1 |
| `run_all.py` | Runs everything and emits the aggregate report | `results/report.md`, `results/metrics.json`, `results/dataset.csv` |

## How to run

```bash
cd system_evals
python3 run_all.py
```

Outputs land in `system_evals/results/`:

- **`report.md`** — drop-in markdown for the final write-up
- **`metrics.json`** — structured metrics for any downstream plotting / tables
- **`dataset.csv`** — flat per-problem table (session, task type, attempts, correct, consolidated, first/last attempt) for ad-hoc analysis

You can also run any single evaluator standalone, e.g.:

```bash
python3 eval_pf_fidelity.py
python3 eval_misconception_detection.py
```

Each prints its own markdown section to stdout.

## Data flow

```
backend/sessions/sess_*.json ─┐
                              ├─► data_loader.py ──► five evaluators ──► run_all.py ──► results/
backend/pf_learning_logs.csv ─┘
```

`data_loader.py` reconstructs a per-problem view from the conversation log (each `problem_start` event opens a problem; `next_problem`, `consolidation`, or end-of-log closes it) and joins it with the per-attempt CSV rows for time data.

## Caveats baked into the report

- All evaluators are offline and deterministic — no LLM-judge stage. PF-fidelity rules are a proxy for the true pedagogical signal.
- The Struggle Index is **not** logged by the live system; it is reconstructed post-hoc from attempt counts, time deltas, and stuck-token rates.
- Misconception silver labels are parsed from consolidation text, which is itself LLM-generated. They are noisy and biased toward errors the tutor explicitly verbalised.
- Sample sizes are pilot-scale (tens of problems). Treat all rates as point estimates with wide confidence intervals.

## Re-running after new sessions

Just run `python3 run_all.py` again — the loader picks up any new `sess_*.json` files and any new rows in `pf_learning_logs.csv` automatically.

---

## Synthetic dataset (`synth/`)

Real session logs are pilot-scale (11 sessions / 26 problems), so we also ship a synthetic generator that produces a 100-session benchmark with **gold-standard misconception labels** for fair F1 evaluation.

```
synth/
├── generate_sessions.py   # CLI generator
├── problem_bank.py        # ~18 Spanish A1–A2 problems with per-error templates
├── profiles.py            # 5 student profiles + sampling mixture
├── sessions/              # generated sess_synth_*.json (real schema)
├── gold_labels.json       # per-problem ground truth tags
└── manifest.json          # population summary
```

### Student profiles

| Profile | Behaviour |
|---|---|
| `fast_finisher` | Solves on attempt 1–2, rarely struggles |
| `intermediate_steady` | 2–4 attempts, mostly converges |
| `novice_persistent` | 3–5 attempts, gradual progress, some stuck signals |
| `novice_stuck` | 5 attempts, frequent "I don't know", low correctness |
| `struggler` | 5 attempts, ~50% stuck, English drift, almost always consolidates |

Mixture weights: 15 / 35 / 25 / 15 / 10 (matches the population_distribution in `profiles.py`).

### Generate + evaluate

```bash
cd system_evals
python3 synth/generate_sessions.py --n 100 --seed 42
python3 run_synth.py
```

Outputs:

- `results/synth_report.md` — full report with per-profile breakdowns
- `results/synth_metrics.json` — machine-readable metrics
- `synth/manifest.json` — generator config + population stats
- `synth/gold_labels.json` — ground-truth misconception tags

Re-running `generate_sessions.py` with the same seed reproduces the dataset bit-for-bit.

### What the synthetic run unlocks

- **Gold labels** for misconception F1 (no consolidation parsing needed).
- **Per-profile breakdowns** showing how the system handles different learner types.
- **Larger sample** — verdict alignment, fidelity, and timing metrics are far more stable on n=197 problems than on n=26.
- **Reproducibility** — same seed ⇒ identical dataset for the report's tables.
