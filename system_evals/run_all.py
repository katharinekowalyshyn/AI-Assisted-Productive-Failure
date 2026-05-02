"""
Run every evaluator and emit:
  results/metrics.json   -- machine-readable summary
  results/report.md      -- human-readable report for the final write-up
  results/dataset.csv    -- flat per-problem table for any further stats

Usage:
    python3 run_all.py
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import eval_consolidation_timing
import eval_jury_simulation
import eval_misconception_detection
import eval_pf_fidelity
import eval_struggle_index
from data_loader import load_attempt_rows, load_sessions

OUT_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR.mkdir(exist_ok=True)


def _serialise(obj):
    """Make any dataclass/object JSON-friendly."""
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(x) for x in obj]
    if hasattr(obj, "__dict__"):
        return _serialise(obj.__dict__)
    return obj


def _write_dataset_csv(sessions, rows, path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "session_id",
            "problem_index",
            "task_type",
            "difficulty",
            "n_attempts",
            "consolidated",
            "correct",
            "first_attempt",
            "last_attempt",
        ])
        for s in sessions:
            for p in s.problems:
                if not p.student_attempts and not p.consolidated:
                    continue
                w.writerow([
                    s.session_id,
                    p.problem_index,
                    p.task_type,
                    p.difficulty_score,
                    len(p.student_attempts),
                    p.consolidated,
                    p.correct,
                    p.student_attempts[0] if p.student_attempts else "",
                    p.student_attempts[-1] if p.student_attempts else "",
                ])


def main() -> None:
    sessions = load_sessions()
    rows = load_attempt_rows()

    fidelity = eval_pf_fidelity.evaluate(sessions)
    struggle = eval_struggle_index.evaluate(sessions, rows)
    consolidation = eval_consolidation_timing.evaluate(sessions)
    jury = eval_jury_simulation.evaluate(sessions)
    misconception = eval_misconception_detection.evaluate(sessions)

    # ------------------------------------------------------------------
    # Headline metrics
    # ------------------------------------------------------------------
    headline = {
        "n_sessions": len(sessions),
        "n_problems": struggle.get("n_problems", 0),
        "n_consolidations": consolidation.get("n_consolidations", 0),
        "pf_fidelity_overall_pass_rate": fidelity.rates.get("all_four_pass", 0),
        "pf_fidelity_no_answer_leak_rate": fidelity.rates.get("no_answer_leak", 0),
        "struggle_index_mean": struggle.get("struggle_index", {}).get("mean"),
        "productive_zone_share": struggle.get("bucket_distribution_pct", {}).get("productive"),
        "consolidation_rule_match_rate": consolidation.get("rule_match_rate"),
        "jury_unanimous_rate": jury.get("agreement", {}).get("unanimous_rate"),
        "jury_verdict_index_alignment": jury.get("verdict_vs_struggle_bucket_alignment"),
        "misconception_micro_f1": misconception.get("micro", {}).get("f1"),
        "misconception_macro_f1": misconception.get("macro_f1"),
    }

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline": headline,
        "pf_fidelity": eval_pf_fidelity.to_dict(fidelity),
        "struggle_index": struggle,
        "consolidation_timing": consolidation,
        "jury_simulation": jury,
        "misconception_detection": misconception,
    }

    (OUT_DIR / "metrics.json").write_text(json.dumps(_serialise(metrics), indent=2))
    _write_dataset_csv(sessions, rows, OUT_DIR / "dataset.csv")

    # ------------------------------------------------------------------
    # Markdown report
    # ------------------------------------------------------------------
    md = []
    md.append("# AI-Assisted Productive Failure — System Evaluation Report")
    md.append("")
    md.append(
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"from {len(sessions)} sessions / {struggle.get('n_problems', 0)} problems._"
    )
    md.append("")
    md.append("## Headline metrics")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|---|---:|")
    md.append(f"| Sessions evaluated | {headline['n_sessions']} |")
    md.append(f"| Problems evaluated | {headline['n_problems']} |")
    md.append(f"| Consolidations fired | {headline['n_consolidations']} |")
    md.append(
        f"| PF fidelity (all four rules) | "
        f"{headline['pf_fidelity_overall_pass_rate']:.1%} |"
    )
    md.append(
        f"| PF fidelity (no answer leak) | "
        f"{headline['pf_fidelity_no_answer_leak_rate']:.1%} |"
    )
    md.append(f"| Mean Struggle Index | {headline['struggle_index_mean']} |")
    md.append(
        f"| Productive-zone share | "
        f"{(headline['productive_zone_share'] or 0):.1%} |"
    )
    md.append(
        f"| Consolidation rule fidelity | "
        f"{(headline['consolidation_rule_match_rate'] or 0):.1%} |"
    )
    md.append(
        f"| Jury unanimous-vote rate | "
        f"{(headline['jury_unanimous_rate'] or 0):.1%} |"
    )
    md.append(
        f"| Verdict ⇄ Struggle Index alignment | "
        f"{(headline['jury_verdict_index_alignment'] or 0):.1%} |"
    )
    md.append(
        f"| Misconception detection micro-F1 | "
        f"{headline['misconception_micro_f1']} |"
    )
    md.append(
        f"| Misconception detection macro-F1 | "
        f"{headline['misconception_macro_f1']} |"
    )
    md.append("")

    md.append(eval_pf_fidelity.render_markdown(fidelity))
    md.append("")
    md.append(eval_struggle_index.render_markdown(struggle))
    md.append("")
    md.append(eval_consolidation_timing.render_markdown(consolidation))
    md.append("")
    md.append(eval_jury_simulation.render_markdown(jury))
    md.append("")
    md.append(eval_misconception_detection.render_markdown(misconception))
    md.append("")

    md.append("## Limitations & threats to validity")
    md.append("")
    md.append(
        "- **Sample size.** All metrics are computed over real session logs "
        "from a small set of pilot users; n is in the tens of problems, not hundreds."
    )
    md.append(
        "- **PF fidelity is rule-based.** A passing struggle-phase message "
        "satisfies the four PF system-prompt constraints but is not "
        "guaranteed to be pedagogically optimal; an LLM-judge pass would "
        "complement these rules."
    )
    md.append(
        "- **Struggle Index is derived, not logged.** The live system does "
        "not yet emit a numeric struggle index; we reconstruct it post-hoc "
        "from attempt counts, time deltas, and stuck-token signals."
    )
    md.append(
        "- **Jury simulation is offline.** The deliberation here applies "
        "deterministic policies that mirror each juror's documented stance; "
        "the real LLMs will introduce variance not captured here."
    )
    md.append(
        "- **Misconception silver labels** come from automated parsing of "
        "consolidation messages. They are noisy and biased toward errors the "
        "tutor explicitly named."
    )
    md.append("")

    (OUT_DIR / "report.md").write_text("\n".join(md))

    print(f"Wrote {OUT_DIR/'metrics.json'}")
    print(f"Wrote {OUT_DIR/'report.md'}")
    print(f"Wrote {OUT_DIR/'dataset.csv'}")


if __name__ == "__main__":
    main()
