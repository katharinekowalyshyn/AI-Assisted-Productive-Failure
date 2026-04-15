from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from .service import PFService

router = APIRouter(prefix="/pf", tags=["Productive Failure"])
service = PFService()


class StartRequest(BaseModel):
    session_id: str
    student_name: str
    task_type: str = "translation"   # translation | error_correction | conversation_completion
    difficulty_score: Optional[int] = None  # 1–5; None = use session default or 2


class AttemptRequest(BaseModel):
    session_id: str
    answer: str
    attempt_number: Optional[int] = None


class HintRequest(BaseModel):
    session_id: str
    problem_text: str
    hint_level: int


class NextRequest(BaseModel):
    session_id: str
    task_type: Optional[str] = None  # if None, reuse the current task type


@router.post("/start")
def start(req: StartRequest):
    """Generate the first (or a manually-reset) problem for a session."""
    problem = service.start_session(
        session_id=req.session_id,
        task_type=req.task_type,
        difficulty_score=req.difficulty_score,
        student_name=req.student_name,
    )
    return problem


@router.post("/attempt")
def attempt(req: AttemptRequest):
    """Evaluate a student attempt and return PF-style feedback."""
    result = service.handle_attempt(req.session_id, req.answer)
    if isinstance(result, dict):
        return result
    return {"reply": result}


@router.post("/hint")
def hint(req: HintRequest):
    """Return a scaffolded hint at the requested level (1–4)."""
    result = service.get_hint(req.session_id, req.problem_text, req.hint_level)
    return {"hint": result}


@router.post("/next")
def next_problem(req: NextRequest):
    """
    Run the LLM jury on the completed problem, silently adjust difficulty,
    and return the next generated problem.
    """
    problem = service.next_problem(
        session_id=req.session_id,
        task_type=req.task_type,
    )
    return problem
