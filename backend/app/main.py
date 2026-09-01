"""FastAPI entry point.

    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import analysis, health, loads, uploads

app = FastAPI(
    title="Venmito API",
    version="0.1.0",
    description="Ingestion, conforming and analysis over the Venmito source files.",
)

# Internal tool, no auth -- the frontend runs on a different port in dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(loads.router)
app.include_router(analysis.router)
