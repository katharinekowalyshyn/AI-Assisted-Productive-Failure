"""
Loads system telemetry for offline evaluation.

Two data sources:
  1. backend/pf_learning_logs.csv     -- one row per attempt
  2. backend/sessions/sess_*.json     -- full conversation + state per session

Everything is normalised into plain Python dicts/lists so the rest of the
eval suite has zero third-party dependencies.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
SESSIONS_DIR = BACKEND / "sessions"
RESULTS_DIR = BACKEND / "results"
LOG_CSV = BACKEND / "pf_learning_logs.csv"


# ---------------------------------------------------------------------------
# Record types
# ---------------------------------------------------------------------------

@dataclass
class AttemptRow:
    timestamp: str
    session_id: str
    problem_id: str
    attempt_number: int
    time_spent_sec: float
    hint_level_used: int
    misconception_tags: list[str]
    final_correct: bool
    reflection_score: float


@dataclass
class Event:
    timestamp: str
    role: str
    event_type: str
    content: str


@dataclass
class Problem:
    """A single problem within a session, reconstructed from the conversation log."""
    session_id: str
    problem_index: int
    task_type: str
    difficulty_score: int
    problem_text: str
    student_attempts: list[str] = field(default_factory=list)
    tutor_feedback: list[str] = field(default_factory=list)
    consolidation: str | None = None
    correct: bool = False
    consolidated: bool = False
    events: list[Event] = field(default_factory=list)


@dataclass
class Session:
    session_id: str
    student_name: str
    problems: list[Problem] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_attempt_rows(csv_path: Path = LOG_CSV) -> list[AttemptRow]:
    rows: list[AttemptRow] = []
    if not csv_path.exists():
        return rows
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append(
                    AttemptRow(
                        timestamp=r.get("timestamp", ""),
                        session_id=r.get("session_id", ""),
                        problem_id=r.get("problem_id", ""),
                        attempt_number=int(r.get("attempt_number") or 0),
                        time_spent_sec=float(r.get("time_spent_sec") or 0),
                        hint_level_used=int(r.get("hint_level_used") or 0),
                        misconception_tags=[
                            t for t in (r.get("misconception_tags") or "").split("|") if t
                        ],
                        final_correct=str(r.get("final_correct")).strip().lower() == "true",
                        reflection_score=float(r.get("reflection_score") or 0),
                    )
                )
            except (TypeError, ValueError):
                continue
    return rows


# ---------------------------------------------------------------------------
# Session JSON loader
# ---------------------------------------------------------------------------

_SESSION_FILE_PATTERN = "sess_*.json"


def _iter_session_files(sessions_dir: Path = SESSIONS_DIR) -> Iterable[Path]:
    """Yield session files. Pattern matches both `sess_*.json` (real)
    and `sess_synth_*.json` (synthetic) since `*` is a wildcard."""
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.glob(_SESSION_FILE_PATTERN))


def _reconstruct_problems(session_id: str, raw: dict) -> list[Problem]:
    """
    Reconstruct a per-problem view from the conversation_history.

    A new problem starts on each event_type == "problem_start". We end the
    current problem on the next problem_start, on a consolidation, or at the
    end of the log. Correctness is inferred from the canonical 'Nice work'
    feedback string used in PFService.handle_attempt.
    """
    history: list[dict] = raw.get("conversation_history", []) or []
    problems: list[Problem] = []

    current: Problem | None = None
    problem_idx = 0

    def start_new(meta_content: str) -> Problem:
        nonlocal problem_idx
        # Parse "New problem started (translation, difficulty 3)."
        task_type = "unknown"
        difficulty = 0
        try:
            inside = meta_content.split("(", 1)[1].rsplit(")", 1)[0]
            parts = [p.strip() for p in inside.split(",")]
            if parts:
                task_type = parts[0]
            if len(parts) > 1 and "difficulty" in parts[1]:
                difficulty = int(parts[1].split()[-1])
        except Exception:
            pass
        problem_idx += 1
        return Problem(
            session_id=session_id,
            problem_index=problem_idx,
            task_type=task_type,
            difficulty_score=difficulty,
            problem_text="",
        )

    for ev in history:
        event_type = ev.get("event_type", "")
        role = ev.get("role", "")
        content = ev.get("content", "")
        timestamp = ev.get("timestamp", "")

        if event_type == "problem_start":
            if current is not None:
                problems.append(current)
            current = start_new(content)
            current.events.append(Event(timestamp, role, event_type, content))
            continue

        if current is None:
            current = Problem(
                session_id=session_id,
                problem_index=0,
                task_type="unknown",
                difficulty_score=0,
                problem_text="",
            )

        current.events.append(Event(timestamp, role, event_type, content))

        if event_type == "attempt" and role == "student":
            current.student_attempts.append(content)
        elif event_type == "feedback" and role == "tutor":
            current.tutor_feedback.append(content)
            if content.startswith("Nice work — that's correct"):
                current.correct = True
        elif event_type == "consolidation" and role == "tutor":
            current.consolidation = content
            current.consolidated = True
        elif event_type == "next_problem":
            problems.append(current)
            current = None

    if current is not None:
        problems.append(current)

    # The last open problem (no next_problem event) keeps whatever state it has.
    # If a session stores a "live" problem in raw["problem"], stitch it in.
    if raw.get("problem") and problems:
        last = problems[-1]
        if not last.problem_text:
            last.problem_text = raw.get("problem", "")
        if not last.task_type or last.task_type == "unknown":
            last.task_type = raw.get("task_type", last.task_type)
        if not last.difficulty_score:
            last.difficulty_score = raw.get("difficulty_score", last.difficulty_score)

    return problems


def load_sessions(sessions_dir: Path = SESSIONS_DIR) -> list[Session]:
    sessions: list[Session] = []
    for path in _iter_session_files(sessions_dir):
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        session_id = path.stem
        student = raw.get("student_name") or "Unknown"
        problems = _reconstruct_problems(session_id, raw)
        sessions.append(Session(session_id=session_id, student_name=student, problems=problems, raw=raw))
    return sessions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def all_problems(sessions: list[Session]) -> list[Problem]:
    out: list[Problem] = []
    for s in sessions:
        out.extend(s.problems)
    return out


def all_tutor_feedback(sessions: list[Session]) -> list[tuple[Problem, str]]:
    out: list[tuple[Problem, str]] = []
    for p in all_problems(sessions):
        for fb in p.tutor_feedback:
            out.append((p, fb))
    return out


if __name__ == "__main__":
    rows = load_attempt_rows()
    sessions = load_sessions()
    print(f"Attempt rows: {len(rows)}")
    print(f"Sessions:     {len(sessions)}")
    print(f"Problems:     {len(all_problems(sessions))}")
