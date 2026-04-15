"""
PFService — core Productive Failure logic for Spanish A1/A2 language tutoring.

Session state shape:
    sessions[session_id] = {
        "problem": str,
        "task_type": "translation" | "error_correction" | "conversation_completion",
        "difficulty_score": int (1–5, invisible to student),
        "attempts": List[str],
        "uploaded_content": str,
        "problems_completed": int,
    }

Difficulty scale:
    1 — very basic A1 (greetings, colours, numbers, cognates)
    2 — basic A1     (present tense, ser/estar/tener/ir/querer)
    3 — A1/A2        (reflexive verbs, adjective agreement, basic questions)
    4 — A2           (preterite past tense, direct object pronouns)
    5 — A2+          (compound sentences, indirect pronouns, opinions)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from services.jury import LanguageJury
from instructor.service import instructor_service, SHARED_GRAMMAR_SESSION_ID
from llmproxy import LLMProxy
from core.config import settings
from .analytics import AnalyticsLogger


# ---------------------------------------------------------------------------
# Prompt tables — keyed by (task_type, difficulty_score)
# ---------------------------------------------------------------------------

_DIFFICULTY_LABELS = {
    1: "very basic A1 Spanish — simple vocabulary, present tense, cognates",
    2: "basic A1 Spanish — simple sentences, high-frequency verbs (ser, estar, tener, ir, querer)",
    3: "A1/A2 Spanish — reflexive verbs, adjective agreement, basic question words",
    4: "A2 Spanish — preterite past tense, direct object pronouns",
    5: "A2+ Spanish — compound sentences, indirect pronouns, expressing opinions",
}

_TASK_GENERATION_PROMPTS: dict[str, dict[int, str]] = {
    "translation": {
        1: (
            "Create a very simple English sentence (max 6 words) for a complete beginner to translate into Spanish. "
            "Use only: greetings, days of the week, numbers 1–10, colours, basic food, or family members. "
            "Present tense only."
        ),
        2: (
            "Create a simple English sentence (max 8 words) for an A1 learner to translate into Spanish. "
            "Use only present tense and common verbs: to be, to have, to want, to go, to like."
        ),
        3: (
            "Create an English sentence (max 10 words) for translation into Spanish at A1/A2 level. "
            "Include a reflexive verb, a question word, or a possessive adjective."
        ),
        4: (
            "Create an English sentence (max 10 words) for an A2 learner to translate into Spanish. "
            "The sentence should require the preterite (simple past) tense."
        ),
        5: (
            "Create a moderately complex English sentence (max 12 words) for an A2+ learner to translate into Spanish. "
            "Include an indirect object pronoun, a compound clause, or an opinion phrase."
        ),
    },
    "error_correction": {
        1: (
            "Write a short Spanish sentence (5–7 words) with ONE obvious error: "
            "a wrong subject pronoun or a basic present-tense verb conjugation mistake."
        ),
        2: (
            "Write a short Spanish sentence (6–8 words) with ONE error: "
            "a noun–adjective gender disagreement or a ser/estar confusion."
        ),
        3: (
            "Write a Spanish sentence (8–10 words) with ONE or TWO errors: "
            "incorrect reflexive pronoun placement or wrong article gender."
        ),
        4: (
            "Write a Spanish sentence (8–12 words) with TWO errors: "
            "a preterite conjugation mistake and a direct object pronoun error."
        ),
        5: (
            "Write a Spanish sentence (10–14 words) with TWO or THREE errors: "
            "mixing pronoun placement, tense, and word order."
        ),
    },
    "conversation_completion": {
        1: (
            "Write a single Spanish conversation opener by Person A — a simple greeting or "
            "'¿Cómo te llamas?' — that a student (Person B) can respond to with 1–3 words."
        ),
        2: (
            "Write a short Spanish exchange where Person A asks a simple question about daily life "
            "(likes, routine, or family). The student plays Person B and must respond in 1–2 sentences."
        ),
        3: (
            "Write a Spanish exchange where Person A describes something and then asks the student (Person B) "
            "a follow-up question requiring reflexive verbs or descriptive adjectives in the answer."
        ),
        4: (
            "Write a Spanish exchange where Person A describes a past event using the preterite. "
            "The student (Person B) must respond with a relevant follow-up also in the preterite."
        ),
        5: (
            "Write a Spanish exchange where Person A expresses an opinion using 'porque'. "
            "The student (Person B) must agree, disagree, or expand with their own reason."
        ),
    },
}

_TASK_FORMAT_INSTRUCTIONS: dict[str, str] = {
    "translation": (
        "Format your output exactly as:\n"
        "English: [the sentence the student must translate]\n"
        "(Do NOT include any Spanish, solution, or hint.)"
    ),
    "error_correction": (
        "Format your output exactly as:\n"
        "Find and correct the error(s): [the Spanish sentence containing the error(s)]\n"
        "(Do NOT include the corrected version.)"
    ),
    "conversation_completion": (
        "Format your output exactly as:\n"
        "Complete the conversation:\n"
        "A: [Spanish line]\n"
        "B: ___\n"
        "(Do NOT complete B's line.)"
    ),
}

_HINT_INSTRUCTIONS: dict[int, str] = {
    1: (
        "Give a very gentle hint — remind the student of a relevant grammar rule "
        "without mentioning the answer. (e.g. 'Remember that adjectives agree in gender…')"
    ),
    2: (
        "Give a structural hint — explain the pattern needed "
        "(e.g. 'This verb is reflexive' or 'This sentence uses the preterite tense') "
        "without solving the problem."
    ),
    3: (
        "Give a more direct hint — show the student the first word or first phrase of the answer "
        "and briefly explain why that form is correct."
    ),
    4: (
        "Give a near-complete scaffold — show the sentence structure with key blanks filled in, "
        "or provide the correct form of the single most challenging element."
    ),
}

MAX_ATTEMPTS = 5


class PFService:
    def __init__(self):
        self.llm = LLMProxy()
        self.instructor = instructor_service
        self.jury = LanguageJury()
        self.analytics = AnalyticsLogger()
        self.sessions_dir = Path("./sessions")
        self.results_dir = Path("./results")
        self.sessions_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)
        self.sessions_file = self.sessions_dir / "sessions.json"
        self.sessions: dict = self._load_sessions()
        self.rag_session_id = SHARED_GRAMMAR_SESSION_ID

    # ------------------------------------------------------------------
    # Start (or restart) a problem
    # ------------------------------------------------------------------

    def start_session(
        self,
        session_id: str,
        task_type: str = "translation",
        difficulty_score: int | None = None,
        student_name: str | None = None,
    ) -> str:
        """Generate a Spanish exercise at the given difficulty.

        If difficulty_score is None, the current session's score is used,
        or 2 (basic A1) for brand-new sessions.
        """
        uploaded_content = self.instructor.get_session_material(session_id)

        # Resolve difficulty
        if difficulty_score is None:
            difficulty_score = self.sessions.get(session_id, {}).get("difficulty_score", 2)
        difficulty_score = max(1, min(5, difficulty_score))

        # Build generation prompt
        task_prompt = (
            _TASK_GENERATION_PROMPTS
            .get(task_type, _TASK_GENERATION_PROMPTS["translation"])
            .get(difficulty_score, _TASK_GENERATION_PROMPTS["translation"][2])
        )
        format_instruction = _TASK_FORMAT_INSTRUCTIONS.get(
            task_type, _TASK_FORMAT_INSTRUCTIONS["translation"]
        )
        context = (
            f"Reference this uploaded material if relevant: {uploaded_content}"
            if uploaded_content
            else ""
        )

        prompt = f"""{context}

