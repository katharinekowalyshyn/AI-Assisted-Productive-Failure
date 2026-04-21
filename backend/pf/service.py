"""
PFService — Productive Failure logic for Spanish A1/A2 language tutoring.

PF Workflow
-----------
Struggle phase  (attempts 1 … MAX_ATTEMPTS-1):
  1. Student submits attempt
  2. Tutor acknowledges motivationally, then asks ONE generative question
     about what the student was thinking (to surface their reasoning)
  3. Tutor prompts for a second / next attempt
  4. Repeat

Consolidation phase  (triggered after MAX_ATTEMPTS without a correct answer):
  Tutor compares ALL prior attempts to the canonical solution, names what
  was right and what was wrong in the student's approach, then reveals the
  correct answer with a brief explanation.

Hints: removed — the struggle phase itself provides adaptive scaffolding
through generative questioning rather than domain-specific hint buttons.

Session state shape:
    sessions[session_id] = {
        "problem": str,
        "task_type": "translation" | "error_correction" | "conversation_completion",
        "difficulty_score": int (1–5, invisible to student),
        "attempts": List[str],
        "uploaded_content": str,
        "problems_completed": int,
        "conversation_history": List[dict],
        ...
    }
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
# Difficulty labels
# ---------------------------------------------------------------------------

_DIFFICULTY_LABELS = {
    1: "very basic A1 Spanish — simple vocabulary, present tense, cognates",
    2: "basic A1 Spanish — simple sentences, high-frequency verbs (ser, estar, tener, ir, querer)",
    3: "A1/A2 Spanish — reflexive verbs, adjective agreement, basic question words",
    4: "A2 Spanish — preterite past tense, direct object pronouns",
    5: "A2+ Spanish — compound sentences, indirect pronouns, expressing opinions",
}

# ---------------------------------------------------------------------------
# Exercise generation prompts
# ---------------------------------------------------------------------------

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
        """Generate a Spanish exercise at the given difficulty."""
        uploaded_content = self.instructor.get_session_material(session_id)

        if difficulty_score is None:
            difficulty_score = self.sessions.get(session_id, {}).get("difficulty_score", 2)
        difficulty_score = max(1, min(5, difficulty_score))

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
    # Evaluate a student attempt  (core PF loop)
    # ------------------------------------------------------------------

    def handle_attempt(self, session_id: str, answer: str) -> dict:
        """
        Struggle phase: acknowledge + generative question + prompt retry.
        Consolidation phase: triggered after MAX_ATTEMPTS, compares all
        attempts to canonical solution and explains what was right/wrong.
        """
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

        # ── 1. Check correctness ──────────────────────────────────────
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
        except Exception as exc:
            print(f"[PFService] Correctness check failed: {exc}")
            is_correct = False

        # ── 2. Build reply ────────────────────────────────────────────
        show_consolidation = (not is_correct) and attempt_number >= MAX_ATTEMPTS
        consolidation = None
        can_advance = is_correct or show_consolidation

        if is_correct:
            reply = (
                "Nice work — that's correct! Click 'Next Exercise' when you're ready to continue."
            )

        elif show_consolidation:
            # ── Consolidation phase ───────────────────────────────────
            consolidation = self._build_consolidation(session_id, answer)
            reply = (
                "You've put in real effort on this one — let's review it together now."
            )

        else:
            # ── Struggle phase: generative questioning ────────────────
            reply = self._build_struggle_response(
                session=session,
                problem=problem,
                task_type=task_type,
                uploaded_content=uploaded_content,
                answer=answer,
                attempt_number=attempt_number,
            )

        # ── 3. Persist ────────────────────────────────────────────────
        self._append_event(session_id, role="tutor", content=reply, event_type="feedback")
        if consolidation:
            self._append_event(
                session_id,
                role="tutor",
                content=f"Consolidation: {consolidation}",
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

    # ------------------------------------------------------------------
    # Struggle-phase response builder
    # ------------------------------------------------------------------

    def _build_struggle_response(
        self,
        session: dict,
        problem: str,
        task_type: str,
        uploaded_content: str,
        answer: str,
        attempt_number: int,
    ) -> str:
        """
        Build a tutor message that:
          1. Acknowledges the attempt motivationally (referencing this specific attempt)
          2. Asks ONE generative question about the student's reasoning
          3. Prompts them to try again
        Context from all prior attempts in this problem is included so the
        tutor never repeats itself.
        """
        # Summarise prior attempts for context
        prior_attempts = session.get("attempts", [])[:-1]  # exclude current
        prior_summary = ""
        if prior_attempts:
            formatted = "\n".join(
                f"  Attempt {i + 1}: {a}" for i, a in enumerate(prior_attempts)
            )
            prior_summary = f"\nThe student's previous attempts on this problem were:\n{formatted}\n"

        context = (
            f"Reference this uploaded material if relevant: {uploaded_content}\n\n"
            if uploaded_content
            else ""
        )

        task_context_map = {
            "translation": "The student is translating an English sentence into Spanish.",
            "error_correction": "The student is identifying and correcting errors in a Spanish sentence.",
            "conversation_completion": "The student is completing a Spanish conversation.",
        }
        task_context = task_context_map.get(task_type, "The student is working on a Spanish task.")

        stuck_signal = any(
            token in answer.lower()
            for token in ["i dont know", "i don't know", "no idea", "idk"]
        )

        if stuck_signal:
            extra_instruction = (
                "The student seems stuck. Ask a very targeted question that focuses on "
                "just ONE specific element of the problem (e.g., the verb ending, the article, "
                "the word order) to get them moving. Keep it to 2 sentences."
            )
        elif attempt_number == 1:
            extra_instruction = (
                "This is their first attempt. Acknowledge what they tried, ask them what they "
                "were thinking when they chose that form/word, and invite a second try."
            )
        else:
            extra_instruction = (
                "Acknowledge any progress since previous attempts (even tiny improvements). "
                "Ask ONE new generative question that probes a different aspect of the problem "
                "from questions you have already asked. Do NOT repeat a question from earlier turns."
            )

        pf_prompt = f"""{context}{task_context}

