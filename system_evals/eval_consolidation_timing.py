"""
Consolidation-timing evaluation.

PFService fires the consolidation phase iff
    not is_correct  AND  attempt_number >= MAX_ATTEMPTS (= 5)

We assess two things:

  1. Trigger correctness — did consolidation fire exactly when both
     conditions were met? (sanity check on the production rule)

  2. Adaptiveness — does the *position* of consolidation predict whether
     the student would have eventually solved the problem? In particular:

       a. % of consolidations on problems where the student was clearly
          stuck (>=2 'I don't know'-type signals or no improvement across
          attempts).
       b. % of consolidations that arrived after the student showed signs
          of progress on the final attempt (debatable — may have been
          premature).

  3. Latency — average minutes from problem start to consolidation.

We also report the inverse: problems where consolidation should have
fired (>=5 incorrect attempts) but did not appear in the log.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from datetime import datetime

from data_loader import Problem, Session, load_sessions


_STUCK_TOKENS = ("i dont know", "i don't know", "no idea", "idk", "i give up")
MAX_ATTEMPTS = 5


@dataclass
class ConsolidationCase:
    session_id: str
    problem_index: int
    task_type: str
    difficulty: int
    attempts: int
    consolidated: bool
    correct: bool
    rule_should_fire: bool
    rule_match: bool
    minutes_to_consolidation: float | None
    stuck_signal_count: int
    showed_late_progress: bool


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def _showed_late_progress(p: Problem) -> bool:
    """Heuristic: final attempt is longer than first AND not a stuck token."""
    if len(p.student_attempts) < 2:
        return False
    first, last = p.student_attempts[0], p.student_attempts[-1]
    if any(tok in last.lower() for tok in _STUCK_TOKENS):
        return False
    return len(last.split()) > len(first.split())


def _stuck_count(p: Problem) -> int:
    return sum(
        1 for a in p.student_attempts if any(tok in a.lower() for tok in _STUCK_TOKENS)
    )


def _minutes_to_consolidation(p: Problem) -> float | None:
    start = next(
        (e.timestamp for e in p.events if e.event_type == "problem_start"), None
    )
    cons = next(
        (e.timestamp for e in p.events if e.event_type == "consolidation"), None
    )
    if not start or not cons:
        return None
    s, c = _parse_ts(start), _parse_ts(cons)
    if not s or not c:
        return None
    return round((c - s).total_seconds() / 60, 2)


def evaluate(sessions: list[Session]) -> dict:
    cases: list[ConsolidationCase] = []
    for sess in sessions:
        for p in sess.problems:
            attempts = len(p.student_attempts)
            if attempts == 0 and not p.consolidated:
                continue
            should_fire = (not p.correct) and attempts >= MAX_ATTEMPTS
            rule_match = should_fire == p.consolidated
            cases.append(
                ConsolidationCase(
                    session_id=sess.session_id,
                    problem_index=p.problem_index,
                    task_type=p.task_type,
                    difficulty=p.difficulty_score,
                    attempts=attempts,
                    consolidated=p.consolidated,
                    correct=p.correct,
                    rule_should_fire=should_fire,
                    rule_match=rule_match,
                    minutes_to_consolidation=_minutes_to_consolidation(p),
                    stuck_signal_count=_stuck_count(p),
                    showed_late_progress=_showed_late_progress(p),
                )
            )

    if not cases:
        return {"n_problems": 0}

    fired = [c for c in cases if c.consolidated]
    rule_total = len(cases)
    rule_passed = sum(1 for c in cases if c.rule_match)
    false_positives = [c for c in cases if c.consolidated and not c.rule_should_fire]
    false_negatives = [c for c in cases if c.rule_should_fire and not c.consolidated]
    latencies = [
        c.minutes_to_consolidation for c in fired if c.minutes_to_consolidation is not None
    ]

    summary = {
        "n_problems": len(cases),
        "n_consolidations": len(fired),
        "consolidation_rate": round(len(fired) / len(cases), 3),
        "rule_match_rate": round(rule_passed / rule_total, 3),
        "false_positives": len(false_positives),
        "false_negatives": len(false_negatives),
        "fired_problems_with_stuck_signals_pct": round(
            (sum(1 for c in fired if c.stuck_signal_count >= 2) / len(fired)) if fired else 0,
            3,
        ),
        "fired_problems_with_late_progress_pct": round(
            (sum(1 for c in fired if c.showed_late_progress) / len(fired)) if fired else 0,
            3,
        ),
        "minutes_to_consolidation": (
            {
                "mean": round(statistics.mean(latencies), 2),
                "median": round(statistics.median(latencies), 2),
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
            }
            if latencies
            else None
        ),
        "examples_false_negative": [asdict(c) for c in false_negatives[:5]],
        "examples_false_positive": [asdict(c) for c in false_positives[:5]],
    }
    return summary


def render_markdown(result: dict) -> str:
    if not result.get("n_problems"):
        return "## Adaptive Consolidation Timing\n\n_No problems available._"
    lines = ["## Adaptive Consolidation Timing", ""]
    lines.append(
        f"Across **{result['n_problems']}** reconstructed problems, consolidation "
        f"fired on **{result['n_consolidations']}** ({result['consolidation_rate']:.1%})."
    )
    lines.append("")
    lines.append(
        f"- Rule-fidelity (consolidation iff ≥{MAX_ATTEMPTS} incorrect attempts): "
        f"**{result['rule_match_rate']:.1%}**"
    )
    lines.append(
        f"- False positives (fired without meeting rule): {result['false_positives']}"
    )
    lines.append(
        f"- False negatives (rule met but not fired): {result['false_negatives']}"
    )
    lines.append(
        f"- Of consolidated problems, {result['fired_problems_with_stuck_signals_pct']:.1%} "
        f"had ≥2 stuck signals (good timing)."
    )
    lines.append(
        f"- Of consolidated problems, {result['fired_problems_with_late_progress_pct']:.1%} "
        f"showed visible late progress (potentially premature)."
    )
    if result["minutes_to_consolidation"]:
        m = result["minutes_to_consolidation"]
        lines.append(
            f"- Latency to consolidation: mean {m['mean']} min "
            f"(median {m['median']}, range {m['min']}–{m['max']})."
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sessions = load_sessions()
    out = evaluate(sessions)
    print(render_markdown(out))
