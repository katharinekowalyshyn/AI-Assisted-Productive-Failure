"""
Generate synthetic Productive-Failure sessions.

Output:
  system_evals/synth/sessions/sess_synth_*.json   (real-format session files)
  system_evals/synth/gold_labels.json             (per-problem ground truth)
  system_evals/synth/manifest.json                (population summary)

The generated session files are byte-for-byte compatible with the live
schema in `backend/sessions/`, so `data_loader.load_sessions(path=...)`
can read them with no changes.

Usage:
    python3 generate_sessions.py                 # 100 sessions, seed 42
    python3 generate_sessions.py --n 250 --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from problem_bank import PROBLEMS, Problem, by_task_and_difficulty
from profiles import PROFILE_MIX, PROFILES, Profile


HERE = Path(__file__).resolve().parent
DEFAULT_SESSIONS_DIR = HERE / "sessions"
DEFAULT_GOLD = HERE / "gold_labels.json"
DEFAULT_MANIFEST = HERE / "manifest.json"

MAX_ATTEMPTS = 5  # mirrors backend/pf/service.py


# ---------------------------------------------------------------------------
# Synthetic name pool
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "Maya", "Jordan", "Alex", "Sam", "Riley", "Taylor", "Casey", "Morgan",
    "Avery", "Quinn", "Reese", "Drew", "Jamie", "Robin", "Skyler", "Devon",
    "Cameron", "Sage", "Rowan", "Phoenix",
]


# ---------------------------------------------------------------------------
# Tutor feedback templates (mirroring real production messages)
# ---------------------------------------------------------------------------

_FEEDBACK_FIRST = [
    "Great start with \"{frag}\" — that's a solid try! What were you thinking when you chose those words? Give it another go!",
    "Nice effort on your first attempt! What tense or form do you think this needs? Try once more.",
    "Good attempt — you're engaging with the prompt. What part feels least certain to you? Take another shot.",
]

_FEEDBACK_RETRY = [
    "I see you're refining your answer — what's making you change your mind on \"{frag}\"? Try again!",
    "You're getting closer. What grammatical detail might still be off? Give it another try.",
    "Nice progress! Can you think about whether the verb form matches the subject? Try once more.",
    "Good thinking. What about the article or preposition — are you sure of it? Have another go.",
]

_FEEDBACK_STUCK = [
    "It's okay to feel unsure — let's break it down. What single word in the prompt feels hardest? Give it another try!",
    "I appreciate your honesty in saying you don't know. What would you guess based on what you know about Spanish verbs? Try again.",
]

_CORRECT_TEMPLATE = "Nice work — that's correct! Click 'Next Exercise' when you're ready to continue."

_PRECONSOL_TEMPLATE = "You've put in real effort on this one — let's review it together now."

_CONSOLIDATION_TEMPLATE = (
    "Consolidation: Good effort across your attempts. You correctly used elements like \"{frag}\". "
    "However, the main issue was {error_summary}. \n\nCorrect answer: {answer}\n\n"
    "Remember: {rule_hint}"
)

_RULE_HINTS = {
    "VOCABULARY": "double-check vocabulary using context — \"tienda\" is store, \"equipo\" is team.",
    "VERB_CONJUGATION": "match the verb ending to the subject (yo → -o, tú → -as/-es, él/ella → -a/-e).",
    "GENDER_AGREEMENT": "noun gender drives the article and adjective ending (el libro, la casa).",
    "SER_VS_ESTAR": "use 'ser' for permanent traits, 'estar' for states/locations.",
    "PREPOSITION": "Spanish requires 'a' before destinations after 'ir' (voy a la tienda).",
    "REFLEXIVE": "verbs like llamarse, lavarse, levantarse take a reflexive pronoun (me, te, se).",
    "TENSE": "the preterite tense expresses completed past actions (comí, fui, hice).",
    "SUBJUNCTIVE": "the subjunctive is used after expressions of doubt, desire, or emotion (espero que llegue).",
    "ENGLISH_INTRUSION": "translate every content word — keep the response fully in Spanish.",
    "STUCK": "even an educated guess based on the prompt's vocabulary helps you learn.",
}

_ERROR_SUMMARIES = {
    "VOCABULARY": "the wrong vocabulary word was used (e.g. 'equipo' means team, not store)",
    "VERB_CONJUGATION": "the verb conjugation did not match the subject's person/number",
    "GENDER_AGREEMENT": "the article or adjective did not agree with the noun's gender",
    "SER_VS_ESTAR": "ser and estar were confused — they are not interchangeable",
    "PREPOSITION": "a required preposition (a/de/en) was missing or wrong",
    "REFLEXIVE": "the reflexive pronoun was missing",
    "TENSE": "the wrong tense was used for the time reference in the prompt",
    "SUBJUNCTIVE": "the subjunctive mood was needed but indicative was used",
    "ENGLISH_INTRUSION": "English words appeared in what should be a fully Spanish response",
    "STUCK": "the student gave up before exploring the structure of the prompt",
}


# ---------------------------------------------------------------------------
# Attempt + session generation
# ---------------------------------------------------------------------------

def _sample_profile(rng: random.Random) -> Profile:
    r = rng.random()
    cum = 0.0
    for name, w in PROFILE_MIX:
        cum += w
        if r <= cum:
            return PROFILES[name]
    return PROFILES[PROFILE_MIX[-1][0]]


def _pick_misconception(problem: Problem, rng: random.Random) -> str:
    candidates = [m for m in problem.misconceptions if m in problem.error_attempts]
    if not candidates:
        candidates = list(problem.error_attempts.keys())
    return rng.choice(candidates)


def _make_wrong_attempt(problem: Problem, tag: str, rng: random.Random) -> str:
    options = problem.error_attempts.get(tag) or [problem.answer_partial]
    return rng.choice(options)


def _maybe_inject_english(text: str, prob: float, rng: random.Random) -> str:
    if rng.random() > prob:
        return text
    swaps = [
        ("la tienda", "the store"),
        ("el libro", "the book"),
        ("la casa", "the house"),
        ("comí", "ate"),
        ("voy", "go"),
        ("quiero", "want"),
        ("hermano", "brother"),
        ("hermana", "sister"),
    ]
    for sp, en in swaps:
        if sp in text:
            return text.replace(sp, en)
    return text + " (idk)"


def _generate_attempts(
    problem: Problem,
    profile: Profile,
    rng: random.Random,
) -> tuple[list[str], list[str], bool]:
    """
    Returns (attempts, gold_misconceptions_per_attempt, solved).
    """
    attempts: list[str] = []
    tags_per_attempt: list[str] = []

    solved = rng.random() < profile.p_correct_first

    if solved:
        first = problem.answer
        first = _maybe_inject_english(first, profile.english_drift * 0.3, rng)
        attempts.append(first)
        tags_per_attempt.append("CORRECT")
        return attempts, tags_per_attempt, True

    # Otherwise iterate up to max_attempts (or MAX_ATTEMPTS — whichever smaller)
    cap = min(profile.max_attempts, MAX_ATTEMPTS)
    for i in range(cap):
        if rng.random() < profile.p_stuck_per_attempt:
            attempts.append(rng.choice(["i don't know", "no idea", "idk", "i give up"]))
            tags_per_attempt.append("STUCK")
            continue

        if rng.random() < profile.p_inject_misconception:
            tag = _pick_misconception(problem, rng)
            wrong = _make_wrong_attempt(problem, tag, rng)
            wrong = _maybe_inject_english(wrong, profile.english_drift, rng)
            attempts.append(wrong)
            tags_per_attempt.append(tag)
        else:
            # Generic partial attempt (no labelled misconception)
            attempts.append(problem.answer_partial)
            tags_per_attempt.append("PARTIAL")

        if i >= 1 and rng.random() < profile.p_correct_per_retry:
            attempts.append(problem.answer)
            tags_per_attempt.append("CORRECT")
            return attempts, tags_per_attempt, True

    return attempts, tags_per_attempt, False


def _build_conversation(
    problem: Problem,
    attempts: list[str],
    tags: list[str],
    profile: Profile,
    start_time: datetime,
    rng: random.Random,
) -> tuple[list[dict], datetime, bool]:
    """Materialise the conversation_history for one problem.

    Returns (events, end_time, consolidated_flag).
    """
    events: list[dict] = []
    t = start_time

    events.append({
        "timestamp": t.isoformat(),
        "role": "system",
        "event_type": "problem_start",
        "content": f"New problem started ({problem.task_type}, difficulty {problem.difficulty}).",
    })

    consolidated = False
    solved = False
    for idx, (attempt_text, tag) in enumerate(zip(attempts, tags)):
        wait = max(5.0, rng.gauss(profile.inter_attempt_mean, profile.inter_attempt_sigma))
        t = t + timedelta(seconds=wait)
        events.append({
            "timestamp": t.isoformat(),
            "role": "student",
            "event_type": "attempt",
            "content": attempt_text,
        })

        # Tutor reply
        t = t + timedelta(seconds=rng.uniform(2.5, 6.0))
        if tag == "CORRECT":
            solved = True
            events.append({
                "timestamp": t.isoformat(),
                "role": "tutor",
                "event_type": "feedback",
                "content": _CORRECT_TEMPLATE,
            })
            break

        if idx + 1 >= MAX_ATTEMPTS and not solved:
            # Consolidation cycle
            events.append({
                "timestamp": t.isoformat(),
                "role": "tutor",
                "event_type": "feedback",
                "content": _PRECONSOL_TEMPLATE,
            })
            t = t + timedelta(seconds=rng.uniform(0.05, 0.5))
            primary_tag = next(
                (g for g in tags if g not in {"CORRECT", "PARTIAL"}),
                "VOCABULARY",
            )
            events.append({
                "timestamp": t.isoformat(),
                "role": "tutor",
                "event_type": "consolidation",
                "content": _CONSOLIDATION_TEMPLATE.format(
                    frag=problem.answer_partial,
                    error_summary=_ERROR_SUMMARIES.get(primary_tag, "an unidentified error"),
                    answer=problem.answer,
                    rule_hint=_RULE_HINTS.get(primary_tag, "review the relevant grammar rule."),
                ),
            })
            consolidated = True
            break

        # Pick a feedback template
        if tag == "STUCK":
            template = rng.choice(_FEEDBACK_STUCK)
        elif idx == 0:
            template = rng.choice(_FEEDBACK_FIRST)
        else:
            template = rng.choice(_FEEDBACK_RETRY)
        events.append({
            "timestamp": t.isoformat(),
            "role": "tutor",
            "event_type": "feedback",
            "content": template.format(frag=problem.answer_partial),
        })

    # next_problem event closes the problem block (mirrors live behaviour)
    t = t + timedelta(seconds=rng.uniform(2, 8))
    events.append({
        "timestamp": t.isoformat(),
        "role": "system",
        "event_type": "next_problem",
        "content": "Advanced to next problem.",
    })
    return events, t, consolidated


# ---------------------------------------------------------------------------
# Per-session orchestration
# ---------------------------------------------------------------------------

def _generate_session(
    sess_index: int,
    rng: random.Random,
    n_problems: int,
) -> tuple[dict, list[dict]]:
    profile = _sample_profile(rng)
    student = rng.choice(_FIRST_NAMES)
    sess_start = datetime(2026, 4, 25, 14, 0, 0, tzinfo=timezone.utc) + timedelta(
        hours=sess_index, minutes=rng.randint(0, 30)
    )
    sess_id = f"sess_synth_{sess_start.strftime('%Y%m%d%H%M%S')}_{sess_index:04d}"

    problems = list(PROBLEMS)
    rng.shuffle(problems)
    selected = problems[:n_problems]

    full_history: list[dict] = []
    gold_records: list[dict] = []
    t_cursor = sess_start
    total_attempts = 0
    last_problem: Problem | None = None
    last_consolidated = False
    last_difficulty = selected[0].difficulty

    for p_idx, problem in enumerate(selected, start=1):
        attempts, tags, solved = _generate_attempts(problem, profile, rng)
        if not attempts:
            continue
        events, t_cursor, consolidated = _build_conversation(
            problem, attempts, tags, profile, t_cursor, rng
        )
        full_history.extend(events)
        total_attempts += len(attempts)
        last_problem = problem
        last_consolidated = consolidated
        last_difficulty = problem.difficulty

        problem_id = f"prob_synth_{uuid4().hex[:10]}"
        gold_records.append({
            "session_id": sess_id,
            "problem_index": p_idx,
            "problem_id": problem_id,
            "task_type": problem.task_type,
            "difficulty": problem.difficulty,
            "profile": profile.name,
            "n_attempts": len(attempts),
            "solved": solved,
            "consolidated": consolidated,
            "gold_misconceptions": sorted({
                t for t in tags if t not in {"CORRECT", "PARTIAL"}
            }),
            "attempts": attempts,
            "answer": problem.answer,
        })

    sess_payload = {
        "problem": last_problem.prompt if last_problem else "",
        "task_type": last_problem.task_type if last_problem else "translation",
        "difficulty_score": last_difficulty,
        "attempts": [],
        "uploaded_content": "",
        "problems_completed": len(selected),
        "student_name": student,
        "problem_id": f"prob_synth_{uuid4().hex[:10]}",
        "problem_started_at": t_cursor.isoformat(),
        "total_attempts": total_attempts,
        "conversation_history": full_history,
        "session_started_at": sess_start.isoformat(),
        "_synthetic": {
            "profile": profile.name,
            "n_problems": len(selected),
            "consolidation_in_last_problem": last_consolidated,
        },
    }
    return sess_payload, gold_records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic PF sessions.")
    parser.add_argument("--n", type=int, default=100, help="Number of sessions to generate (default: 100).")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42).")
    parser.add_argument(
        "--problems-per-session",
        type=str,
        default="1-3",
        help="Range of problems per session, e.g. '1-3' or '2'. Default '1-3'.",
    )
    parser.add_argument("--out-sessions", type=Path, default=DEFAULT_SESSIONS_DIR)
    parser.add_argument("--out-gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--out-manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    if "-" in args.problems_per_session:
        lo, hi = (int(x) for x in args.problems_per_session.split("-"))
    else:
        lo = hi = int(args.problems_per_session)

    args.out_sessions.mkdir(parents=True, exist_ok=True)
    # Wipe any prior synthetic files so re-runs are clean.
    for old in args.out_sessions.glob("sess_synth_*.json"):
        old.unlink()

    all_gold: list[dict] = []
    profile_counts: dict[str, int] = {}
    consolidation_count = 0
    correct_count = 0
    total_problems = 0

    for i in range(args.n):
        n_p = rng.randint(lo, hi)
        sess, gold = _generate_session(i, rng, n_p)
        path = args.out_sessions / f"{sess['_synthetic'].get('sess_id') or i:04}_placeholder"
        # Use the conversation-history-derived id stored in sess id
        sess_id = next(
            (g["session_id"] for g in gold), f"sess_synth_{i:05d}"
        )
        path = args.out_sessions / f"{sess_id}.json"
        path.write_text(json.dumps(sess, indent=2))
        all_gold.extend(gold)
        profile = sess["_synthetic"]["profile"]
        profile_counts[profile] = profile_counts.get(profile, 0) + 1
        for g in gold:
            total_problems += 1
            if g["consolidated"]:
                consolidation_count += 1
            if g["solved"]:
                correct_count += 1

    args.out_gold.write_text(json.dumps(all_gold, indent=2))
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_sessions": args.n,
        "n_problems": total_problems,
        "profile_distribution": profile_counts,
        "consolidation_rate": round(consolidation_count / total_problems, 3) if total_problems else 0,
        "correct_rate": round(correct_count / total_problems, 3) if total_problems else 0,
        "seed": args.seed,
    }
    args.out_manifest.write_text(json.dumps(manifest, indent=2))

    print(f"Wrote {args.n} sessions to {args.out_sessions}")
    print(f"Wrote gold labels   ({len(all_gold)} problems) to {args.out_gold}")
    print(f"Wrote manifest      to {args.out_manifest}")
    print()
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
