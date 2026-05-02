"""
Synthetic student profiles.

Each profile parameterises:
  - p_correct_first        : probability of solving on attempt 1
  - p_correct_per_retry    : per-attempt probability of converging once started
  - max_attempts           : hard cap before giving up (consolidation triggered at 5)
  - p_stuck_per_attempt    : probability that an attempt is an "I don't know" string
  - p_inject_misconception : probability the attempt contains an injected error
  - inter_attempt_seconds  : (mean, sigma) for time between attempts
  - english_drift          : prob of throwing in an English word
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Profile:
    name: str
    p_correct_first: float
    p_correct_per_retry: float
    max_attempts: int
    p_stuck_per_attempt: float
    p_inject_misconception: float
    inter_attempt_mean: float
    inter_attempt_sigma: float
    english_drift: float


PROFILES: dict[str, Profile] = {
    "fast_finisher": Profile(
        name="fast_finisher",
        p_correct_first=0.65,
        p_correct_per_retry=0.7,
        max_attempts=2,
        p_stuck_per_attempt=0.0,
        p_inject_misconception=0.25,
        inter_attempt_mean=12,
        inter_attempt_sigma=4,
        english_drift=0.05,
    ),
    "intermediate_steady": Profile(
        name="intermediate_steady",
        p_correct_first=0.25,
        p_correct_per_retry=0.45,
        max_attempts=4,
        p_stuck_per_attempt=0.05,
        p_inject_misconception=0.7,
        inter_attempt_mean=25,
        inter_attempt_sigma=8,
        english_drift=0.10,
    ),
    "novice_persistent": Profile(
        name="novice_persistent",
        p_correct_first=0.05,
        p_correct_per_retry=0.30,
        max_attempts=5,
        p_stuck_per_attempt=0.10,
        p_inject_misconception=0.85,
        inter_attempt_mean=35,
        inter_attempt_sigma=10,
        english_drift=0.20,
    ),
    "novice_stuck": Profile(
        name="novice_stuck",
        p_correct_first=0.0,
        p_correct_per_retry=0.10,
        max_attempts=5,
        p_stuck_per_attempt=0.30,
        p_inject_misconception=0.95,
        inter_attempt_mean=45,
        inter_attempt_sigma=15,
        english_drift=0.30,
    ),
    "struggler": Profile(
        name="struggler",
        p_correct_first=0.0,
        p_correct_per_retry=0.05,
        max_attempts=5,
        p_stuck_per_attempt=0.50,
        p_inject_misconception=0.95,
        inter_attempt_mean=55,
        inter_attempt_sigma=20,
        english_drift=0.40,
    ),
}


# Mixture used when sampling profiles for the population.
PROFILE_MIX: list[tuple[str, float]] = [
    ("fast_finisher",        0.15),
    ("intermediate_steady",  0.35),
    ("novice_persistent",    0.25),
    ("novice_stuck",         0.15),
    ("struggler",            0.10),
]
