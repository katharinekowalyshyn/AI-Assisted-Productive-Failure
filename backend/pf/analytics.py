import csv
from datetime import datetime
from pathlib import Path


class AnalyticsLogger:
    def __init__(self):
        self.log_file = Path("pf_learning_logs.csv")
        self._ensure_file()

    def _ensure_file(self):
        if not self.log_file.exists():
            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "session_id",
                    "problem_id",
                    "attempt_number",
                    "time_spent_sec",
                    "hint_level_used",
                    "misconception_tags",
                    "final_correct",
                    "reflection_score"
                ])

    def log_attempt(
        self,
        session_id,
        problem_id,
        attempt_number,
        time_spent,
        hint_level,
        misconceptions,
        correct,
        reflection_score
    ):
        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.utcnow().isoformat(),
                session_id,
                problem_id,
                attempt_number,
                time_spent,
                hint_level,
                "|".join(misconceptions),
                correct,
                reflection_score
            ])