You are generating a Spanish exercise for a university student at {_DIFFICULTY_LABELS[difficulty_score]}.

Task specification: {task_prompt}

{format_instruction}

Generate the exercise now:"""

        try:
            response = self.llm.generate(
                model=settings.llm_model,
                system=(
                    "You are an expert Spanish exercise designer for beginner university students. "
                    "Create clear, unambiguous exercises. Never include the answer or any hint."
                ),
                query=prompt,
                session_id=self.rag_session_id,
                temperature=0.8,
                rag_usage=True,
            )
            problem = response.get("result", "English: I like to eat tacos.")
        except Exception as exc:
            print(f"[PFService] Problem generation failed: {exc}")
            problem = f"Problem generation failed: {exc}"

        previous_session = self.sessions.get(session_id, {})
        problems_completed = previous_session.get("problems_completed", 0)
        existing_attempts_total = previous_session.get("total_attempts", 0)
        existing_hints_total = previous_session.get("hints_used", 0)
        existing_conversation = previous_session.get("conversation_history", [])

        self.sessions[session_id] = {
            "problem": problem,
            "task_type": task_type,
            "difficulty_score": difficulty_score,
            "attempts": [],
            "uploaded_content": uploaded_content,
            "problems_completed": problems_completed,
            "student_name": student_name or previous_session.get("student_name", "Unknown Student"),
            "problem_id": f"prob_{uuid4().hex[:10]}",
            "problem_started_at": datetime.utcnow().isoformat(),
            "total_attempts": existing_attempts_total,
            "hints_used": existing_hints_total,
            "conversation_history": existing_conversation,
            "session_started_at": previous_session.get("session_started_at", datetime.utcnow().isoformat()),
        }
        self._append_event(
            session_id,
            role="system",
            content=f"New problem started ({task_type}, difficulty {difficulty_score}).",
            event_type="problem_start",
        )
        self._persist_session(session_id)
        self._persist_result_snapshot(session_id)

        return problem

    # ------------------------------------------------------------------
    # Evaluate a student attempt
    # ------------------------------------------------------------------

    def handle_attempt(self, session_id: str, answer: str) -> dict:
        """Evaluate a student attempt and optionally trigger consolidation."""
        if session_id not in self.sessions:
            return {
                "reply": "Session not found. Please start a new problem.",
                "is_correct": False,
                "can_advance": False,
                "show_consolidation": False,
            }

        session = self.sessions[session_id]
        problem = session["problem"]
        task_type = session.get("task_type", "translation")
        uploaded_content = session.get("uploaded_content", "")

        session["attempts"].append(answer)
        session["total_attempts"] = session.get("total_attempts", 0) + 1
        attempt_number = len(session["attempts"])
        self._append_event(session_id, role="student", content=answer, event_type="attempt")

        context = (
            f"Reference this uploaded material for feedback: {uploaded_content}"
            if uploaded_content
            else ""
        )

        task_context_map = {
            "translation": "The student is attempting to translate an English sentence into Spanish.",
            "error_correction": "The student is trying to find and correct errors in a Spanish sentence.",
            "conversation_completion": "The student is completing a Spanish conversation.",
        }
        task_context = task_context_map.get(task_type, "The student is working on a Spanish language task.")
        answer_lower = answer.lower()
        stuck_signal = any(token in answer_lower for token in ["i dont know", "i don't know", "no", "idk"])

        adaptive_scaffold = (
            "- Keep guidance light and ask one guiding question.\n"
            "- Do not reveal the full answer."
        )
        if task_type == "translation":
            if attempt_number >= 1:
                adaptive_scaffold = (
                    "- Give one concrete scaffold (for example, first letter of an important missing word).\n"
                    "- Ask one short follow-up question.\n"
                    "- Do not reveal the full answer."
                )
            if attempt_number >= 2 or stuck_signal:
                adaptive_scaffold = (
                    "- Give stronger scaffold: provide ONE key Spanish word the student needs.\n"
                    "- Also provide the first letter of another missing word.\n"
                    "- Keep it brief and still do not give the full sentence."
                )
            if attempt_number >= 4:
                adaptive_scaffold = (
                    "- Give maximal scaffold without full solution: provide 2 key words plus one grammar/order reminder.\n"
                    "- Keep it to 2-3 sentences; do not provide the complete translated sentence."
                )

        pf_prompt = f"""{context}

