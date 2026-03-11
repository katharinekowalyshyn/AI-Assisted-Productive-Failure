from fastapi import APIRouter, Depends

from backend.models.chat import ChatRequest, ChatResponse
from backend.services.llm_client import LLMTutorClient
from backend.services.rag import RAGService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_llm_client() -> LLMTutorClient:
    # In a larger app you might manage this with a container or lifespan hook.
    return LLMTutorClient()


def get_rag_service() -> RAGService:
    return RAGService()


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    llm_client: LLMTutorClient = Depends(get_llm_client),
    rag_service: RAGService = Depends(get_rag_service),
) -> ChatResponse:
    """
    Main tutor chat endpoint.

    - Optionally fetches retrieval context from `RAGService`
    - Delegates completion generation to `LLMTutorClient`
    """
    context = rag_service.retrieve_context(payload.user_message, payload.session_id)
    response = llm_client.generate_reply(payload, context=context)
    return response

