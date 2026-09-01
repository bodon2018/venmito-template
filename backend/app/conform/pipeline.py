"""Turns read records into rows ready for the clean schema.

Stateless and database-free on purpose: the whole conform stage can be run and
asserted without a Postgres connection, which is what makes it testable.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from .flags import (flag_duplicate_transactions, flag_transaction_items,
                    flag_transfers)
from .identity import IdentityResolution
from .normalize import normalize_email, normalize_phone


@dataclass
class ConformedBatch:
    rows: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def conform_people(merged, resolution: IdentityResolution) -> ConformedBatch:
    batch = ConformedBatch()
    for pid, person in sorted(merged.people.items()):
        batch.rows.append({
            "id": pid,
            "first_name": person["first_name"],
            "last_name": person["last_name"],
            "email": person["email"],
            "phone": person["phone"],
            "city": person["city"],
            "country": person["country"],
            "dob": person["dob"],
            "source": person["source"],
            "is_synthetic": pid in resolution.synthetic,
            "canonical_id": resolution.canonical.get(pid, pid),
            "devices": sorted(person["devices"]),
        })
    batch.stats = {
        "people": len(batch.rows),
        "distinct_entities": len({r["canonical_id"] for r in batch.rows}),
        "conflicts": len(merged.conflicts),
    }
    batch.notes = [{"note_type": "identity", "detail": n} for n in resolution.notes]
    return batch


def conform_promotions(records: list[dict[str, Any]],
                       resolution: IdentityResolution) -> ConformedBatch:
    """Re-key on row position and resolve each row to a person.

    The source `id` is demoted to a provenance column: it repeats across
    unrelated rows, so it cannot be a primary key.
    """
    batch = ConformedBatch()
    id_counts: dict[str, int] = {}
    for record in records:
        id_counts[record.get("id", "")] = id_counts.get(record.get("id", ""), 0) + 1

    for record in records:
        email = normalize_email(record.get("client_email"))
        phone = normalize_phone(record.get("telephone"))
        person_id = resolution.resolve_email(email) or resolution.resolve_phone(phone)
        resolved_via = ("email" if resolution.resolve_email(email)
                        else "phone" if resolution.resolve_phone(phone) else "unresolved")

        if not email and not phone:
            batch.quarantined.append({"reason": "no contact field", "payload": record})
            continue

        batch.rows.append({
            "person_id": person_id,
            "promotion": record.get("promotion"),
            "responded": {"Yes": True, "No": False}.get(record.get("responded")),
            "promotion_date": _parse_date(record.get("promotion_date")),
            "resolved_via": resolved_via,
            "email": email or None,
            "phone": phone or None,
            "source_id": record.get("id"),
            "source_id_is_ambiguous": id_counts.get(record.get("id", ""), 0) > 1,
            "source_row": record.get("source_row"),
        })

    batch.stats = {
        "promotions": len(batch.rows),
        "resolved": sum(1 for r in batch.rows if r["person_id"] is not None),
        "ambiguous_source_ids": sum(1 for r in batch.rows if r["source_id_is_ambiguous"]),
    }
    return batch


def conform_transactions(records: list[dict[str, Any]],
                         resolution: IdentityResolution) -> ConformedBatch:
    batch = ConformedBatch()
    transactions = []

    for record in records:
        phone = normalize_phone(record.get("phone"))
        person_id = resolution.resolve_phone(phone)
        items = [{
            "line_no": line["line_no"],
            "item": line["item"],
            "quantity": float(line["quantity"]),
            "price_per_item": float(line["price_per_item"]),
            "price_reported": float(line["price_reported"]),
        } for line in record["items"]]
        flag_transaction_items(items)

        transactions.append({
            "transaction_id": int(record["transaction_id"]),
            "person_id": person_id,
            "phone": phone,
            "store": record["store"],
            "date": _parse_date(record["date"]),
            "is_orphan": person_id is None,
            "items": items,
            "source_row": record.get("source_row"),
        })

    flag_duplicate_transactions(transactions)
    batch.rows = transactions

    # An orphan phone is not a defect in the row -- it means a person we have
    # never seen. Surfaced for review rather than dropped or silently nulled.
    for txn in transactions:
        if txn["is_orphan"]:
            batch.quarantined.append({
                "reason": f"phone {txn['phone']} matches no person",
                "source_row": txn["source_row"],
                "payload": {"transaction_id": txn["transaction_id"], "phone": txn["phone"]},
            })

    all_items = [i for t in transactions for i in t["items"]]
    batch.stats = {
        "transactions": len(transactions),
        "line_items": len(all_items),
        "orphans": sum(1 for t in transactions if t["is_orphan"]),
        "duplicates": sum(1 for t in transactions if t["is_duplicate"]),
        "items_needing_review": sum(1 for i in all_items if i["needs_review"]),
    }
    return batch


def conform_transfers(records: list[dict[str, Any]],
                      resolution: IdentityResolution) -> ConformedBatch:
    batch = ConformedBatch()
    rows = []
    for record in records:
        rows.append({
            "sender_id": resolution.resolve_person_id(record.get("sender_id")),
            "recipient_id": resolution.resolve_person_id(record.get("recipient_id")),
            "amount": float(record["amount"]) if record.get("amount") else 0.0,
            "date": _parse_date(record.get("date")),
            "source_row": record.get("source_row"),
        })

    summary = flag_transfers(rows)
    batch.rows = rows
    batch.stats = {"transfers": len(rows), **summary}
    batch.notes = [
        {"note_type": "ingestion_outage", "note_date": d,
         "detail": "transfer rows present with no sender, recipient or amount"}
        for d in summary["outage_dates"]
    ]
    return batch


def _parse_date(value) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value).strip())
    except ValueError:
        return None
