"""
Offline jury-verdict simulation.

Re-runs the *deterministic policy* the three jurors are prompted with
(see `backend/services/jury.py`) on every reconstructed problem from the
session logs and produces what each persona would most likely vote, plus
the resulting majority verdict. No LLM calls.

Persona policies (mirroring the system prompts in jury.py):

  Melchior  (strict, biased toward INCREASE)
    INCREASE if attempts <= 3 OR student answered correctly with no stuck signal
    DECREASE only if attempts >= 7 AND no progress
    else MAINTAIN

  Casper    (benevolent, protective of confidence)
    DECREASE if attempts >= 5 OR any stuck signal
    INCREASE only if solved on attempt 1
    else MAINTAIN

  Balthazar (balanced, evidence-based)
    INCREASE if attempts <= 2 AND solved correctly
    DECREASE if attempts >= 6 OR (attempts >= 5 AND no late progress)
    else MAINTAIN

We then check:
  - Inter-juror agreement (Fleiss-style 3-rater proportion).
  - Distribution of majority verdicts.
  - Whether the verdict aligns with the empirically-derived productive
    zone from eval_struggle_index.py.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from data_loader import Problem, Session, load_sessions
from eval_struggle_index import _stuck_rate, _struggle_index, _bucket


INCREASE = "INCREASE"
MAINTAIN = "MAINTAIN"
DECREASE = "DECREASE"


@dataclass
class JuryRow:
    session_id: str
    problem_index: int
    task_type: str
    difficulty: int
    attempts: int
    correct: bool
    stuck_rate: float
    showed_progress: bool
    melchior: str
    casper: str
    balthazar: str
    verdict: str
    bucket_from_index: str


def _showed_progress(p: Problem) -> bool:
    if len(p.student_attempts) < 2:
        return False
    first, last = p.student_attempts[0], p.student_attempts[-1]
    return len(last.split()) >= len(first.split())


def melchior(attempts: int, correct: bool, stuck: float) -> str:
    if attempts <= 3 and (correct or stuck == 0):
        return INCREASE
    if attempts >= 7 and not correct:
        return DECREASE
    return MAINTAIN


def casper(attempts: int, correct: bool, stuck: float) -> str:
    if attempts == 1 and correct:
        return INCREASE
    if attempts >= 5 or stuck > 0:
        return DECREASE
    return MAINTAIN


def balthazar(attempts: int, correct: bool, stuck: float, progress: bool) -> str:
    if attempts <= 2 and correct:
        return INCREASE
    if attempts >= 6 or (attempts >= 5 and not progress):
        return DECREASE
    return MAINTAIN


def majority(verdicts: list[str]) -> str:
    counts = Counter(verdicts)
    return counts.most_common(1)[0][0]


def evaluate(sessions: list[Session]) -> dict:
    rows: list[JuryRow] = []
    for sess in sessions:
        for p in sess.problems:
            attempts = len(p.student_attempts)
            if attempts == 0:
                continue
            stuck = _stuck_rate(p.student_attempts)
            progress = _showed_progress(p)
            mean_time = 0.0  # Not strictly needed for verdict policy.
            s_index = _struggle_index(attempts, mean_time, stuck)
            m = melchior(attempts, p.correct, stuck)
            c = casper(attempts, p.correct, stuck)
            b = balthazar(attempts, p.correct, stuck, progress)
            v = majority([m, c, b])
            rows.append(
                JuryRow(
                    session_id=sess.session_id,
                    problem_index=p.problem_index,
                    task_type=p.task_type,
                    difficulty=p.difficulty_score,
                    attempts=attempts,
                    correct=p.correct,
                    stuck_rate=round(stuck, 2),
                    showed_progress=progress,
                    melchior=m,
                    casper=c,
                    balthazar=b,
                    verdict=v,
                    bucket_from_index=_bucket(s_index),
                )
            )

    if not rows:
        return {"n": 0}

    total = len(rows)
    unanimous = sum(1 for r in rows if r.melchior == r.casper == r.balthazar)
    two_of_three = sum(
        1
        for r in rows
        if not (r.melchior == r.casper == r.balthazar)
        and (
            (r.melchior == r.casper)
            or (r.melchior == r.balthazar)
            or (r.casper == r.balthazar)
        )
    )
    split = total - unanimous - two_of_three

    verdict_counts = Counter(r.verdict for r in rows)
    juror_counts = {
        "Melchior": Counter(r.melchior for r in rows),
        "Casper": Counter(r.casper for r in rows),
        "Balthazar": Counter(r.balthazar for r in rows),
    }

    # Verdict-vs-bucket consistency check.
    # Expected mapping: too_easy -> INCREASE, productive -> MAINTAIN, too_hard -> DECREASE.
    expected = {"too_easy": INCREASE, "productive": MAINTAIN, "too_hard": DECREASE}
    aligned = sum(1 for r in rows if r.verdict == expected[r.bucket_from_index])
    alignment_rate = round(aligned / total, 3)

    return {
        "n": total,
        "agreement": {
            "unanimous": unanimous,
            "majority_2of3": two_of_three,
            "split_3way": split,
            "unanimous_rate": round(unanimous / total, 3),
        },
        "verdict_distribution": dict(verdict_counts),
        "verdict_distribution_pct": {
            k: round(v / total, 3) for k, v in verdict_counts.items()
        },
        "by_juror": {
            name: dict(c) for name, c in juror_counts.items()
        },
        "verdict_vs_struggle_bucket_alignment": alignment_rate,
        "rows": [asdict(r) for r in rows],
    }


def render_markdown(result: dict) -> str:
    if not result.get("n"):
        return "## Jury Verdict Simulation\n\n_No data._"
    n = result["n"]
    a = result["agreement"]
    lines = ["## Jury Verdict Simulation (offline policy replay)", ""]
    lines.append(
        f"Replayed jury policy on **{n}** problems (no API calls — uses each "
        f"juror's documented stance to predict its vote)."
    )
    lines.append("")
    lines.append("### Inter-juror agreement")
    lines.append("| Outcome | Count | Share |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Unanimous | {a['unanimous']} | {a['unanimous']/n:.1%} |")
    lines.append(f"| 2-of-3 majority | {a['majority_2of3']} | {a['majority_2of3']/n:.1%} |")
    lines.append(f"| 3-way split | {a['split_3way']} | {a['split_3way']/n:.1%} |")

    lines.append("")
    lines.append("### Final verdict distribution")
    lines.append("| Verdict | Count | Share |")
    lines.append("|---|---:|---:|")
    for v in ("INCREASE", "MAINTAIN", "DECREASE"):
        cnt = result["verdict_distribution"].get(v, 0)
        lines.append(f"| {v} | {cnt} | {cnt/n:.1%} |")

    lines.append("")
    lines.append("### Per-juror lean")
    lines.append("| Juror | INCREASE | MAINTAIN | DECREASE |")
    lines.append("|---|---:|---:|---:|")
    for name in ("Melchior", "Casper", "Balthazar"):
        c = result["by_juror"][name]
        lines.append(
            f"| {name} | {c.get('INCREASE',0)} | {c.get('MAINTAIN',0)} | {c.get('DECREASE',0)} |"
        )

    lines.append("")
    lines.append(
        f"**Verdict ⇄ struggle-index alignment:** "
        f"{result['verdict_vs_struggle_bucket_alignment']:.1%} of verdicts match "
        f"the bucket implied by the derived Struggle Index."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    sessions = load_sessions()
    out = evaluate(sessions)
    print(render_markdown(out))
