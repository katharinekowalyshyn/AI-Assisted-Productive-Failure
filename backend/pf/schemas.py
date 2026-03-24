from pydantic import BaseModel
from typing import Optional


class StartPFResponse(BaseModel):
    session_id: str
    problem: str


class AttemptRequest(BaseModel):
    session_id: str
    content: str


class HintRequest(BaseModel):
    session_id: str
    level: int


class ReflectionRequest(BaseModel):
    session_id: str
    content: str