"""FastAPI entry point.

    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import analysis, auth, export, health, loads, uploads
from .config import settings
from .security import HEADER, token_is_valid

app = FastAPI(
    title="Venmito API",
    version="0.1.0",
    description="Ingestion, conforming and analysis over the Venmito source files.",
)

# Routes reachable without a token. Everything else needs one, so opening a
# deep link directly still lands on the code prompt rather than on data.
OPEN_PATHS = {"/auth", "/auth/required", "/ping", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def require_access_code(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    # Vercel mounts the app under /api; compare on the suffix so the same
    # rule works locally and deployed.
    suffix = path[4:] if path.startswith("/api/") else path
    open_path = suffix in OPEN_PATHS or path in OPEN_PATHS

    if settings.gate_enabled and request.method != "OPTIONS" and not open_path:
        token = request.headers.get(HEADER) or ""
        if not token_is_valid(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "An access code is required."},
            )
    return await call_next(request)


# Added after the gate, so CORS ends up the outer layer. Order matters: a 401
# raised by the gate must still pass through CORS, or the browser blocks the
# response and the client sees a network failure instead of "code required".
# In dev the frontend runs on its own port; deployed on Vercel it calls a
# same-origin path, so CORS is not involved at all.
_origins = os.environ.get(
    "VENMITO_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/ping", tags=["system"], summary="Unauthenticated liveness check")
def ping() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(loads.router)
app.include_router(analysis.router)
app.include_router(export.router)
