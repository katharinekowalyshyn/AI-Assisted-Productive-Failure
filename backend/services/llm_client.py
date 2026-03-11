from typing import List, Optional
from uuid import uuid4

from llmproxy import LLMProxy

from backend.core.config import settings
from backend.models.chat import ChatMessage, ChatRequest, ChatResponse


class LLMTutorClient:
    """
    Thin wrapper around LLMProxy focused on the language-tutor use case.

    This class is the main abstraction the rest of the backend should talk to
    when interacting with the LLM. It will be easy to swap implementations
    or enrich prompts (e.g., with RAG) here later.
    """

    def __init__(self) -> None:
        self._client = LLMProxy()

    def _build_session_id(self, explicit: Optional[str]) -> str:
        if explicit:
            return explicit
        # Simple default; callers can pass their own scheme if needed
        return f"{settings.default_session_prefix}{uuid4().hex[:8]}"

    def generate_reply(self, request: ChatRequest, context: Optional[str] = None) -> ChatResponse:
        """
        Generate a tutor-style reply for the given user message.

        `context` can be used in the future for RAG or tool outputs; for now
        it's simply appended to the system prompt if provided.
        """
        session_id = self._build_session_id(request.session_id)

        system_prompt = settings.llm_system_prompt
        if context:
            system_prompt = f"{system_prompt}\n\nAdditional context:\n{context}"

        # Derive a short textual representation of history for now.
        # You can later switch this to a structured call if LLMProxy supports it.
        history_snippets: List[str] = []
        for msg in request.history[-5:]:  # keep it short by default
            prefix = "User" if msg.role == "user" else "Tutor"
            history_snippets.append(f"{prefix}: {msg.content}")

        history_text = "\n".join(history_snippets)
        query = request.user_message
        if history_text:
            query = f"{history_text}\n\nUser: {request.user_message}"

        response = self._client.generate(
            model=settings.llm_model,
            system=system_prompt,
            query=query,
            temperature=0.2,
            lastk=5,
            session_id=session_id,
        )

        reply = response.get("result", "")
        usage = response.get("usage")

        return ChatResponse(session_id=session_id, reply=reply, usage=usage)

