"""Exchanging an access code for a token."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ...config import settings
from ...security import TOKEN_TTL_SECONDS, code_is_valid, issue_token

router = APIRouter(tags=["access"])


class CodeRequest(BaseModel):
    code: str


class TokenResponse(BaseModel):
    token: str
    expires_in: int


@router.get("/auth/required", summary="Whether this deployment requires a code")
def gate_required() -> dict:
    return {"required": settings.gate_enabled}


@router.post("/auth", response_model=TokenResponse, summary="Exchange a code for a token")
def authenticate(body: CodeRequest) -> TokenResponse:
    if not settings.gate_enabled:
        # No codes configured: hand back a token so the client flow is the
        # same either way.
        return TokenResponse(token=issue_token("OPEN"), expires_in=TOKEN_TTL_SECONDS)
    if not code_is_valid(body.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="That code is not valid.")
    return TokenResponse(token=issue_token(body.code), expires_in=TOKEN_TTL_SECONDS)
