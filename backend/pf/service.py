from services.llm_client import LLMTutorClient
from services.rag import RAGService
from .models import *
from .analytics import AnalyticsLogger


class PFService:
    def __init__(self):
        self.llm = LLMTutorClient()
        self.rag = RAGService()
        self.logger = AnalyticsLogger()

    # -------------------------------
    # 1️⃣ Evaluate Student Attempt
    # -------------------------------
    def evaluate_attempt(self, req: AttemptRequest) -> PFResponse:
        # 🔹 RAG uses BOTH problem and student reasoning
        query = f"{req.problem_text}\nStudent solution:\n{req.student_answer}"
        context = self.rag.retrieve_context(query)

        prompt = f"""
You are an expert tutor analyzing a student's solution.

PROBLEM:
{req.problem_text}

STUDENT ANSWER:
{req.student_answer}

RETRIEVED EXPERT CONTEXT:
{context}

TASK:
1. Identify misconceptions
2. Evaluate correctness
3. Suggest improvement strategy
4. Reference expert method where helpful
"""

        reply = self.llm.generate(prompt)

        # 🔹 Log analytics AFTER evaluation
        self.logger.log_attempt(
            session_id=req.session_id,
            problem=req.problem_text,
            attempt=req.student_answer,
            evaluation=reply
        )

        return PFResponse(
            message="Attempt evaluated",
            evaluation=reply
        )

    # -------------------------------
    #  Generate Progressive Hints
    # -------------------------------
    def generate_hint(self, req: HintRequest) -> PFResponse:
        #  Retrieval grounded in problem type
        query = f"{req.problem_text}\nStudent attempt:\n{req.student_answer}"
        context = self.rag.retrieve_context(query)

        hint_levels = {
            1: "Give a conceptual clue without revealing steps.",
            2: "Give a structural hint showing the approach.",
            3: "Give a near-complete method with minor gaps.",
            4: "Provide the full expert solution clearly."
        }

        prompt = f"""
You are guiding a struggling student using Productive Failure pedagogy.

PROBLEM:
{req.problem_text}

STUDENT ANSWER:
{req.student_answer}

RETRIEVED EXPERT CONTEXT:
{context}

HINT LEVEL: {req.hint_level}
INSTRUCTION: {hint_levels[req.hint_level]}

Keep tone supportive. Do not shame mistakes.
"""

        reply = self.llm.generate(prompt)

        self.logger.log_hint(
            session_id=req.session_id,
            hint_level=req.hint_level,
            hint=reply
        )

        return PFResponse(message="Hint generated", hint=reply)

    # -------------------------------
    # 3️⃣ Analyze Student Reflection
    # -------------------------------
    def analyze_reflection(self, req: ReflectionRequest) -> PFResponse:
        # 🔹 RAG finds expert explanations about topic gaps
        context = self.rag.retrieve_context(req.problem_text)

        prompt = f"""
Analyze the student reflection for learning gaps.

PROBLEM CONTEXT:
{req.problem_text}

STUDENT REFLECTION:
{req.student_reflection}

RETRIEVED EXPERT CONTEXT:
{context}

Identify:
• misunderstanding
• emotional state
• knowledge gaps
• recommended exercises
"""

        reply = self.llm.generate(prompt)

        self.logger.log_reflection(
            session_id=req.session_id,
            reflection=req.student_reflection,
            analysis=reply
        )

        return PFResponse(message="Reflection analyzed", evaluation=reply)