{task_context}

Problem: {problem}
Student attempt #{attempt_number}: {answer}

You are a supportive Spanish tutor using Productive Failure pedagogy.
Rules:
- DO NOT provide the correct answer, translation, or corrected sentence.
- Acknowledge anything correct or partially correct in their attempt.
- Ask one guiding question to help them think further.
- Respond entirely in English — students are A1/A2 level.
- Keep your response to 2–3 sentences maximum.
- Adaptive support based on attempt number:
{adaptive_scaffold}

Feedback:"""

        correctness_rules = """
Grading rules:
- Be meaning-focused, not literal-wording-focused.
- Accept valid Spanish variants, including omitted subject pronouns (e.g., 'quiero' vs 'yo quiero').
- Ignore capitalization, punctuation, and minor spacing.
- For translation tasks, accept equivalent grammar/word order if meaning is correct.
- Do not mark correct answers as wrong just because they are shorter.
"""
        if task_type == "translation":
            correctness_rules += """
Translation-specific examples:
- If prompt is "I want to go to the park.", "quiero ir al parque" IS correct.
- "yo quiero ir al parque" is also correct.
"""

        correctness_prompt = f"""
Problem: {problem}
Task type: {task_type}
Student answer: {answer}

Determine whether the student's answer is acceptably correct.
{correctness_rules}
Respond ONLY as valid JSON:
{{
  "is_correct": true or false,
  "reason": "one short sentence"
}}
"""

        try:
            correctness_response = self.llm.generate(
                model=settings.llm_model,
                system="You are a strict Spanish grading assistant. Return JSON only.",
                query=correctness_prompt,
                session_id=self.rag_session_id,
                temperature=0.0,
                rag_usage=True,
            )
            is_correct = self._parse_is_correct(correctness_response.get("result", ""))

            if is_correct:
                reply = (
                    "Nice work - that's correct. Click Next Exercise when you're ready for a new one."
                )
            else:
                response = self.llm.generate(
                    model=settings.llm_model,
                    system=settings.llm_system_prompt,
                    query=pf_prompt,
                    session_id=self.rag_session_id,
                    temperature=0.5,
                    rag_usage=True,
                )
                reply = response.get("result", "Good effort! What part are you most unsure about?")
            show_consolidation = (not is_correct) and attempt_number >= MAX_ATTEMPTS
            consolidation = None
            can_advance = is_correct or show_consolidation

            if show_consolidation:
                consolidation = self._build_consolidation(session_id, answer)
                reply = (
                    "You've put in strong effort. Let's consolidate this one now so you can move on."
                )

            self._append_event(session_id, role="tutor", content=reply, event_type="feedback")
            if consolidation:
                self._append_event(
                    session_id,
                    role="tutor",
                    content=f"Consolidation answer: {consolidation}",
                    event_type="consolidation",
                )

            self.analytics.log_attempt(
                session_id=session_id,
                problem_id=session.get("problem_id", ""),
                attempt_number=attempt_number,
                time_spent=self._time_spent_for_problem(session),
                hint_level=0,
                misconceptions=[],
                correct=is_correct,
                reflection_score=0,
            )
            self._persist_session(session_id)
            self._persist_result_snapshot(session_id)

            return {
                "reply": reply,
                "is_correct": is_correct,
                "can_advance": can_advance,
                "show_consolidation": show_consolidation,
                "consolidation": consolidation,
                "attempts_used": attempt_number,
                "max_attempts": MAX_ATTEMPTS,
            }
        except Exception as exc:
            print(f"[PFService] Attempt evaluation failed: {exc}")
            return {
                "reply": f"Evaluation failed: {exc}",
                "is_correct": False,
                "can_advance": False,
                "show_consolidation": False,
            }

    # ------------------------------------------------------------------
    # Hints
    # ------------------------------------------------------------------

    def get_hint(self, session_id: str, problem_text: str, hint_level: int) -> str:
        """Return a scaffolded hint scaled to hint_level (1–4)."""
        if session_id not in self.sessions:
            return "Session not found."

        session = self.sessions[session_id]
        uploaded_content = session.get("uploaded_content", "")
        task_type = session.get("task_type", "translation")

        context = (
            f"Reference this uploaded material: {uploaded_content}"
            if uploaded_content
            else ""
        )
        hint_instruction = _HINT_INSTRUCTIONS.get(hint_level, _HINT_INSTRUCTIONS[1])

        hint_prompt = f"""{context}

