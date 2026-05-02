"""
Struggle-Index analysis.

We define a per-problem Struggle Index that operationalises the jury's
attempt-count buckets (see backend/services/jury.py) into a continuous score:

  S = 0.6 * normalised_attempts
    + 0.3 * normalised_time_per_attempt
    + 0.1 * stuck_signal_rate

  where:
    normalised_attempts        = min(attempts / 5, 1.0)
    normalised_time_per_attempt= min(mean_time_sec / 60, 1.0)
    stuck_signal_rate          = fraction of attempts containing
                                 'i dont know', 'no idea', 'idk', etc.

Interpretation:
  S in [0.00, 0.25)  -> too easy        (verdict: INCREASE)
  S in [0.25, 0.65]  -> productive zone (verdict: MAINTAIN)
  S in (0.65, 1.00]  -> too hard        (verdict: DECREASE)

We then check three things:
  A. Distribution of S across all logged problems (mean, median, % in zone).
  B. Histogram of attempts-per-problem and consolidation rate.
  C. Per-task-type and per-difficulty breakdown.

This is a derived metric — the live system does not yet log a numeric
Struggle Index; it relies on the jury verdict alone. This eval shows what
the index looks like on real data and whether the jury's bucket boundaries
make empirical sense.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from data_loader import (
    AttemptRow,
    Problem,
    Session,
    load_attempt_rows,
    load_sessions,
)


_STUCK_TOKENS = ("i dont know", "i don't know", "no idea", "idk", "i give up", "no clue")


@dataclass
class ProblemStruggle:
    session_id: str
    problem_id: str
    task_type: str
    difficulty: int
    attempts: int
    mean_time_sec: float
    total_time_sec: float
    stuck_rate: float
    correct: bool
    consolidated: bool
    struggle_index: float
    bucket: str  # too_easy | productive | too_hard


def _bucket(score: float) -> str:
    if score < 0.25:
        return "too_easy"
    if score <= 0.65:
        return "productive"
    return "too_hard"


def _stuck_rate(attempts: list[str]) -> float:
    if not attempts:
        return 0.0
    hits = sum(
        1 for a in attempts if any(tok in a.lower() for tok in _STUCK_TOKENS)
    )
    return hits / len(attempts)


def _struggle_index(
    n_attempts: int, mean_time: float, stuck_rate: float
) -> float:
    norm_attempts = min(n_attempts / 5, 1.0)
    norm_time = min(mean_time / 60, 1.0)
    return round(
        0.6 * norm_attempts + 0.3 * norm_time + 0.1 * stuck_rate, 4
    )


def _join_csv_rows_by_problem(rows: list[AttemptRow]) -> dict[tuple[str, str], list[AttemptRow]]:
    grouped: dict[tuple[str, str], list[AttemptRow]] = defaultdict(list)
    for r in rows:
        grouped[(r.session_id, r.problem_id)].append(r)
    for v in grouped.values():
        v.sort(key=lambda x: x.attempt_number)
    return grouped


def evaluate(
    sessions: list[Session], rows: list[AttemptRow]
) -> dict:
    grouped = _join_csv_rows_by_problem(rows)

    # We use CSV rows for time/attempt counts because the conversation log
    # does not carry per-attempt elapsed seconds. We then enrich each
    # CSV-derived problem with task_type/difficulty from the matching
    # session conversation if available.
    session_problem_meta: dict[str, list[Problem]] = defaultdict(list)
    for s in sessions:
        session_problem_meta[s.session_id].extend(s.problems)

    items: list[ProblemStruggle] = []
    for (session_id, problem_id), prows in grouped.items():
        attempts_count = len(prows)
        times = [r.time_spent_sec for r in prows if r.time_spent_sec >= 0]
        # CSV time_spent_sec is cumulative-from-problem-start — convert to per-attempt deltas.
        per_attempt = []
        prev = 0.0
        for t in times:
            per_attempt.append(max(t - prev, 0.0))
            prev = t
        mean_time = statistics.mean(per_attempt) if per_attempt else 0.0
        total_time = times[-1] if times else 0.0
        correct = any(r.final_correct for r in prows)

        # Attempt strings come from session conversation if we can match.
        matched_problem: Problem | None = None
        for p in session_problem_meta.get(session_id, []):
            if len(p.student_attempts) == attempts_count and not p.consolidated and not correct:
                matched_problem = p
                break
            if len(p.student_attempts) == attempts_count and (p.consolidated or p.correct == correct):
                matched_problem = p
                break

        attempt_texts = matched_problem.student_attempts if matched_problem else []
        task_type = matched_problem.task_type if matched_problem else "unknown"
        difficulty = matched_problem.difficulty_score if matched_problem else 0
        consolidated = matched_problem.consolidated if matched_problem else (
            attempts_count >= 5 and not correct
        )

        stuck = _stuck_rate(attempt_texts)
        s_index = _struggle_index(attempts_count, mean_time, stuck)
        items.append(
            ProblemStruggle(
                session_id=session_id,
                problem_id=problem_id,
                task_type=task_type,
                difficulty=difficulty,
                attempts=attempts_count,
                mean_time_sec=round(mean_time, 2),
                total_time_sec=round(total_time, 2),
                stuck_rate=round(stuck, 3),
                correct=correct,
                consolidated=consolidated,
                struggle_index=s_index,
                bucket=_bucket(s_index),
            )
        )

    if not items:
        return {"n_problems": 0}

    indices = [it.struggle_index for it in items]
    attempts = [it.attempts for it in items]
    bucket_counts = Counter(it.bucket for it in items)
    by_task = defaultdict(list)
    by_diff = defaultdict(list)
    for it in items:
        by_task[it.task_type].append(it.struggle_index)
        by_diff[it.difficulty].append(it.struggle_index)

    summary = {
        "n_problems": len(items),
        "struggle_index": {
            "mean": round(statistics.mean(indices), 3),
            "median": round(statistics.median(indices), 3),
            "stdev": round(statistics.pstdev(indices), 3),
            "min": round(min(indices), 3),
            "max": round(max(indices), 3),
        },
        "attempts": {
            "mean": round(statistics.mean(attempts), 2),
            "median": statistics.median(attempts),
            "max": max(attempts),
        },
        "bucket_distribution": {
            "too_easy": bucket_counts.get("too_easy", 0),
            "productive": bucket_counts.get("productive", 0),
            "too_hard": bucket_counts.get("too_hard", 0),
        },
        "bucket_distribution_pct": {
            k: round(v / len(items), 3)
            for k, v in {
                "too_easy": bucket_counts.get("too_easy", 0),
                "productive": bucket_counts.get("productive", 0),
                "too_hard": bucket_counts.get("too_hard", 0),
            }.items()
        },
        "consolidation_rate": round(
            sum(1 for it in items if it.consolidated) / len(items), 3
        ),
        "correct_rate": round(
            sum(1 for it in items if it.correct) / len(items), 3
        ),
        "by_task_type_mean_index": {
            t: round(statistics.mean(v), 3) for t, v in sorted(by_task.items())
        },
        "by_difficulty_mean_index": {
            d: round(statistics.mean(v), 3) for d, v in sorted(by_diff.items())
        },
        "items": [asdict(it) for it in items],
    }
    return summary


def _ascii_hist(values: list[int], width: int = 30) -> str:
    if not values:
        return ""
    counts = Counter(values)
    max_v = max(counts.values())
    out = []
    for k in sorted(counts):
        bar = "█" * max(1, int(counts[k] / max_v * width))
        out.append(f"  {k:>2}  {bar} ({counts[k]})")
    return "\n".join(out)


def render_markdown(result: dict) -> str:
    if not result.get("n_problems"):
        return "## Struggle Index\n\n_No problems found in CSV log._"
    lines = ["## Struggle Index", ""]
    lines.append(f"Computed on **{result['n_problems']}** problems from `pf_learning_logs.csv`.")
    s = result["struggle_index"]
    lines.append("")
    lines.append(
        f"- Mean struggle index: **{s['mean']}**  (median {s['median']}, σ {s['stdev']})"
    )
    lines.append(
        f"- Attempts/problem: mean {result['attempts']['mean']}, "
        f"median {result['attempts']['median']}, max {result['attempts']['max']}"
    )
    lines.append(f"- Consolidation fired: **{result['consolidation_rate']:.1%}** of problems")
    lines.append(f"- Correctly solved: **{result['correct_rate']:.1%}** of problems")
    lines.append("")
    lines.append("### Productive zone occupancy")
    bd = result["bucket_distribution"]
    bdp = result["bucket_distribution_pct"]
    lines.append("| Bucket | Range | Count | Share |")
    lines.append("|---|---|---:|---:|")
    lines.append(f"| Too easy | S < 0.25 | {bd['too_easy']} | {bdp['too_easy']:.1%} |")
    lines.append(f"| Productive | 0.25 ≤ S ≤ 0.65 | {bd['productive']} | {bdp['productive']:.1%} |")
    lines.append(f"| Too hard | S > 0.65 | {bd['too_hard']} | {bdp['too_hard']:.1%} |")

    lines.append("")
    lines.append("### Mean struggle index by difficulty")
    lines.append("| Difficulty | Mean S |")
    lines.append("|---:|---:|")
    for d, v in result["by_difficulty_mean_index"].items():
        lines.append(f"| {d} | {v} |")

    lines.append("")
    lines.append("### Mean struggle index by task type")
    lines.append("| Task type | Mean S |")
    lines.append("|---|---:|")
    for t, v in result["by_task_type_mean_index"].items():
        lines.append(f"| {t} | {v} |")

    return "\n".join(lines)


if __name__ == "__main__":
    sessions = load_sessions()
    rows = load_attempt_rows()
    out = evaluate(sessions, rows)
    print(render_markdown(out))
