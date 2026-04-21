from pydantic import BaseModel
from typing import Optional


class StartPFResponse(BaseModel):
    session_id: str
    problem: str


class AttemptRequest(BaseModel):
    session_id: str
    content: str



class ReflectionRequest(BaseModel):
    session_id: str
    content: str