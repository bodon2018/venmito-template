"""FastAPI entry point.

    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import analysis, health, loads, uploads

app = FastAPI(
    title="Venmito API",
    version="0.1.0",
    description="Ingestion, conforming and analysis over the Venmito source files.",
)

# Internal tool, no auth. In dev the frontend runs on its own port; when
# deployed together on Vercel the frontend calls a same-origin path, so CORS
# is not involved at all. VENMITO_CORS_ORIGINS overrides for any other host.
_origins = os.environ.get(
    "VENMITO_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(loads.router)
app.include_router(analysis.router)
