from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.chat import router as chat_router
from backend.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # CORS: allow local dev frontends; tighten this as needed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite default
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_v1 = FastAPI()
    api_v1.include_router(chat_router)

    app.mount(settings.api_v1_prefix, api_v1)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()

