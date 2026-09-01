"""Orchestrates one upload: detect -> read -> store raw -> conform -> write.

The whole thing runs inside a single transaction. If any step raises, nothing
from that file lands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..conform import pipeline as conform
from ..conform.identity import resolve_identities
from ..conform.people import merge_people
from ..db import repository as repo
from ..ingestion import detect_entity, detect_format, read_file


@dataclass
class IngestResult:
    load_id: str | None
    filename: str
    file_format: str
    entity: str
    status: str
    mode: str = "append"
    rows_read: int = 0
    rows_loaded: int = 0
    rows_quarantined: int = 0
    stats: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    integrity: dict[str, Any] = field(default_factory=dict)


def ingest_upload(session: Session, *, filename: str, content: bytes,
                  mode: str = "append") -> IngestResult:
    """mode:
      append  - add this file's rows to what is already stored (default)
      replace - this file becomes the entity's contents; earlier loads are
                superseded, their clean rows removed, raw history kept
    """
    if mode not in ("append", "replace"):
        raise ValueError(f"mode must be 'append' or 'replace', got {mode!r}")

    file_format = detect_format(content, filename)
    entity = detect_entity(content, file_format, filename)
    sha = repo.content_sha256(content)

    # Re-uploading the same bytes is a no-op -- but only in append mode.
    # A replace is an explicit instruction, so it proceeds even when the
    # content is unchanged (that is how you rebuild an entity from one file).
    existing = repo.find_succeeded_load(session, entity, sha) if mode == "append" else None
    if existing:
        return IngestResult(load_id=existing, filename=filename, file_format=file_format,
                            entity=entity, status="skipped_duplicate_file", mode=mode,
                            notes=["identical file already loaded"])

    # Appending on top of an existing load is legitimate, but it is also how
    # someone accidentally doubles their data by re-uploading a corrected
    # file. Warn rather than guess what they meant.
    warnings: list[str] = []
    if mode == "append":
        previous = repo.previous_active_load(session, entity, filename)
        if previous:
            warnings.append(
                f"appended to an existing {entity} load ({previous['filename']}, "
                f"{previous['rows_loaded']} rows). Use mode=replace if this file "
                f"supersedes it.")

    load_id = repo.start_load(session, filename=filename, file_format=file_format,
                              entity=entity, sha=sha, mode=mode)
    try:
        if mode == "replace":
            superseded = repo.supersede_previous_loads(session, entity, load_id)
            repo.clear_entity_rows(session, entity)
            if superseded:
                warnings.append(f"replaced {superseded} earlier {entity} load(s)")

        read = read_file(content, file_format, entity)
        repo.save_raw_records(session, load_id, entity, read.records)
        if read.errors:
            repo.save_quarantine(session, load_id, entity,
                                 [{"reason": e["reason"], "source_row": e.get("source_row"),
                                   "payload": {"raw": str(e.get("payload"))[:2000]}}
                                  for e in read.errors])

        result = _conform_and_write(session, load_id, entity, read)
        result.mode = mode
        result.warnings = warnings
        result.rows_read = read.rows_read
        result.rows_quarantined += len(read.errors)

        repo.finish_load(session, load_id, status="succeeded", rows_read=result.rows_read,
                         rows_loaded=result.rows_loaded,
                         rows_quarantined=result.rows_quarantined)
        result.integrity = repo.post_load_assertions(session)
        return result
    except Exception as exc:
        # finish_load runs on the rolled-back session in the caller's handler;
        # re-raised so the transaction aborts and nothing partial lands.
        repo.finish_load(session, load_id, status="failed", error=str(exc)[:2000])
        raise


def _conform_and_write(session: Session, load_id: str, entity: str, read) -> IngestResult:
    base = IngestResult(load_id=load_id, filename="", file_format=read.file_format,
                        entity=entity, status="succeeded")

    if entity == "people":
        # People are re-merged across every people file ever loaded: a new file
        # can change the outcome for ids it does not itself contain.
        batches = repo.load_people_raw(session)
        merged = merge_people(batches, precedence=settings.people_precedence)
        resolution = resolve_identities(merged, duplicate_policy=settings.duplicate_policy)
        conformed = conform.conform_people(merged, resolution)

        repo.upsert_people(session, load_id, conformed.rows)
        repo.upsert_identifiers(session, conformed.rows, resolution.retired_keys)
        repo.save_notes(session, load_id, conformed.notes)
        base.rows_loaded = len(conformed.rows)
        base.stats = conformed.stats
        base.notes = [n["detail"] for n in conformed.notes]
        return base

    # Everything else resolves against the population already in the database.
    resolution = repo.load_identity_resolution(session)

    if entity == "promotions":
        conformed = conform.conform_promotions(read.records, resolution)
        base.rows_loaded = repo.insert_promotions(session, load_id, conformed.rows)
    elif entity == "transactions":
        conformed = conform.conform_transactions(read.records, resolution)
        base.rows_loaded = repo.upsert_transactions(session, load_id, conformed.rows)
    elif entity == "transfers":
        conformed = conform.conform_transfers(read.records, resolution)
        base.rows_loaded = repo.insert_transfers(session, load_id, conformed.rows)
    else:
        raise ValueError(f"no conform step for entity {entity!r}")

    repo.save_quarantine(session, load_id, entity, conformed.quarantined)
    repo.save_notes(session, load_id, conformed.notes)
    base.rows_quarantined = len(conformed.quarantined)
    base.stats = conformed.stats
    base.notes = [n["detail"] for n in conformed.notes]
    return base
