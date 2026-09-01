"""Upload endpoint. One file per request; order does not matter except that
people must be loaded before the files that reference them."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ...config import settings
from ...db.session import session_scope
from ...services.ingest_service import ingest_upload

router = APIRouter(prefix="/uploads", tags=["ingestion"])


class UploadResponse(BaseModel):
    load_id: str | None
    filename: str
    file_format: str
    entity: str
    status: str
    mode: str
    rows_read: int
    rows_loaded: int
    rows_quarantined: int
    stats: dict
    notes: list[str]
    warnings: list[str]
    integrity: dict


@router.post("", response_model=list[UploadResponse],
             status_code=status.HTTP_201_CREATED,
             summary="Upload one or more source files (JSON, YAML, CSV, XML)")
async def upload_files(
    files: list[UploadFile] = File(...),
    mode: str = Form("append",
                     description="append: add to existing data. "
                                 "replace: this file becomes the entity's contents."),
) -> list[UploadResponse]:
    """Upload is explicit about what happens to existing data.

    The default is append, so re-uploading can never silently destroy rows;
    replacing is something the caller has to ask for.
    """
    if mode not in ("append", "replace"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="mode must be 'append' or 'replace'")
    responses: list[UploadResponse] = []

    # People files are processed first: the other entities resolve against
    # them, so loading a transfer file into an empty people table would
    # quarantine every row.
    payloads = [(f.filename or "upload", await f.read()) for f in files]
    payloads.sort(key=lambda p: 0 if "people" in p[0].lower() else 1)

    for filename, content in payloads:
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail=f"{filename} exceeds the size limit")
        try:
            # One transaction per file, so a bad file cannot half-land.
            with session_scope() as session:
                result = ingest_upload(session, filename=filename,
                                       content=content, mode=mode)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"{filename}: {exc}") from exc
        except Exception as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"{filename}: {exc}") from exc

        result.filename = filename
        responses.append(UploadResponse(**result.__dict__))
    return responses
