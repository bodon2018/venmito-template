"""CSV export.

Streams straight from the database rather than building the whole file in
memory, so a large table does not have to fit in a serverless function's
allowance. Behind the access gate like every other data route.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from ...db.session import session_scope

router = APIRouter(prefix="/export", tags=["export"])

# Named queries rather than an arbitrary table parameter: the caller cannot
# reach a table that is not listed here, and each export is a considered shape
# rather than a raw dump.
EXPORTS: dict[str, dict] = {
    "people": {
        "label": "Clients",
        "note": "One row per person, with devices collapsed into one column.",
        "sql": """
            select p.id, p.first_name, p.last_name, p.email, p.phone, p.city,
                   p.country, p.dob, p.source, p.is_synthetic, p.canonical_id,
                   (select string_agg(d.device, '|' order by d.device)
                      from clean.person_devices d where d.person_id = p.id) as devices
              from clean.people p order by p.id
        """,
    },
    "promotions": {
        "label": "Promotions",
        "note": "Every offer, resolved to a client where possible.",
        "sql": """
            select promotion_key, person_id, promotion, responded, promotion_date,
                   resolved_via, email, phone, source_id, source_id_is_ambiguous,
                   source_file, source_row
              from clean.promotions order by promotion_key
        """,
    },
    "transactions": {
        "label": "Transactions",
        "note": "Transaction headers, including orphan and duplicate flags.",
        "sql": """
            select transaction_id, person_id, phone, store, txn_date,
                   is_orphan, is_duplicate, duplicate_of
              from clean.transactions order by transaction_id
        """,
    },
    "transaction_items": {
        "label": "Transaction line items",
        "note": "One row per line. price is recomputed; price_reported is the source value.",
        "sql": """
            select i.transaction_id, i.line_no, t.person_id, t.store, t.txn_date,
                   i.item, i.quantity, i.price_per_item, i.price, i.price_reported,
                   i.price_mismatch, i.price_zero, i.price_negative, i.needs_review
              from clean.transaction_items i
              join clean.transactions t using (transaction_id)
             order by i.transaction_id, i.line_no
        """,
    },
    "transfers": {
        "label": "Transfers",
        "note": "Every row including the empty ones, with all risk flags.",
        "sql": """
            select transfer_key, sender_id, recipient_id, amount, transfer_date,
                   is_null_row, is_self_transfer, is_amt_outlier, is_round_amount,
                   is_reciprocal_pair, is_fanout, is_ambiguous_998, flags, is_clean,
                   source_row
              from clean.transfers order by transfer_key
        """,
    },
    "quarantine": {
        "label": "Quarantined rows",
        "note": "Rows that could not be resolved to a client, with the reason.",
        "sql": """
            select q.id, l.filename, q.entity, q.reason, q.source_row,
                   q.payload::text as payload, q.created_at
              from ops.quarantine q join ops.loads l using (load_id)
             where not l.superseded order by q.id
        """,
    },
    "loads": {
        "label": "Load history",
        "note": "Every upload and what it did.",
        "sql": """
            select load_id, filename, file_format, entity, mode, status, rows_read,
                   rows_loaded, rows_quarantined, superseded, error,
                   started_at, finished_at
              from ops.loads order by started_at
        """,
    },
}

CHUNK_ROWS = 500


@router.get("", summary="Datasets available for export")
def list_exports() -> dict:
    return {"exports": [{"name": n, "label": e["label"], "note": e["note"]}
                        for n, e in EXPORTS.items()]}


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _rows(name: str):
    """Yield CSV text in chunks, holding only a few hundred rows at a time."""
    with session_scope() as session:
        result = session.execute(text(EXPORTS[name]["sql"]))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(result.keys())

        while True:
            batch = result.fetchmany(CHUNK_ROWS)
            if not batch:
                break
            for row in batch:
                writer.writerow([_cell(v) for v in row])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

        remainder = buffer.getvalue()
        if remainder:
            yield remainder


@router.get("/{name}.csv", summary="Download one dataset as CSV")
def export_csv(name: str) -> StreamingResponse:
    if name not in EXPORTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail=f"Unknown export {name!r}; see GET /export")
    stamp = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        _rows(name),
        media_type="text/csv",
        headers={"content-disposition":
                 f'attachment; filename="venmito_{name}_{stamp}.csv"'},
    )
