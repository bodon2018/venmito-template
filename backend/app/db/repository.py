"""All SQL writes. Kept in one place so the conform stage stays database-free.

Every write is an upsert on a natural key, so re-uploading a file corrects
rows instead of duplicating them.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def find_succeeded_load(session: Session, entity: str, sha: str) -> str | None:
    """A byte-identical file that already loaded is a no-op, not a new load."""
    row = session.execute(text("""
        select load_id from ops.loads
        where entity = :entity and content_sha256 = :sha
          and status = 'succeeded' and not superseded
        limit 1
    """), {"entity": entity, "sha": sha}).first()
    return str(row[0]) if row else None


def start_load(session: Session, *, filename: str, file_format: str,
               entity: str, sha: str, mode: str = "append") -> str:
    load_id = str(uuid.uuid4())
    session.execute(text("""
        insert into ops.loads (load_id, filename, file_format, entity, content_sha256, mode)
        values (:load_id, :filename, :file_format, :entity, :sha, :mode)
    """), {"load_id": load_id, "filename": filename, "file_format": file_format,
           "entity": entity, "sha": sha, "mode": mode})
    return load_id


def finish_load(session: Session, load_id: str, *, status: str, rows_read: int = 0,
                rows_loaded: int = 0, rows_quarantined: int = 0,
                error: str | None = None) -> None:
    session.execute(text("""
        update ops.loads
           set status = :status, rows_read = :rows_read, rows_loaded = :rows_loaded,
               rows_quarantined = :rows_quarantined, error = :error, finished_at = now()
         where load_id = :load_id
    """), {"load_id": load_id, "status": status, "rows_read": rows_read,
           "rows_loaded": rows_loaded, "rows_quarantined": rows_quarantined,
           "error": error})


def save_raw_records(session: Session, load_id: str, entity: str,
                     records: list[dict[str, Any]]) -> None:
    """Store the file as read, before any conforming. Lets a policy change be
    replayed without the original file."""
    if not records:
        return
    session.execute(text("""
        insert into raw.records (load_id, entity, source_row, payload)
        values (:load_id, :entity, :source_row, cast(:payload as jsonb))
    """), [{"load_id": load_id, "entity": entity, "source_row": r.get("source_row"),
            "payload": json.dumps(r, default=str)} for r in records])


def save_quarantine(session: Session, load_id: str, entity: str,
                    rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    session.execute(text("""
        insert into ops.quarantine (load_id, entity, reason, source_row, payload)
        values (:load_id, :entity, :reason, :source_row, cast(:payload as jsonb))
    """), [{"load_id": load_id, "entity": entity, "reason": r["reason"],
            "source_row": r.get("source_row"),
            "payload": json.dumps(r.get("payload", {}), default=str)} for r in rows])


def save_notes(session: Session, load_id: str, notes: list[dict[str, Any]]) -> None:
    if not notes:
        return
    session.execute(text("""
        insert into ops.data_quality_notes (load_id, note_type, note_date, detail)
        values (:load_id, :note_type, :note_date, :detail)
    """), [{"load_id": load_id, "note_type": n["note_type"],
            "note_date": n.get("note_date"), "detail": n["detail"]} for n in notes])


# ------------------------------------------------------------------- people
def upsert_people(session: Session, load_id: str, rows: list[dict[str, Any]]) -> int:
    """Two passes: canonical_id is a self-referencing FK, so every row must
    exist before the pointers can be set."""
    payload = [{**{k: r[k] for k in ("id", "first_name", "last_name", "email", "phone",
                                     "city", "country", "dob", "source", "is_synthetic")},
                "load_id": load_id} for r in rows]

    session.execute(text("""
        insert into clean.people (id, first_name, last_name, email, phone, city, country,
                                  dob, source, is_synthetic, canonical_id, load_id)
        values (:id, :first_name, :last_name, :email, :phone, :city, :country,
                :dob, :source, :is_synthetic, :id, :load_id)
        on conflict (id) do update set
            first_name = excluded.first_name, last_name = excluded.last_name,
            email = excluded.email, phone = excluded.phone, city = excluded.city,
            country = excluded.country, dob = excluded.dob, source = excluded.source,
            is_synthetic = excluded.is_synthetic, load_id = excluded.load_id,
            updated_at = now()
    """), payload)

    session.execute(text("""
        update clean.people set canonical_id = :canonical_id where id = :id
    """), [{"id": r["id"], "canonical_id": r["canonical_id"]} for r in rows])

    session.execute(text("delete from clean.person_devices where person_id = any(:ids)"),
                    {"ids": [r["id"] for r in rows]})
    devices = [{"person_id": r["id"], "device": d} for r in rows for d in r["devices"]]
    if devices:
        session.execute(text("""
            insert into clean.person_devices (person_id, device)
            values (:person_id, :device) on conflict do nothing
        """), devices)
    return len(rows)


def upsert_identifiers(session: Session, rows: list[dict[str, Any]],
                       retired: list[dict[str, Any]]) -> None:
    """Natural keys, live and retired. A retired key belongs to the surviving
    entity, so it must overwrite any live row holding the same value."""
    live = [{"person_id": r["canonical_id"], "key_type": kind, "key_value": r[field],
             "is_retired": False}
            for r in rows for kind, field in (("email", "email"), ("phone", "phone"))
            if r[field]]
    aliases = [{**a, "is_retired": True} for a in retired]

    for batch in (live, aliases):
        if not batch:
            continue
        session.execute(text("""
            insert into clean.person_identifiers (person_id, key_type, key_value, is_retired)
            values (:person_id, :key_type, :key_value, :is_retired)
            on conflict (key_type, key_value) do update set
                person_id = excluded.person_id, is_retired = excluded.is_retired
        """), batch)


# --------------------------------------------------------------- promotions
def insert_promotions(session: Session, load_id: str, rows: list[dict[str, Any]]) -> int:
    """Promotions have no natural key of their own -- the source id repeats --
    so rows are simply inserted. Whether prior rows survive is decided by the
    upload mode, not by the filename."""
    if not rows:
        return 0
    session.execute(text("""
        insert into clean.promotions (person_id, promotion, responded, promotion_date,
                                      resolved_via, email, phone, source_id,
                                      source_id_is_ambiguous, source_file, source_row, load_id)
        values (:person_id, :promotion, :responded, :promotion_date, :resolved_via,
                :email, :phone, :source_id, :source_id_is_ambiguous,
                :source_file, :source_row, :load_id)
    """), [{**r, "source_file": _source_file(load_id, session), "load_id": load_id}
           for r in rows])
    return len(rows)


def _source_file(load_id: str, session: Session) -> str:
    return session.execute(text("select filename from ops.loads where load_id = :i"),
                           {"i": load_id}).scalar_one()


# ------------------------------------------------------------- transactions
def upsert_transactions(session: Session, load_id: str, rows: list[dict[str, Any]]) -> int:
    session.execute(text("""
        insert into clean.transactions (transaction_id, person_id, phone, store, txn_date,
                                        is_orphan, is_duplicate, load_id)
        values (:transaction_id, :person_id, :phone, :store, :date,
                :is_orphan, :is_duplicate, :load_id)
        on conflict (transaction_id) do update set
            person_id = excluded.person_id, phone = excluded.phone, store = excluded.store,
            txn_date = excluded.txn_date, is_orphan = excluded.is_orphan,
            is_duplicate = excluded.is_duplicate, load_id = excluded.load_id
    """), [{**{k: r[k] for k in ("transaction_id", "person_id", "phone", "store", "date",
                                 "is_orphan", "is_duplicate")}, "load_id": load_id}
           for r in rows])

    # duplicate_of is a self-FK, so it is set after every row exists.
    session.execute(text("""
        update clean.transactions set duplicate_of = :duplicate_of where transaction_id = :tid
    """), [{"tid": r["transaction_id"], "duplicate_of": r["duplicate_of"]} for r in rows])

    ids = [r["transaction_id"] for r in rows]
    session.execute(text("delete from clean.transaction_items where transaction_id = any(:ids)"),
                    {"ids": ids})
    items = [{"transaction_id": t["transaction_id"], **i} for t in rows for i in t["items"]]
    if items:
        session.execute(text("""
            insert into clean.transaction_items
                (transaction_id, line_no, item, quantity, price_per_item, price,
                 price_reported, price_mismatch, price_zero, price_negative, needs_review)
            values (:transaction_id, :line_no, :item, :quantity, :price_per_item, :price,
                    :price_reported, :price_mismatch, :price_zero, :price_negative, :needs_review)
        """), items)
    return len(rows)


# ----------------------------------------------------------------- transfers
def insert_transfers(session: Session, load_id: str, rows: list[dict[str, Any]]) -> int:
    """Transfers carry no id of their own, so rows are inserted. Whether prior
    rows survive is decided by the upload mode, not by the filename."""
    if not rows:
        return 0
    session.execute(text("""
        insert into clean.transfers (sender_id, recipient_id, amount, transfer_date,
                                     is_null_row, is_self_transfer, is_amt_outlier,
                                     is_round_amount, is_reciprocal_pair, is_fanout,
                                     is_ambiguous_998, flags, is_clean, source_row, load_id)
        values (:sender_id, :recipient_id, :amount, :date, :is_null_row, :is_self_transfer,
                :is_amt_outlier, :is_round_amount, :is_reciprocal_pair, :is_fanout,
                :is_ambiguous_998, :flags, :is_clean, :source_row, :load_id)
    """), [{**r, "load_id": load_id} for r in rows])
    return len(rows)


# ------------------------------------------------------- reading back state
def load_people_raw(session: Session) -> list[tuple[str, list[dict[str, Any]]]]:
    """Every people record ever ingested, grouped by source filename.

    People are re-merged from raw on each upload because merging is a
    whole-population operation: a new file can change the outcome for ids it
    does not even contain (a duplicate entity, a conflicting id).
    """
    rows = session.execute(text("""
        select l.filename, r.payload
          from raw.records r
          join ops.loads l using (load_id)
         where r.entity = 'people' and l.status in ('running','succeeded')
           and not l.superseded
         order by l.started_at, r.source_row
    """)).all()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for filename, payload in rows:
        grouped.setdefault(filename, []).append(payload)
    return list(grouped.items())


def load_identity_resolution(session: Session):
    """Rebuild the lookups from what is already in the database, so a
    non-people upload can resolve against the current population."""
    from ..conform.identity import IdentityResolution

    resolution = IdentityResolution()
    for pid, canonical, synthetic in session.execute(text(
            "select id, canonical_id, is_synthetic from clean.people")).all():
        resolution.canonical[pid] = canonical
        if synthetic:
            resolution.synthetic.add(pid)

    for key_type, key_value, person_id in session.execute(text(
            "select key_type, key_value, person_id from clean.person_identifiers")).all():
        target = resolution.email_to_id if key_type == "email" else resolution.phone_to_id
        target[key_value] = person_id
    return resolution


def post_load_assertions(session: Session) -> dict[str, Any]:
    """Cheap integrity gate run after every load."""
    checks = {
        "people": "select count(*) from clean.people",
        "distinct_entities": "select count(distinct canonical_id) from clean.people",
        "orphan_transactions": "select count(*) from clean.transactions where is_orphan",
        "unresolved_promotions": "select count(*) from clean.promotions where person_id is null",
        "null_transfers": "select count(*) from clean.transfers where is_null_row",
        "flagged_transfers": "select count(*) from clean.transfers where not is_clean",
        "items_needing_review": "select count(*) from clean.transaction_items where needs_review",
        "duplicate_transactions": "select count(*) from clean.transactions where is_duplicate",
    }
    return {name: session.execute(text(sql)).scalar() for name, sql in checks.items()}


# --------------------------------------------------------------- load modes
# Which clean tables each entity owns, in delete order (children first).
ENTITY_TABLES = {
    "promotions": ("clean.promotions",),
    "transactions": ("clean.transaction_items", "clean.transactions"),
    "transfers": ("clean.transfers",),
    # people are rebuilt by re-merging raw, so a replace supersedes the prior
    # raw loads rather than deleting rows that are about to be rewritten.
    "people": (),
}


def supersede_previous_loads(session: Session, entity: str, load_id: str) -> int:
    """Mark every earlier active load of this entity as superseded.

    History is kept: the audit row and its raw records stay, they are simply
    excluded from the current picture and from the duplicate-file guard.
    """
    result = session.execute(text("""
        update ops.loads set superseded = true, superseded_by = :load_id
         where entity = :entity and load_id <> :load_id
           and status = 'succeeded' and not superseded
    """), {"entity": entity, "load_id": load_id})
    return result.rowcount or 0


def clear_entity_rows(session: Session, entity: str) -> None:
    """Remove the clean rows an entity owns, ahead of a replace."""
    for table in ENTITY_TABLES.get(entity, ()):
        session.execute(text(f"delete from {table}"))


def previous_active_load(session: Session, entity: str, filename: str) -> dict | None:
    """An earlier load of the same entity, used to warn about accidental
    double-appends when someone re-uploads a corrected file."""
    row = session.execute(text("""
        select load_id, filename, rows_loaded, started_at from ops.loads
         where entity = :entity and status = 'succeeded' and not superseded
         order by started_at desc limit 1
    """), {"entity": entity, "filename": filename}).mappings().first()
    return dict(row) if row else None
