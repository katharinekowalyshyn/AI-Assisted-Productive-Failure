# AI-Assisted PF — System Evaluation (Synthetic Dataset)

_Generated 2026-05-02T14:36:53+00:00 on 100 synthetic sessions / 197 problems._

## Synthetic dataset summary

| Field | Value |
|---|---|
| Sessions | 100 |
| Problems | 197 |
| Seed | 42 |
| Profile mix | fast_finisher=15, novice_persistent=33, intermediate_steady=37, novice_stuck=9, struggler=6 |
| Synth correct rate | 0.761 |
| Synth consolidation rate | 0.198 |

## Headline metrics

| Metric | Value |
|---|---:|
| Sessions evaluated | 100 |
| Problems evaluated | 197 |
| Consolidations fired | 39 |
| PF fidelity (all four rules) | 100.0% |
| PF fidelity (no answer leak) | 100.0% |
| Mean Struggle Index | 0.586 |
| Productive-zone share | 45.2% |
| Consolidation rule fidelity | 100.0% |
| Jury unanimous-vote rate | 31.0% |
| Verdict ⇄ Struggle Index alignment | 83.2% |
| Misconception micro-F1 (gold) | 0.399 |
| Misconception macro-F1 (gold) | 0.282 |

## PF Fidelity (rule-based)

Evaluated **491** struggle-phase tutor messages (excluded: 145 correctness templates, 39 consolidation openers).

| Criterion | Pass | Rate |
|---|---:|---:|
| No answer leak | 491/491 | 100.0% |
| Contains generative question | 491/491 | 100.0% |
| Brevity (≤ 3 sentences) | 491/491 | 100.0% |
| Motivational opener | 491/491 | 100.0% |
| **All four pass** | 491/491 | 100.0% |

## Struggle Index

Computed on **197** problems from `pf_learning_logs.csv`.

- Mean struggle index: **0.586**  (median 0.612, σ 0.232)
- Attempts/problem: mean 3.43, median 4, max 5
- Consolidation fired: **19.3%** of problems
- Correctly solved: **73.6%** of problems

### Productive zone occupancy
| Bucket | Range | Count | Share |
|---|---|---:|---:|
| Too easy | S < 0.25 | 26 | 13.2% |
| Productive | 0.25 ≤ S ≤ 0.65 | 89 | 45.2% |
| Too hard | S > 0.65 | 82 | 41.6% |

### Mean struggle index by difficulty
| Difficulty | Mean S |
|---:|---:|
| 1 | 0.599 |
| 2 | 0.575 |
| 3 | 0.58 |
| 4 | 0.568 |
| 5 | 0.64 |

### Mean struggle index by task type
| Task type | Mean S |
|---|---:|
| conversation_completion | 0.535 |
| error_correction | 0.617 |
| translation | 0.595 |

## Adaptive Consolidation Timing

Across **197** reconstructed problems, consolidation fired on **39** (19.8%).

- Rule-fidelity (consolidation iff ≥5 incorrect attempts): **100.0%**
- False positives (fired without meeting rule): 0
- False negatives (rule met but not fired): 0
- Of consolidated problems, 56.4% had ≥2 stuck signals (good timing).
- Of consolidated problems, 25.6% showed visible late progress (potentially premature).
- Latency to consolidation: mean 4.02 min (median 3.91, range 2.81–6.1).

## Jury Verdict Simulation (offline policy replay)

Replayed jury policy on **197** problems (no API calls — uses each juror's documented stance to predict its vote).

### Inter-juror agreement
| Outcome | Count | Share |
|---|---:|---:|
| Unanimous | 61 | 31.0% |
| 2-of-3 majority | 125 | 63.5% |
| 3-way split | 11 | 5.6% |

### Final verdict distribution
| Verdict | Count | Share |
|---|---:|---:|
| INCREASE | 49 | 24.9% |
| MAINTAIN | 132 | 67.0% |
| DECREASE | 16 | 8.1% |

### Per-juror lean
| Juror | INCREASE | MAINTAIN | DECREASE |
|---|---:|---:|---:|
| Melchior | 96 | 101 | 0 |
| Casper | 38 | 70 | 89 |
| Balthazar | 38 | 143 | 16 |

**Verdict ⇄ struggle-index alignment:** 83.2% of verdicts match the bucket implied by the derived Struggle Index.

## Misconception Detection (synthetic, GOLD labels)

Heuristic detector evaluated against **gold-injected** labels on **197** synthetic problems. Unlike the real-data run, gold tags are exact (no parsing of consolidation text).

- Micro-averaged F1: **0.399** (P 0.591, R 0.301)
- Macro-averaged F1: **0.282**

Slide target F1 ≥ 0.75: micro ✗ misses, macro ✗ misses.

| Tag | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| STUCK | 40 | 26 | 0 | 0.606 | 1.0 | 0.755 |
| ENGLISH_INTRUSION | 4 | 0 | 17 | 1.0 | 0.19 | 0.32 |
| VOCABULARY | 2 | 14 | 5 | 0.125 | 0.286 | 0.174 |
| VERB_CONJUGATION | 0 | 0 | 45 | 0.0 | 0.0 | 0.0 |
| GENDER_AGREEMENT | 6 | 7 | 18 | 0.462 | 0.25 | 0.324 |
| SER_VS_ESTAR | 0 | 0 | 16 | 0.0 | 0.0 | 0.0 |
| PREPOSITION | 11 | 4 | 20 | 0.733 | 0.355 | 0.478 |
| REFLEXIVE | 4 | 1 | 25 | 0.8 | 0.138 | 0.235 |
| TENSE | 8 | 0 | 14 | 1.0 | 0.364 | 0.533 |
| SUBJUNCTIVE | 0 | 0 | 14 | 0.0 | 0.0 | 0.0 |

### Per student-profile micro-F1
| Profile | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| intermediate_steady | 75 | 0.571 | 0.211 | 0.308 |
| novice_persistent | 64 | 0.519 | 0.273 | 0.358 |
| fast_finisher | 30 | 0.0 | 0.0 | 0.0 |
| novice_stuck | 17 | 0.69 | 0.488 | 0.571 |
| struggler | 11 | 0.75 | 0.48 | 0.585 |

## Outcomes by synthetic student profile

| Profile | n | Mean attempts | Correct rate | Consolidation rate |
|---|---:|---:|---:|---:|
| intermediate_steady | 75 | 3.16 | 90.7% | 0.0% |
| novice_persistent | 64 | 4.05 | 71.9% | 28.1% |
| fast_finisher | 30 | 1.67 | 80.0% | 0.0% |
| novice_stuck | 17 | 4.53 | 29.4% | 70.6% |
| struggler | 11 | 4.73 | 18.2% | 81.8% |

## Synthetic-data caveats

- Tutor feedback in synthetic sessions is sampled from a fixed template bank; the PF-fidelity evaluator therefore measures the *templates*, not the live LLM, so the rate should be taken as a best-case ceiling.
- Student attempts are sampled with parameterised profiles. They are realistic in shape (counts, stuck signals, English drift) but do not capture the long-tail creativity of real learners.
- Gold misconception labels are exact by construction. Real-data labels (parsed from consolidation text) are noisier.
- Jury simulation is still offline policy replay — synthetic data does not exercise the actual LLM jurors.