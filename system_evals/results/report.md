# AI-Assisted Productive Failure — System Evaluation Report

_Generated 2026-05-02T14:27:13+00:00 from 11 sessions / 26 problems._

## Headline metrics

| Metric | Value |
|---|---:|
| Sessions evaluated | 11 |
| Problems evaluated | 26 |
| Consolidations fired | 6 |
| PF fidelity (all four rules) | 90.5% |
| PF fidelity (no answer leak) | 97.6% |
| Mean Struggle Index | 0.492 |
| Productive-zone share | 26.9% |
| Consolidation rule fidelity | 100.0% |
| Jury unanimous-vote rate | 19.0% |
| Verdict ⇄ Struggle Index alignment | 33.3% |
| Misconception detection micro-F1 | 0.522 |
| Misconception detection macro-F1 | 0.14 |

## PF Fidelity (rule-based)

Evaluated **42** struggle-phase tutor messages (excluded: 8 correctness templates, 7 consolidation openers).

| Criterion | Pass | Rate |
|---|---:|---:|
| No answer leak | 41/42 | 97.6% |
| Contains generative question | 42/42 | 100.0% |
| Brevity (≤ 3 sentences) | 40/42 | 95.2% |
| Motivational opener | 41/42 | 97.6% |
| **All four pass** | 38/42 | 90.5% |

Sample violations:
- *sess_1776263723268* problem 1 (translation) — violations: too_long
  > Great job with "quiero" and "ir"! You're on the right track. What do you think you need to say before "ir" to complete your thought? Remember, it starts with "a."
- *sess_1776263723268* problem 1 (translation) — violations: answer_leak
  > Great job using "quiero" and "parque"! Now, think about how you connect "quiero" to "ir." What do you remember about using "ir" after a verb like "quiero"?
- *sess_1777032626957* problem 8 (conversation_completion) — violations: too_long
  > Great effort with your response! I see you’re expressing a preference, which is a good start. What made you choose "spring" instead of the Spanish word for it? Try again!
- *sess_1777037803060* problem 2 (translation) — violations: not_motivational
  > It's completely okay to feel unsure; recognizing that is the first step! Can you think about what verb you might need to use for "wash" in this question? Give it another try!

## Struggle Index

Computed on **26** problems from `pf_learning_logs.csv`.

- Mean struggle index: **0.492**  (median 0.543, σ 0.263)
- Attempts/problem: mean 3.15, median 3.5, max 6
- Consolidation fired: **42.3%** of problems
- Correctly solved: **38.5%** of problems

### Productive zone occupancy
| Bucket | Range | Count | Share |
|---|---|---:|---:|
| Too easy | S < 0.25 | 8 | 30.8% |
| Productive | 0.25 ≤ S ≤ 0.65 | 7 | 26.9% |
| Too hard | S > 0.65 | 11 | 42.3% |

### Mean struggle index by difficulty
| Difficulty | Mean S |
|---:|---:|
| 0 | 0.512 |
| 1 | 0.414 |
| 2 | 0.45 |
| 3 | 0.735 |
| 4 | 0.198 |
| 5 | 0.658 |

### Mean struggle index by task type
| Task type | Mean S |
|---|---:|
| conversation_completion | 0.601 |
| error_correction | 0.317 |
| translation | 0.553 |
| unknown | 0.512 |

## Adaptive Consolidation Timing

Across **21** reconstructed problems, consolidation fired on **6** (28.6%).

- Rule-fidelity (consolidation iff ≥5 incorrect attempts): **100.0%**
- False positives (fired without meeting rule): 0
- False negatives (rule met but not fired): 0
- Of consolidated problems, 50.0% had ≥2 stuck signals (good timing).
- Of consolidated problems, 16.7% showed visible late progress (potentially premature).
- Latency to consolidation: mean 1.57 min (median 1.57, range 1.22–1.83).

## Jury Verdict Simulation (offline policy replay)

Replayed jury policy on **21** problems (no API calls — uses each juror's documented stance to predict its vote).

### Inter-juror agreement
| Outcome | Count | Share |
|---|---:|---:|
| Unanimous | 4 | 19.0% |
| 2-of-3 majority | 17 | 81.0% |
| 3-way split | 0 | 0.0% |

### Final verdict distribution
| Verdict | Count | Share |
|---|---:|---:|
| INCREASE | 3 | 14.3% |
| MAINTAIN | 12 | 57.1% |
| DECREASE | 6 | 28.6% |

### Per-juror lean
| Juror | INCREASE | MAINTAIN | DECREASE |
|---|---:|---:|---:|
| Melchior | 12 | 9 | 0 |
| Casper | 3 | 10 | 8 |
| Balthazar | 3 | 12 | 6 |

**Verdict ⇄ struggle-index alignment:** 33.3% of verdicts match the bucket implied by the derived Struggle Index.

## Misconception Detection

Heuristic detector evaluated against silver labels parsed from consolidation messages on **6** problems.

- Micro-averaged F1: **0.522** (P 0.545, R 0.5)
- Macro-averaged F1: **0.14**

| Tag | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| STUCK | 5 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| ENGLISH_INTRUSION | 0 | 3 | 0 | 0.0 | 0.0 | 0.0 |
| VOCABULARY | 1 | 2 | 1 | 0.333 | 0.5 | 0.4 |
| VERB_CONJUGATION | 0 | 0 | 0 | 0.0 | 0.0 | 0.0 |
| GENDER_AGREEMENT | 0 | 0 | 1 | 0.0 | 0.0 | 0.0 |
| SER_VS_ESTAR | 0 | 0 | 0 | 0.0 | 0.0 | 0.0 |
| PREPOSITION | 0 | 0 | 1 | 0.0 | 0.0 | 0.0 |
| REFLEXIVE | 0 | 0 | 1 | 0.0 | 0.0 | 0.0 |
| TENSE | 0 | 0 | 1 | 0.0 | 0.0 | 0.0 |
| SUBJUNCTIVE | 0 | 0 | 1 | 0.0 | 0.0 | 0.0 |

Target from system slide: **F1 ≥ 0.75**. Micro F1 ✗ misses, Macro F1 ✗ misses the bar.

## Limitations & threats to validity

- **Sample size.** All metrics are computed over real session logs from a small set of pilot users; n is in the tens of problems, not hundreds.
- **PF fidelity is rule-based.** A passing struggle-phase message satisfies the four PF system-prompt constraints but is not guaranteed to be pedagogically optimal; an LLM-judge pass would complement these rules.
- **Struggle Index is derived, not logged.** The live system does not yet emit a numeric struggle index; we reconstruct it post-hoc from attempt counts, time deltas, and stuck-token signals.
- **Jury simulation is offline.** The deliberation here applies deterministic policies that mirror each juror's documented stance; the real LLMs will introduce variance not captured here.
- **Misconception silver labels** come from automated parsing of consolidation messages. They are noisy and biased toward errors the tutor explicitly named.
