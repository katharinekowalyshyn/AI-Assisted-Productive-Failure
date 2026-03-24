from typing import Optional
from llmproxy import LLMProxy


class RAGService:
    """
    Cloud Retrieval-Augmented Generation using LLMProxy.
    Retrieves relevant instructor materials for a student query.
    """

    def __init__(self) -> None:
        self.client = LLMProxy()
        self.default_session = "instructor_material"

    def _format_context(self, rag_response: dict) -> str:
        """
        Convert LLMProxy RAG JSON into readable context text.
        """
        if not rag_response or "rag_context" not in rag_response:
            return "No relevant expert materials found."

        context_text = "\n\n📚 Expert Reference Materials:\n"
        collections = rag_response.get("rag_context", [])

        for i, collection in enumerate(collections, start=1):
            summary = collection.get("doc_summary", "No summary available")
            context_text += f"\nSource {i}: {summary}\n"

            chunks = collection.get("chunks", [])
            for j, chunk in enumerate(chunks, start=1):
                context_text += f"  {i}.{j} {chunk}\n"

        return context_text

    def retrieve_context(self, query: str, session_id: Optional[str] = None) -> str:
        """
        Retrieve expert learning materials related to the query.
        """
        sid = session_id or self.default_session

        try:
            rag_response = self.client.retrieve(
                query=query,
                session_id=sid,
                rag_threshold=0.35,
                rag_k=5,
            )

            if "error" in rag_response:
                return f"RAG retrieval error: {rag_response['error']}"

            return self._format_context(rag_response)

        except Exception as e:
            return f"RAG system unavailable: {str(e)}"