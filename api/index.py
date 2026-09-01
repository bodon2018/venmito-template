"""Vercel serverless entry point.

Vercel runs each request in a fresh Python function, so the app is mounted
under /api and the whole backend package is imported from the repo root.
Locally you still run `uvicorn app.main:app` from backend/ -- this file only
exists for the hosted deployment.
"""
import os
import sys
from pathlib import Path

# The backend package lives in backend/; make it importable from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

# Serverless: no long-lived process, so no connection pool to reuse.
os.environ.setdefault("VENMITO_SERVERLESS", "1")

from fastapi import FastAPI  # noqa: E402
from app.main import app as backend_app  # noqa: E402

# Vercel routes /api/* here and passes the full path, so the backend is
# mounted at /api rather than at the root.
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
app.mount("/api", backend_app)
