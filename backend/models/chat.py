from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Represents a single message in the conversation."""

    role: str = Field(..., description="e.g. 'user' or 'assistant'")
    content: str


class ChatTurn(BaseModel):
    """Represents a turn in the dialogue, useful for future RAG/context."""

    user_message: str
    assistant_message: Optional[str] = None


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    session_id: Optional[str] = Field(
        default=None,
        description="Optional session id; if not provided, backend will derive one.",
    )
    user_message: str = Field(..., min_length=1)
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="Optional short conversation history for better responses.",
    )


class ChatResponse(BaseModel):
    """Standardized response from the chat endpoint."""

    session_id: str
    reply: str
    usage: Optional[dict] = None

