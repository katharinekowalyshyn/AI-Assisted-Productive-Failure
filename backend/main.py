from dotenv import load_dotenv
import os

# Load .env file BEFORE any other imports
load_dotenv()


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from pf.router import router as pf_router
from instructor.router import router as instructor_router
from instructor.service import instructor_service


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite
            "http://localhost:3000",  # Node frontend
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers directly with prefix
    app.include_router(pf_router, prefix=settings.api_v1_prefix)
    app.include_router(instructor_router, prefix=settings.api_v1_prefix)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    @app.on_event("startup")
    async def startup_tasks():
        instructor_service.ensure_shared_grammar_uploaded()

    return app


app = create_app()