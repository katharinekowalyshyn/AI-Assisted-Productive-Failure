from pydantic import BaseModel
from typing import Optional, List


class AttemptRequest(BaseModel):
    problem_id: str
    problem_text: str
    student_answer: str
    attempt_number: int
    session_id: str


class HintRequest(BaseModel):
    problem_id: str
    student_answer: str
    hint_level: int
    session_id: str


class ReflectionRequest(BaseModel):
    problem_id: str
    student_reflection: str
    session_id: str


class PFResponse(BaseModel):
    message: str
    hint: Optional[str] = None
    evaluation: Optional[str] = None
    expert_solution: Optional[str] = None