"""
Run all evaluators against the synthetic dataset in `synth/sessions/`.

Differences from `run_all.py`:
  - Loads sessions from `synth/sessions/` instead of `backend/sessions/`.
  - Skips the CSV-based per-attempt time/struggle metric (no synthetic CSV
    is emitted) and instead derives attempt deltas from event timestamps.
  - Replaces the silver labels in the misconception evaluator with the
    GOLD labels saved alongside the synthetic data.
  - Writes results to `results/synth_report.md` and `results/synth_metrics.json`.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import eval_consolidation_timing
import eval_jury_simulation
import eval_misconception_detection as mceval
import eval_pf_fidelity
import eval_struggle_index
from data_loader import Session, load_sessions
from data_loader import AttemptRow

HERE = Path(__file__).resolve().parent
SYNTH_SESSIONS = HERE / "synth" / "sessions"
GOLD_PATH = HERE / "synth" / "gold_labels.json"
MANIFEST_PATH = HERE / "synth" / "manifest.json"
OUT_DIR = HERE / "results"
OUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Build pseudo CSV rows from session timestamps
# ---------------------------------------------------------------------------

def _attempt_rows_from_sessions(sessions: list[Session]) -> list[AttemptRow]:
    rows: list[AttemptRow] = []
    for sess in sessions:
        for p in sess.problems:
            attempt_events = [e for e in p.events if e.event_type == "attempt"]
            if not attempt_events:
                continue
            start_ts = next(
                (e.timestamp for e in p.events if e.event_type == "problem_start"),
                attempt_events[0].timestamp,
            )
            try:
                t0 = datetime.fromisoformat(start_ts)
            except ValueError:
                continue
            problem_id = f"{sess.session_id}_p{p.problem_index}"
            for n, ev in enumerate(attempt_events, start=1):
                try:
                    t = datetime.fromisoformat(ev.timestamp)
                except ValueError:
                    continue
                rows.append(
                    AttemptRow(
                        timestamp=ev.timestamp,
                        session_id=sess.session_id,
                        problem_id=problem_id,
                        attempt_number=n,
                        time_spent_sec=(t - t0).total_seconds(),
                        hint_level_used=0,
                        misconception_tags=[],
                        final_correct=p.correct,
                        reflection_score=0,
                    )
                )
    return rows


# ---------------------------------------------------------------------------
# Gold-label override for misconception evaluator
# ---------------------------------------------------------------------------

def _evaluate_misconceptions_with_gold(
    sessions: list[Session], gold_records: list[dict]
) -> dict:
    """Same scoring code as the real eval, but using injected gold labels."""
    # Build a lookup from (session_id, problem_index) -> gold tags
    gold_index: dict[tuple[str, int], set[str]] = {}
    profile_for: dict[tuple[str, int], str] = {}
    for g in gold_records:
        key = (g["session_id"], g["problem_index"])
        gold_index[key] = set(g["gold_misconceptions"])
        profile_for[key] = g.get("profile", "unknown")

    pairs: list[tuple[set[str], set[str], dict]] = []
    by_profile: dict[str, list[tuple[set[str], set[str]]]] = defaultdict(list)

    for sess in sessions:
        for p in sess.problems:
            key = (sess.session_id, p.problem_index)
            gold = gold_index.get(key)
            if gold is None:
                continue
            pred = mceval.predict_for_problem(p)
            pairs.append((gold, pred, {
                "session_id": sess.session_id,
                "problem_index": p.problem_index,
                "task_type": p.task_type,
                "attempts": p.student_attempts,
                "gold": sorted(gold),
                "pred": sorted(pred),
            }))
            by_profile[profile_for[key]].append((gold, pred))

    if not pairs:
        return {"n": 0}

    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for gold, pred, _meta in pairs:
        for tag in mceval.TAGS:
            in_gold = tag in gold
            in_pred = tag in pred
            if in_gold and in_pred:
                counts[tag]["tp"] += 1
            elif in_pred and not in_gold:
                counts[tag]["fp"] += 1
            elif in_gold and not in_pred:
                counts[tag]["fn"] += 1

    per_tag = []
    for tag in mceval.TAGS:
        c = counts[tag]
        p, r, f = mceval._prf(c["tp"], c["fp"], c["fn"])
        per_tag.append({
            "tag": tag, "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
            "precision": p, "recall": r, "f1": f,
        })

    micro_tp = sum(c["tp"] for c in counts.values())
    micro_fp = sum(c["fp"] for c in counts.values())
    micro_fn = sum(c["fn"] for c in counts.values())
    micro_p, micro_r, micro_f = mceval._prf(micro_tp, micro_fp, micro_fn)
    macro_f = round(sum(t["f1"] for t in per_tag) / len(per_tag), 3) if per_tag else 0.0

    # Per-profile micro-F1.
    profile_breakdown: dict[str, dict] = {}
    for prof, items in by_profile.items():
        c2 = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
        for gold, pred in items:
            for tag in mceval.TAGS:
                in_gold = tag in gold
                in_pred = tag in pred
                if in_gold and in_pred:
                    c2[tag]["tp"] += 1
                elif in_pred and not in_gold:
                    c2[tag]["fp"] += 1
                elif in_gold and not in_pred:
                    c2[tag]["fn"] += 1
        tp = sum(v["tp"] for v in c2.values())
        fp = sum(v["fp"] for v in c2.values())
        fn = sum(v["fn"] for v in c2.values())
        pp, rr, ff = mceval._prf(tp, fp, fn)
        profile_breakdown[prof] = {
            "n": len(items),
            "precision": pp,
            "recall": rr,
            "f1": ff,
        }

    return {
        "n": len(pairs),
        "tags": per_tag,
        "micro": {"precision": micro_p, "recall": micro_r, "f1": micro_f},
        "macro_f1": macro_f,
        "by_profile": profile_breakdown,
        "examples": [m for _g, _p, m in pairs[:10]],
    }


def _render_misconception_md(result: dict) -> str:
    if not result.get("n"):
        return "## Misconception Detection (synthetic, GOLD labels)\n\n_No data._"
    lines = ["## Misconception Detection (synthetic, GOLD labels)", ""]
    lines.append(
        f"Heuristic detector evaluated against **gold-injected** labels on "
        f"**{result['n']}** synthetic problems. Unlike the real-data run, "
        f"gold tags are exact (no parsing of consolidation text)."
    )
    lines.append("")
    lines.append(
        f"- Micro-averaged F1: **{result['micro']['f1']}** "
        f"(P {result['micro']['precision']}, R {result['micro']['recall']})"
    )
    lines.append(f"- Macro-averaged F1: **{result['macro_f1']}**")
    target = 0.75
    micro_meets = result["micro"]["f1"] >= target
    macro_meets = result["macro_f1"] >= target
    lines.append("")
    lines.append(
        f"Slide target F1 ≥ 0.75: micro {'✓ meets' if micro_meets else '✗ misses'}, "
        f"macro {'✓ meets' if macro_meets else '✗ misses'}."
    )
    lines.append("")
    lines.append("| Tag | TP | FP | FN | Precision | Recall | F1 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for t in result["tags"]:
        lines.append(
            f"| {t['tag']} | {t['tp']} | {t['fp']} | {t['fn']} | "
            f"{t['precision']} | {t['recall']} | {t['f1']} |"
        )
    if result.get("by_profile"):
        lines.append("")
        lines.append("### Per student-profile micro-F1")
        lines.append("| Profile | n | Precision | Recall | F1 |")
        lines.append("|---|---:|---:|---:|---:|")
        for prof, d in sorted(result["by_profile"].items(), key=lambda kv: -kv[1]["n"]):
            lines.append(
                f"| {prof} | {d['n']} | {d['precision']} | {d['recall']} | {d['f1']} |"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-profile cross-cut for jury + struggle index
# ---------------------------------------------------------------------------

def _profile_breakdown(
    sessions: list[Session], gold_records: list[dict]
) -> dict:
    profile_for: dict[tuple[str, int], str] = {
        (g["session_id"], g["problem_index"]): g["profile"] for g in gold_records
    }
    bucket: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "consolidations": 0, "correct": 0, "attempts": []}
    )
    for sess in sessions:
        for p in sess.problems:
            key = (sess.session_id, p.problem_index)
            prof = profile_for.get(key, "unknown")
            d = bucket[prof]
            d["n"] += 1
            d["consolidations"] += int(p.consolidated)
            d["correct"] += int(p.correct)
            d["attempts"].append(len(p.student_attempts))

    out = {}
    for prof, d in bucket.items():
        attempts = d["attempts"] or [0]
        out[prof] = {
            "n": d["n"],
            "consolidation_rate": round(d["consolidations"] / d["n"], 3) if d["n"] else 0,
            "correct_rate": round(d["correct"] / d["n"], 3) if d["n"] else 0,
            "mean_attempts": round(statistics.mean(attempts), 2),
            "max_attempts": max(attempts),
        }
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not SYNTH_SESSIONS.exists() or not any(SYNTH_SESSIONS.glob("sess_synth_*.json")):
        print("No synthetic sessions found. Run `python3 synth/generate_sessions.py` first.")
        return

    sessions = load_sessions(SYNTH_SESSIONS)
    rows = _attempt_rows_from_sessions(sessions)
    gold_records = json.loads(GOLD_PATH.read_text()) if GOLD_PATH.exists() else []
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}

    fidelity = eval_pf_fidelity.evaluate(sessions)
    struggle = eval_struggle_index.evaluate(sessions, rows)
    consolidation = eval_consolidation_timing.evaluate(sessions)
    jury = eval_jury_simulation.evaluate(sessions)
    misconception = _evaluate_misconceptions_with_gold(sessions, gold_records)
    by_profile = _profile_breakdown(sessions, gold_records)

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
        "manifest": manifest,
        "headline": headline,
        "pf_fidelity": eval_pf_fidelity.to_dict(fidelity),
        "struggle_index": struggle,
        "consolidation_timing": consolidation,
        "jury_simulation": jury,
        "misconception_detection": misconception,
        "per_profile": by_profile,
    }

    (OUT_DIR / "synth_metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    md: list[str] = []
    md.append("# AI-Assisted PF — System Evaluation (Synthetic Dataset)")
    md.append("")
    md.append(
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"on {len(sessions)} synthetic sessions / {struggle.get('n_problems',0)} problems._"
    )
    md.append("")
    md.append("## Synthetic dataset summary")
    md.append("")
    if manifest:
        pd = manifest.get("profile_distribution", {})
        md.append("| Field | Value |")
        md.append("|---|---|")
        md.append(f"| Sessions | {manifest.get('n_sessions')} |")
        md.append(f"| Problems | {manifest.get('n_problems')} |")
        md.append(f"| Seed | {manifest.get('seed')} |")
        md.append(
            f"| Profile mix | "
            + ", ".join(f"{k}={v}" for k, v in pd.items())
            + " |"
        )
        md.append(f"| Synth correct rate | {manifest.get('correct_rate')} |")
        md.append(f"| Synth consolidation rate | {manifest.get('consolidation_rate')} |")
    md.append("")
    md.append("## Headline metrics")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|---|---:|")
    for label, key in [
        ("Sessions evaluated", "n_sessions"),
        ("Problems evaluated", "n_problems"),
        ("Consolidations fired", "n_consolidations"),
        ("PF fidelity (all four rules)", "pf_fidelity_overall_pass_rate"),
        ("PF fidelity (no answer leak)", "pf_fidelity_no_answer_leak_rate"),
        ("Mean Struggle Index", "struggle_index_mean"),
        ("Productive-zone share", "productive_zone_share"),
        ("Consolidation rule fidelity", "consolidation_rule_match_rate"),
        ("Jury unanimous-vote rate", "jury_unanimous_rate"),
        ("Verdict ⇄ Struggle Index alignment", "jury_verdict_index_alignment"),
        ("Misconception micro-F1 (gold)", "misconception_micro_f1"),
        ("Misconception macro-F1 (gold)", "misconception_macro_f1"),
    ]:
        v = headline.get(key)
        if isinstance(v, float) and 0 <= v <= 1 and key.endswith(("rate", "share", "alignment")):
            md.append(f"| {label} | {v:.1%} |")
        else:
            md.append(f"| {label} | {v} |")
    md.append("")

    md.append(eval_pf_fidelity.render_markdown(fidelity))
    md.append("")
    md.append(eval_struggle_index.render_markdown(struggle))
    md.append("")
    md.append(eval_consolidation_timing.render_markdown(consolidation))
    md.append("")
    md.append(eval_jury_simulation.render_markdown(jury))
    md.append("")
    md.append(_render_misconception_md(misconception))
    md.append("")

    if by_profile:
        md.append("## Outcomes by synthetic student profile")
        md.append("")
        md.append("| Profile | n | Mean attempts | Correct rate | Consolidation rate |")
        md.append("|---|---:|---:|---:|---:|")
        for prof, d in sorted(by_profile.items(), key=lambda kv: -kv[1]["n"]):
            md.append(
                f"| {prof} | {d['n']} | {d['mean_attempts']} | "
                f"{d['correct_rate']:.1%} | {d['consolidation_rate']:.1%} |"
            )
        md.append("")

    md.append("## Synthetic-data caveats")
    md.append("")
    md.append(
        "- Tutor feedback in synthetic sessions is sampled from a fixed "
        "template bank; the PF-fidelity evaluator therefore measures the "
        "*templates*, not the live LLM, so the rate should be taken as a "
        "best-case ceiling."
    )
    md.append(
        "- Student attempts are sampled with parameterised profiles. They "
        "are realistic in shape (counts, stuck signals, English drift) but "
        "do not capture the long-tail creativity of real learners."
    )
    md.append(
        "- Gold misconception labels are exact by construction. Real-data "
        "labels (parsed from consolidation text) are noisier."
    )
    md.append(
        "- Jury simulation is still offline policy replay — synthetic data "
        "does not exercise the actual LLM jurors."
    )

    (OUT_DIR / "synth_report.md").write_text("\n".join(md))

    print(f"Wrote {OUT_DIR/'synth_metrics.json'}")
    print(f"Wrote {OUT_DIR/'synth_report.md'}")
    # Echo headline so the reader can sanity-check inline.
    print()
    for k, v in headline.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