Task type: {task_type}
Problem: {problem_text}
Hint level: {hint_level}/4

{hint_instruction}

Respond in English. Do not give the full solution."""

        try:
            response = self.llm.generate(
                model=settings.llm_model,
                system=(
                    "You are a Spanish language tutor providing scaffolded hints. "
                    "Guide students toward the answer without revealing it."
                ),
                query=hint_prompt,
                session_id=self.rag_session_id,
                temperature=0.5,
                rag_usage=True,
            )
            hint_text = response.get(
                "result",
                "Think about the verb conjugation pattern. What tense is being used?",
            )
            session["hints_used"] = session.get("hints_used", 0) + 1
            self._append_event(session_id, role="tutor", content=hint_text, event_type="hint")
            self._persist_session(session_id)
            self._persist_result_snapshot(session_id)
            return hint_text
        except Exception as exc:
            print(f"[PFService] Hint generation failed: {exc}")
            return f"Hint generation failed: {exc}"

    # ------------------------------------------------------------------
    # Next problem (jury-calibrated)
    # ------------------------------------------------------------------

    def next_problem(self, session_id: str, task_type: str | None = None) -> str:
        """
        Evaluate the completed problem via the LLM jury, adjust the internal
        difficulty score, and return the next generated problem.

        The jury verdict and difficulty adjustment are never exposed to the student.
        """
        if session_id not in self.sessions:
            return "Session not found. Please start a new problem."

        session = self.sessions[session_id]
        current_difficulty = session.get("difficulty_score", 2)
        attempts = session.get("attempts", [])
        problem = session.get("problem", "")
        current_task_type = session.get("task_type", "translation")
        next_task_type = task_type or current_task_type

        # Run jury
        try:
            verdict = self.jury.deliberate(
                problem=problem,
                task_type=current_task_type,
                difficulty_score=current_difficulty,
                attempts=attempts,
                session_id=session_id,
            )
            adjustment = {
                "INCREASE": +1,
                "MAINTAIN":  0,
                "DECREASE": -1,
            }.get(verdict, 0)
            next_difficulty = max(1, min(5, current_difficulty + adjustment))
            print(f"[PFService] difficulty {current_difficulty} → {next_difficulty} (jury: {verdict})")
        except Exception as exc:
            print(f"[PFService] Jury failed, keeping difficulty: {exc}")
            next_difficulty = current_difficulty

        # Increment completed-problem counter
        session["problems_completed"] = session.get("problems_completed", 0) + 1
        self._append_event(session_id, role="system", content="Advanced to next problem.", event_type="next_problem")
        self._persist_session(session_id)
        self._persist_result_snapshot(session_id)

        return self.start_session(
            session_id=session_id,
            task_type=next_task_type,
            difficulty_score=next_difficulty,
        )

    def _load_sessions(self) -> dict:
        if not self.sessions_file.exists():
            return {}
        try:
            return json.loads(self.sessions_file.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[PFService] Could not load persisted sessions: {exc}")
            return {}

    def _persist_session(self, session_id: str):
        self.sessions_file.write_text(json.dumps(self.sessions, indent=2), encoding="utf-8")
        session_path = self.sessions_dir / f"{session_id}.json"
        session_path.write_text(json.dumps(self.sessions.get(session_id, {}), indent=2), encoding="utf-8")

    def _persist_result_snapshot(self, session_id: str):
        session = self.sessions.get(session_id, {})
        student_name = session.get("student_name", "Unknown Student")
        payload = {
            "session_id": session_id,
            "student_name": student_name,
            "task_type": session.get("task_type"),
            "difficulty_score": session.get("difficulty_score"),
            "problem_id": session.get("problem_id"),
            "problem": session.get("problem"),
            "attempts_current_problem": len(session.get("attempts", [])),
            "stats": {
                "total_attempts": session.get("total_attempts", 0),
                "hints_used": session.get("hints_used", 0),
                "problems_completed": session.get("problems_completed", 0),
                "session_started_at": session.get("session_started_at"),
            },
            "conversation_history": session.get("conversation_history", []),
            "last_updated_at": datetime.utcnow().isoformat(),
        }
        safe_name = self._safe_filename_component(student_name)
        result_path = self.results_dir / f"{safe_name}__{session_id}.json"
        result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _safe_filename_component(self, value: str) -> str:
        cleaned = (value or "unknown_user").strip().lower()
        cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
        cleaned = cleaned.strip("_")
        return cleaned or "unknown_user"

    def list_history_for_student(self, student_name: str) -> list[dict]:
        safe_name = self._safe_filename_component(student_name)
        entries: list[dict] = []
        for path in self.results_dir.glob(f"{safe_name}__*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entries.append(
                    {
                        "session_id": data.get("session_id"),
                        "student_name": data.get("student_name"),
                        "task_type": data.get("task_type"),
                        "difficulty_score": data.get("difficulty_score"),
                        "stats": data.get("stats", {}),
                        "last_updated_at": data.get("last_updated_at"),
                    }
                )
            except Exception as exc:
                print(f"[PFService] Skipping unreadable history file {path.name}: {exc}")

        entries.sort(key=lambda item: item.get("last_updated_at") or "", reverse=True)
        return entries

    def get_history_session(self, session_id: str, student_name: str | None = None) -> dict | None:
        if student_name:
            safe_name = self._safe_filename_component(student_name)
            candidate = self.results_dir / f"{safe_name}__{session_id}.json"
            if candidate.exists():
                try:
                    return json.loads(candidate.read_text(encoding="utf-8"))
                except Exception:
                    return None

        for path in self.results_dir.glob(f"*__{session_id}.json"):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
        return None

    def _append_event(self, session_id: str, role: str, content: str, event_type: str):
        session = self.sessions.get(session_id)
        if not session:
            return
        session.setdefault("conversation_history", []).append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "role": role,
                "event_type": event_type,
                "content": content,
            }
        )

    def _parse_is_correct(self, raw_text: str) -> bool:
        try:
            parsed = json.loads(raw_text)
            return bool(parsed.get("is_correct", False))
        except Exception:
            normalized = raw_text.lower()
            return '"is_correct": true' in normalized or "is correct" in normalized

    def _build_consolidation(self, session_id: str, student_answer: str) -> str:
        session = self.sessions[session_id]
        prompt = f"""
Problem: {session.get('problem', '')}
Student final attempt: {student_answer}
Task type: {session.get('task_type', 'translation')}

Provide:
1) Correct answer
2) Brief explanation (2-4 sentences, in English)

Label exactly as:
Correct answer:
Why this is correct:
"""
        response = self.llm.generate(
            model=settings.llm_model,
            system="You are a Spanish tutor giving concise consolidation after productive struggle.",
            query=prompt,
            session_id=self.rag_session_id,
            temperature=0.3,
            rag_usage=True,
        )
        return response.get("result", "Correct answer unavailable.")

    def _time_spent_for_problem(self, session: dict) -> int:
        started = session.get("problem_started_at")
        if not started:
            return 0
        try:
            start_dt = datetime.fromisoformat(started)
            return max(0, int((datetime.utcnow() - start_dt).total_seconds()))
        except Exception:
            return 0
