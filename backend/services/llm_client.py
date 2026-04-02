from llmproxy import LLMProxy
from core.config import settings


class LLMTutorClient:
    def __init__(self):
        self.model = settings.llm_model
        self.client = LLMProxy()

    def generate(self, query: str, session_id: str, context: str = None):
        system_prompt = settings.llm_system_prompt

        if context:
            system_prompt += f"\n\nContext:\n{context}"

        response = self.client.generate(
            model=self.model,
            system=system_prompt,
            query=query,
            session_id=session_id,
            temperature=0.5,
            lastk=3,
            rag_usage=False
        )

        return response.get("result", "")