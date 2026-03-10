"""
Adaptive Diagnostic Engine - Main Application Entry Point

A FastAPI-based adaptive testing system that uses Item Response Theory (IRT)
to dynamically assess student proficiency and generate AI-powered study plans.

Supports both local (uvicorn) and serverless (Vercel) deployment modes.
In serverless mode, FastAPI lifespan events may not fire, so we use
middleware-based lazy initialization as a fallback.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.database import database
from app.core.config import settings
from app.routes.routes import router


# ─── Initialization Flag ─────────────────────────────────────────────
_initialized = False


async def _ensure_initialized() -> None:
    """Initialize database and seed questions if not already done.

    This is safe to call multiple times — it's a no-op after the first call.
    Handles both local (lifespan) and serverless (middleware) startup paths.
    """
    global _initialized
    if _initialized:
        return

    if database.db is None:
        await database.connect()

    # Seed if the questions collection is empty
    questions_col = database.get_collection("questions")
    if len(questions_col._data) == 0:
        print("[Init] Seeding in-memory database with questions...")
        from app.seed import seed_questions
        await seed_questions()

    _initialized = True
    print("[Init] Adaptive Diagnostic Engine ready")


# ─── Lifespan (for local uvicorn) ────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    print("=" * 50)
    print("  Adaptive Diagnostic Engine v1.0.0")
    print("=" * 50)
    await _ensure_initialized()
    yield
    await database.disconnect()


# ─── Application ─────────────────────────────────────────────────────

app = FastAPI(
    title="Adaptive Diagnostic Engine",
    description=(
        "AI-Driven Adaptive Testing System using Item Response Theory (IRT) "
        "for GRE-style assessments with personalized study plan generation."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Serverless Initialization Middleware ─────────────────────────────
# Vercel may skip FastAPI's lifespan events. This middleware ensures the
# database is initialized on the first incoming request (cold start).

@app.middleware("http")
async def ensure_db_initialized(request: Request, call_next):
    """Lazily initialize the database on the first request (serverless fallback)."""
    await _ensure_initialized()
    response = await call_next(request)
    return response


# Register API routes
app.include_router(router)

# Serve frontend static files (for local development)
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/")
    async def serve_frontend():
        """Serve the frontend application."""
        return FileResponse(str(frontend_path / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
