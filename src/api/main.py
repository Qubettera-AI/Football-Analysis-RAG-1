"""FastAPI Application Entry Point for Football Analysis Platform."""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from src.api.routes import router
from src.api.services.discussion_service import (
    start_discussion_worker,
    shutdown_discussion_worker,
)
from src.utils.logger import configure_logging

configure_logging()
logger = logging.getLogger("src.api")

# ── Configurable CORS ──
DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8501",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8501",
]

env_cors = os.environ.get("CORS_ORIGINS", "").strip()
allowed_origins = (
    [origin.strip() for origin in env_cors.split(",") if origin.strip()]
    if env_cors
    else DEFAULT_ORIGINS
)


# ── Application Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage worker startup and graceful shutdown."""
    logger.info("Starting Football Analysis Platform API server...")
    logger.info("Configured CORS origins: %s", allowed_origins)

    start_discussion_worker()

    try:
        yield
    finally:
        logger.info("Waiting for accepted discussion jobs to finish...")
        await run_in_threadpool(shutdown_discussion_worker)
        logger.info("Discussion worker stopped.")

# ── FastAPI App Instance ──
app = FastAPI(
    title="Football Analysis Platform API",
    description="Unified REST API wrapping multi-agent football discussions, RAG retrieval, and intelligence analytics.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Logging Middleware ──
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests with method, path, HTTP status, and duration."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        "method=%s path=%s status=%d duration=%.4fs",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response


# ── Global Exception Handlers ──
@app.exception_handler(FileNotFoundError)
async def handle_not_found(request: Request, exc: FileNotFoundError):
    logger.warning("Resource not found: %s", exc)
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def handle_validation_error(request: Request, exc: ValueError):
    logger.warning("Validation error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=422,
        content={"error": "Validation Error", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def handle_internal_error(request: Request, exc: Exception):
    logger.error("Unhandled exception processing %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)},
    )


# ── Frontend ──
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")


# ── Mount Routers ──
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=port, reload=True)
