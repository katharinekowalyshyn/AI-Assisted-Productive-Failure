## Backend: TutorChat API (LLMProxy)

This folder contains a small FastAPI backend that wraps the `llmproxy` client
behind a clean chat API suitable for a tutor-style chatbot.

### Layout

- `main.py` – FastAPI application and CORS setup, mounts the API under `/api`.
- `core/config.py` – central configuration (model, system prompt, prefixes).
- `api/chat.py` – chat router exposing `POST /api/chat/`.
- `models/chat.py` – Pydantic data models for chat requests/responses.
- `services/llm_client.py` – `LLMTutorClient` class that wraps `LLMProxy`.
- `services/rag.py` – `RAGService` stub where you can plug in retrieval logic.

### Install dependencies

Create and activate a virtual environment, then:

```bash
cd backend
pip install -r requirements.txt
```

Also install `llmproxy` following the instructions in `LLMProxy-main/py/README.md`
(either from the local `py/` directory or via git).

### Configure environment

Create a `.env` file in the `backend/` folder (or project root) with:

```bash
LLMPROXY_API_KEY="your-api-key-here"
LLMPROXY_ENDPOINT="https://a061igc186.execute-api.us-east-1.amazonaws.com/prod"
```

Optionally override:

- `LLM_MODEL`
- `LLM_SYSTEM_PROMPT`

See `core/config.py` for defaults.

### Run the backend

From the `backend/` directory:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The chat endpoint will then be available at:

- `POST http://localhost:8000/api/chat/`

### Plugging in RAG later

Implement your retrieval logic inside `RAGService.retrieve_context` in
`services/rag.py`. Whatever text you return there will be appended to the system
prompt as additional context for the LLM.

