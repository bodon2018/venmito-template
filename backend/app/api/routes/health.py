from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...db.session import healthcheck

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness and database connectivity")
def health() -> dict:
    try:
        return {"status": "ok", "database": "reachable" if healthcheck() else "unreachable"}
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
