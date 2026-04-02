from fastapi import APIRouter
from pydantic import BaseModel
from .service import PFService

router = APIRouter(prefix="/pf", tags=["Productive Failure"])
service = PFService()


class StartRequest(BaseModel):
    session_id: str
    topic: str = "general"
    level: str = "intermediate"


class AttemptRequest(BaseModel):
    session_id: str
    answer: str
    attempt_number: int = None


class HintRequest(BaseModel):
    session_id: str
    problem_text: str
    hint_level: int


@router.post("/start")
def start(req: StartRequest):
    problem = service.start_session(
        session_id=req.session_id,
        topic=req.topic,
        level=req.level
    )
    return problem
    
@router.post("/attempt")
def attempt(req: AttemptRequest):
    reply = service.handle_attempt(req.session_id, req.answer)
    return {"reply": reply}

@router.post("/hint")
def hint(req: HintRequest):
    hint = service.get_hint(req.session_id, req.problem_text, req.hint_level)
    return {"hint": hint}


"""
for debugging purposes:
print(f"DEBUG: Received start request: session_id={req.session_id}, topic={req.topic}, level={req.level}")  # ADD
    try:
        problem = service.start_session(
            session_id=req.session_id,
            topic=req.topic,
            level=req.level
        )
        print(f"DEBUG: Generated problem: {problem}")  # ADD
        return {"problem": problem}
    except Exception as e:
        print(f"ERROR in /start: {e}")  # ADD
        return {"error": str(e), "problem": "Error generating problem"}
"""