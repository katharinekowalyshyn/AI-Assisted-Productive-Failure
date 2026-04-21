from fastapi import APIRouter, HTTPException, Query
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


@router.get("/history")
def history(student_name: str = Query(..., min_length=1)):
    """List previous saved sessions for a student name."""
    return service.list_history_for_student(student_name)


@router.get("/history/{session_id}")
def history_session(session_id: str, student_name: Optional[str] = Query(default=None)):
    """Fetch one saved session detail including conversation history."""
    payload = service.get_history_session(session_id=session_id, student_name=student_name)
    if not payload:
        raise HTTPException(status_code=404, detail="Session history not found.")
    return payload
