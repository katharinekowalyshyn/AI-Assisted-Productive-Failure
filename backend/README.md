## Backend: TutorChat API (LLMProxy)

FastAPI backend that powers **Productive Failure** tutoring: session-scoped problems, attempt feedback via LLMProxy, optional instructor file uploads as context, and hooks for RAG.

### Implemented services

| Area | Role |
|------|------|
| **`pf/service.py` (`PFService`)** | Starts a session and generates a problem (topic, level, optional uploaded text). Handles student attempts with Productive Failure–style feedback through LLMProxy `generate` (`rag_usage=True`). Exposes hint generation on the router. Keeps in-memory session state (`problem`, attempts, uploaded snippet). |
| **`instructor/service.py` (`InstructorService`)** | Multipart upload: saves files under `./uploads` keyed by `session_id`, returns metadata. `get_session_material` reads UTF-8 text from those files (truncated) so PF prompts can include instructor material. |
| **`services/llm_client.py` (`LLMTutorClient`)** | Thin wrapper around `LLMProxy` with configurable system prompt and optional extra context; `rag_usage=False`. Available for simple chat-style calls; PF flows use `LLMProxy` directly in `PFService`. |
| **`services/rag.py` (`RAGService`)** | Uses `LLMProxy.retrieve` to pull expert chunks and format them as text. Instantiated by `PFService`; you can extend call sites to blend this with session uploads. |
| **`pf/analytics.py` (`AnalyticsLogger`)** | CSV logger scaffold (`pf_learning_logs.csv`) for future attempt/hint analytics; not wired into routers yet. |

### Layout

- `main.py` – FastAPI app, CORS, mounts routers under `settings.api_v1_prefix` (`/api/v1` by default), `GET /health`.
- `core/config.py` – Settings: `app_name`, `api_v1_prefix`, `llm_model`, `llm_system_prompt`, `LLMPROXY_*`, `default_session_prefix`.
- `pf/router.py` – Productive Failure HTTP API (see below).
- `pf/service.py`, `pf/models.py`, `pf/schemas.py`, `pf/analytics.py` – PF domain logic and helpers.
- `instructor/router.py`, `instructor/service.py`, `instructor/schemas.py` – Instructor upload API.
- `services/llm_client.py`, `services/rag.py` – LLM and RAG helpers.
- `models/chat.py` – Legacy/shared chat-oriented Pydantic models (not required for current PF routes).

### HTTP API

Base path: **`/api/v1`** (override with `API_V1_PREFIX` in env if you change `core/config.py`).

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness: `{ "status": "ok", "app": ... }` |
| `POST` | `/api/v1/pf/start` | Body: `session_id`, optional `topic`, `level`. Returns generated problem text. |
| `POST` | `/api/v1/pf/attempt` | Body: `session_id`, `answer`, optional `attempt_number`. Returns `{ "reply": ... }`. |
| `POST` | `/api/v1/pf/hint` | Body: `session_id`, `problem_text`, `hint_level`. Returns `{ "hint": ... }`. |
| `POST` | `/api/v1/instructor/upload` | Form: `file`, `session_id`. Stores file for that session for PF context. |

### Install dependencies

Create and activate a virtual environment, then:

```bash
cd backend
pip install -r requirements.txt
```

Also install `llmproxy` following the instructions in `LLMProxy-main/py/README.md` (local `py/` directory or git).

### Configure environment

Create a `.env` file in the `backend/` folder (or project root) with:

```bash
LLMPROXY_API_KEY="your-api-key-here"
LLMPROXY_ENDPOINT="https://a061igc186.execute-api.us-east-1.amazonaws.com/prod"
```

Optional overrides (see `core/config.py`):

- `LLM_MODEL` → `llm_model`
- `LLM_SYSTEM_PROMPT` → `llm_system_prompt`
- `APP_NAME`, `API_V1_PREFIX`, `DEFAULT_SESSION_PREFIX`

### Run the backend

From the `backend/` directory:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Examples:

- Health: `GET http://localhost:8000/health`
- Start PF: `POST http://localhost:8000/api/v1/pf/start`

### Extending RAG and analytics

- **`RAGService.retrieve_context`** – Use or compose with `PFService` prompts when you want retrieval-backed context beyond inline upload text.
- **`AnalyticsLogger`** – Wire `log_attempt` from PF attempt/hint handlers when you are ready to persist learning metrics to CSV.
