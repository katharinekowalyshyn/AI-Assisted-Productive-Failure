"""
LanguageJury — a three-LLM panel that evaluates student performance against
Productive Failure (PF) pedagogy and recommends a difficulty adjustment for
the next Spanish exercise.

Jurors:
  Melchior  — GPT-4o-mini      (strict, biased toward challenge)
  Casper    — Claude 3 Haiku   (benevolent, protective of student confidence)
  Balthazar — Llama 3.3 70B    (balanced, evidence-based)

All three jurors run concurrently; majority vote determines the verdict.
The jury is invisible to the student — its output only affects the
difficulty score used when generating the next problem.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from llmproxy import LLMProxy

INCREASE = "INCREASE"
MAINTAIN = "MAINTAIN"
DECREASE = "DECREASE"

# Maps difficulty score → human-readable description for jury context
DIFFICULTY_LABELS = {
    1: "very basic A1 (simple vocabulary, present tense only)",
    2: "basic A1 (simple sentences, common verbs: ser, estar, tener, ir)",
    3: "A1/A2 transition (reflexive verbs, adjective agreement, basic questions)",
    4: "A2 (preterite past tense, direct object pronouns)",
    5: "A2+ (compound sentences, indirect pronouns, expressing opinions)",
}


class LanguageJury:
    """
    Three-LLM jury for Productive Failure difficulty calibration.

    Usage:
        jury = LanguageJury()
        verdict = jury.deliberate(
            problem="...",
            task_type="translation",
            difficulty_score=2,
            attempts=["hola mundo", "hola el mundo"],
            session_id="sess_123",
        )
        # verdict is one of: "INCREASE", "MAINTAIN", "DECREASE"
    """

    def __init__(self) -> None:
        self.client = LLMProxy()

    # ------------------------------------------------------------------
    # Query builder
    # ------------------------------------------------------------------

    def _build_query(
        self,
        problem: str,
        task_type: str,
        difficulty_score: int,
        attempts: List[str],
    ) -> str:
        difficulty_label = DIFFICULTY_LABELS.get(difficulty_score, "A1/A2")
        attempts_text = (
            "\n".join(f"  Attempt {i + 1}: {a}" for i, a in enumerate(attempts))
            if attempts
            else "  (no attempts submitted)"
        )

        return f"""You are evaluating a university student's Spanish language exercise for Productive Failure (PF) calibration.

TASK TYPE: {task_type}
CURRENT DIFFICULTY: {difficulty_score}/5 — {difficulty_label}
PROBLEM GIVEN: {problem}

STUDENT'S ATTEMPTS:
{attempts_text}
TOTAL ATTEMPTS: {len(attempts)}

PRODUCTIVE FAILURE PRINCIPLES:
- PF requires students to STRUGGLE productively — multiple attempts, exploring ideas, making errors
- Too easy  (solved in 1–2 attempts, minimal effort) → INCREASE difficulty
- Good zone (3–6 attempts, visible exploration, some partial progress) → MAINTAIN difficulty
- Too hard  (7+ attempts with no visible improvement, increasing confusion, giving up) → DECREASE difficulty

Based on these principles, should the next problem be harder, the same, or easier?

Respond with EXACTLY:
VERDICT: [INCREASE|MAINTAIN|DECREASE]
REASON: [one sentence]"""

    # ------------------------------------------------------------------
    # Individual jurors
    # ------------------------------------------------------------------

    def _call_melchior(self, query: str, eval_id: str) -> dict:
        """GPT-4o-mini — strict, biased toward challenge."""
        return self.client.generate(
            model="4o-mini",
            system=(
                "You are a strict academic evaluator specializing in second-language acquisition. "
                "You believe students grow fastest when consistently pushed beyond their comfort zone. "
                "Lean toward INCREASE unless there are clear signs the student is overwhelmed. "
                "Be concise and decisive."
            ),
            query=query,
            temperature=0.3,
            lastk=0,
            session_id=f"jury_melchior_{eval_id}",
            rag_usage=False,
        )

    def _call_casper(self, query: str, eval_id: str) -> dict:
        """Claude 3 Haiku — benevolent, protective of student confidence."""
        return self.client.generate(
            model="us.anthropic.claude-3-haiku-20240307-v1:0",
            system=(
                "You are a supportive language learning coach who prioritises student motivation. "
                "You believe sustained engagement matters more than short-term challenge. "
                "Lean toward DECREASE if there are signs of frustration or lack of progress. "
                "Be concise and decisive."
            ),
            query=query,
            temperature=0.3,
            lastk=0,
            session_id=f"jury_casper_{eval_id}",
            rag_usage=False,
        )

    def _call_balthazar(self, query: str, eval_id: str) -> dict:
        """Llama 3.3 70B — balanced, evidence-based."""
        return self.client.generate(
            model="us.meta.llama3-3-70b-instruct-v1:0",
            system=(
                "You are an impartial evaluator grounded in second-language acquisition research. "
                "Evaluate the student's performance objectively based only on the evidence provided. "
                "Recommend INCREASE, MAINTAIN, or DECREASE purely from what the attempts show. "
                "Be concise and decisive."
            ),
            query=query,
            temperature=0.3,
            lastk=0,
            session_id=f"jury_balthazar_{eval_id}",
            rag_usage=False,
        )

    # ------------------------------------------------------------------
    # Parsing + deliberation
    # ------------------------------------------------------------------

    def _parse_verdict(self, response: dict) -> str:
        """Extract INCREASE / MAINTAIN / DECREASE from a juror response."""
        text = response.get("result", "").upper()
        if INCREASE in text:
            return INCREASE
        if DECREASE in text:
            return DECREASE
        return MAINTAIN  # default on ambiguous / failed response

    def deliberate(
        self,
        problem: str,
        task_type: str,
        difficulty_score: int,
        attempts: List[str],
        session_id: str,
    ) -> str:
        """
        Run all three jurors concurrently, collect verdicts, return majority.

        Returns one of: "INCREASE", "MAINTAIN", "DECREASE"
        Falls back to "MAINTAIN" on any juror failure.
        """
        eval_id = f"{session_id}_{int(time.time())}"
        query = self._build_query(problem, task_type, difficulty_score, attempts)

        callers = {
            "Melchior": self._call_melchior,
            "Casper": self._call_casper,
            "Balthazar": self._call_balthazar,
        }

        verdicts: List[str] = []

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(fn, query, eval_id): name
                for name, fn in callers.items()
            }
            for future in as_completed(futures, timeout=45):
                name = futures[future]
                try:
                    verdict = self._parse_verdict(future.result())
                    print(f"[Jury] {name}: {verdict}")
                    verdicts.append(verdict)
                except Exception as exc:
                    print(f"[Jury] {name} failed: {exc} — defaulting to MAINTAIN")
                    verdicts.append(MAINTAIN)

        counts = {
            INCREASE: verdicts.count(INCREASE),
            MAINTAIN: verdicts.count(MAINTAIN),
            DECREASE: verdicts.count(DECREASE),
        }
        final = max(counts, key=counts.get)
        print(f"[Jury] Final verdict: {final}  (tally: {counts})")
        return final
