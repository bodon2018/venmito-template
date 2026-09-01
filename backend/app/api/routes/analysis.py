"""Analysis endpoints.

Read-only and computed live from current database state, so the numbers
reflect whatever has been uploaded at the moment of the call. There is no
cache to invalidate: after an upload, the client simply asks again.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...analysis import build_report, section
from ...analysis.service import SECTIONS
from ...db.session import get_session

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("", summary="The full report: every section plus plain-language headlines")
def full_report(session: Session = Depends(get_session)) -> dict:
    return build_report(session)


@router.get("/headlines", summary="Just the headline sentences, for the non-technical view")
def headlines(session: Session = Depends(get_session)) -> dict:
    return {"headlines": build_report(session)["headlines"]}


@router.get("/sections", summary="Section names available")
def list_sections() -> dict:
    return {"sections": sorted(SECTIONS)}


@router.get("/{name}", summary="One section, so a single panel can refresh alone")
def one_section(name: str, session: Session = Depends(get_session)) -> dict:
    try:
        return section(session, name)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