Problem: {problem}
{prior_summary}
Current attempt (attempt #{attempt_number}): {answer}

You are a supportive Spanish tutor using Productive Failure pedagogy.

Your response MUST:
1. Open with brief motivational acknowledgement of THIS specific attempt (1 sentence, note what is right or partially right if anything)
2. Ask ONE generative question about what the student was thinking — probe their reasoning, not just the answer (e.g. "Why did you choose that ending?", "What tense do you think is needed here?")
3. End with a short prompt to try again

Rules:
- NEVER give the correct answer, translation, or corrected sentence
- Respond entirely in English
- Keep the whole response to 3 sentences maximum
- Do NOT repeat questions already asked in prior turns
{extra_instruction}

Tutor response:"""

        try:
            response = self.llm.generate(
                model=settings.llm_model,
                system=settings.llm_system_prompt,
                query=pf_prompt,
                session_id=self.rag_session_id,
                temperature=0.5,
                rag_usage=True,
            )
            return response.get("result", "Good effort! What were you thinking when you wrote that? Give it another go.")
        except Exception as exc:
            print(f"[PFService] Struggle response failed: {exc}")
            return "Good effort — what were you thinking here? Give it another try!"

    # ------------------------------------------------------------------
    # Consolidation builder
    # ------------------------------------------------------------------

    def _build_consolidation(self, session_id: str, final_answer: str) -> str:
        """
        Compare ALL student attempts to the canonical solution.
        Name specifically what was right and what was wrong, then reveal
        the correct answer with a brief explanation.
        """
        session = self.sessions[session_id]
        all_attempts = session.get("attempts", [])
        attempts_formatted = "\n".join(
            f"  Attempt {i + 1}: {a}" for i, a in enumerate(all_attempts)
        )

        prompt = f"""
Problem: {session.get('problem', '')}
Task type: {session.get('task_type', 'translation')}

All student attempts:
{attempts_formatted}

You are a Spanish tutor closing the productive struggle phase with a consolidation.

Write a consolidation message (in English, 4–6 sentences) that:
1. Briefly notes what the student got RIGHT across their attempts (be specific — name the words/forms they used correctly)
2. Clearly explains what was WRONG or missing and why (name the specific error pattern)
3. Reveals the correct answer, labelled exactly as: Correct answer:
4. Gives a short memorable explanation (1–2 sentences) of the key grammar rule

Do NOT be vague. Reference the student's actual attempts by number if helpful.
"""
        try:
            response = self.llm.generate(
                model=settings.llm_model,
                system="You are a Spanish tutor giving clear, specific consolidation feedback after productive struggle.",
                query=prompt,
                session_id=self.rag_session_id,
                temperature=0.3,
                rag_usage=True,
            )
            return response.get("result", "Correct answer unavailable.")
        except Exception as exc:
            print(f"[PFService] Consolidation failed: {exc}")
            return "Consolidation could not be generated. Please ask your instructor."

    # ------------------------------------------------------------------
    # Next problem (jury-calibrated)
    # ------------------------------------------------------------------

    def next_problem(self, session_id: str, task_type: str | None = None) -> str:
        if session_id not in self.sessions:
            return "Session not found. Please start a new problem."

        session = self.sessions[session_id]
        current_difficulty = session.get("difficulty_score", 2)
        attempts = session.get("attempts", [])
        problem = session.get("problem", "")
        current_task_type = session.get("task_type", "translation")
        next_task_type = task_type or current_task_type

        try:
            verdict = self.jury.deliberate(
                problem=problem,
                task_type=current_task_type,
                difficulty_score=current_difficulty,
                attempts=attempts,
                session_id=session_id,
            )
            adjustment = {"INCREASE": +1, "MAINTAIN": 0, "DECREASE": -1}.get(verdict, 0)
            next_difficulty = max(1, min(5, current_difficulty + adjustment))
            print(f"[PFService] difficulty {current_difficulty} → {next_difficulty} (jury: {verdict})")
        except Exception as exc:
            print(f"[PFService] Jury failed, keeping difficulty: {exc}")
            next_difficulty = current_difficulty

        session["problems_completed"] = session.get("problems_completed", 0) + 1
        self._append_event(session_id, role="system", content="Advanced to next problem.", event_type="next_problem")
        self._persist_session(session_id)
        self._persist_result_snapshot(session_id)

        return self.start_session(
            session_id=session_id,
            task_type=next_task_type,
            difficulty_score=next_difficulty,
        )

    # ------------------------------------------------------------------
    # History helpers
    # ------------------------------------------------------------------

    def list_history_for_student(self, student_name: str) -> list[dict]:
        safe_name = self._safe_filename_component(student_name)
        entries: list[dict] = []
        for path in self.results_dir.glob(f"{safe_name}__*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entries.append({
                    "session_id": data.get("session_id"),
                    "student_name": data.get("student_name"),
                    "task_type": data.get("task_type"),
                    "difficulty_score": data.get("difficulty_score"),
                    "stats": data.get("stats", {}),
                    "last_updated_at": data.get("last_updated_at"),
                })
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    def _append_event(self, session_id: str, role: str, content: str, event_type: str):
        session = self.sessions.get(session_id)
        if not session:
            return
        session.setdefault("conversation_history", []).append({
            "timestamp": datetime.utcnow().isoformat(),
            "role": role,
            "event_type": event_type,
            "content": content,
        })

    def _parse_is_correct(self, raw_text: str) -> bool:
        try:
            parsed = json.loads(raw_text)
            return bool(parsed.get("is_correct", False))
        except Exception:
            normalized = raw_text.lower()
            return '"is_correct": true' in normalized or "is correct" in normalized

    def _time_spent_for_problem(self, session: dict) -> int:
        started = session.get("problem_started_at")
        if not started:
            return 0
        try:
            start_dt = datetime.fromisoformat(started)
            return max(0, int((datetime.utcnow() - start_dt).total_seconds()))
        except Exception:
            return 0
