"""Load history and quarantine -- the technical view's audit surface."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...db.session import get_session

router = APIRouter(prefix="/loads", tags=["ingestion"])


@router.get("", summary="Every upload, newest first")
def list_loads(limit: int = 50, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.execute(text("""
        select load_id, filename, file_format, entity, status, rows_read, rows_loaded,
               rows_quarantined, error, started_at, finished_at
          from ops.loads order by started_at desc limit :limit
    """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/quarantine", summary="Rows that could not be loaded, with the reason")
def list_quarantine(limit: int = 200, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.execute(text("""
        select q.id, l.filename, q.entity, q.reason, q.source_row, q.payload, q.created_at
          from ops.quarantine q join ops.loads l using (load_id)
         order by q.created_at desc limit :limit
    """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/notes", summary="Data-quality notes, e.g. detected ingestion outages")
def list_notes(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.execute(text("""
        select note_type, note_date, detail, created_at
          from ops.data_quality_notes order by note_date nulls last, created_at desc
    """)).mappings().all()
    return [dict(r) for r in rows]
