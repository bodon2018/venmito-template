"""Row-level defect and risk rules.

Everything here sets a boolean. Nothing deletes: a bad row stays queryable and
auditable, and the analysis layer filters on the flags instead. The transfer
rules in particular are the fraud signal, not noise to be cleaned away.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any, Iterable

PRICE_TOLERANCE = 0.011          # a cent, plus float slack
ROUND_AMOUNT_FLOOR = 100.0       # below this, a whole-number amount is unremarkable
IQR_FAR_OUT = 3.0                # Tukey far-out multiplier
RECIPROCAL_WINDOW = dt.timedelta(days=7)
FANOUT_MIN_RECIPIENTS = 3


# ------------------------------------------------------------- transactions
def flag_transaction_items(items: list[dict[str, Any]]) -> None:
    """Recompute price and flag the rows that disagree with the source.

    price_reported is kept alongside so the correction stays auditable.
    """
    for item in items:
        quantity = float(item["quantity"])
        unit = float(item["price_per_item"])
        reported = float(item["price_reported"])
        item["price"] = round(unit * quantity, 2)
        item["price_mismatch"] = abs(item["price"] - reported) > PRICE_TOLERANCE
        item["price_zero"] = reported == 0
        item["price_negative"] = reported < 0
        item["needs_review"] = (item["price_mismatch"] or item["price_zero"]
                                or item["price_negative"])


def flag_duplicate_transactions(transactions: list[dict[str, Any]]) -> None:
    """Mark repeats by content signature rather than by id.

    Signature-based so it survives the source renumbering its ids -- the
    earliest id in a group is kept and the rest point at it.
    """
    seen: dict[tuple, int] = {}
    for txn in sorted(transactions, key=lambda t: t["transaction_id"]):
        basket = tuple(sorted((i["item"], i["quantity"], i["price"]) for i in txn["items"]))
        signature = (txn["phone"], txn["store"], txn["date"], basket)
        original = seen.get(signature)
        txn["is_duplicate"] = original is not None
        txn["duplicate_of"] = original
        if original is None:
            seen[signature] = txn["transaction_id"]


# ----------------------------------------------------------------- transfers
def flag_transfers(transfers: list[dict[str, Any]]) -> dict[str, Any]:
    """Tag null rows, self-transfers and the three outlier patterns.

    Returns a summary including the outlier fence and the dates on which the
    null rows cluster, which get recorded as a data-quality note.
    """
    for row in transfers:
        row["is_null_row"] = row["sender_id"] is None and row["recipient_id"] is None

    real = [r for r in transfers if not r["is_null_row"]]

    for row in transfers:
        row["is_self_transfer"] = (
            row["sender_id"] is not None and row["sender_id"] == row["recipient_id"])

    fence = _far_out_fence([r["amount"] for r in real])
    for row in transfers:
        amount = row["amount"]
        row["is_amt_outlier"] = (not row["is_null_row"]) and amount > fence
        row["is_round_amount"] = ((not row["is_null_row"])
                                  and amount >= ROUND_AMOUNT_FLOOR
                                  and float(amount).is_integer())

    _flag_reciprocal_pairs(real)
    _flag_fanout(real)

    flag_names = ("is_null_row", "is_self_transfer", "is_amt_outlier", "is_round_amount",
                  "is_reciprocal_pair", "is_fanout", "is_ambiguous_998")
    for row in transfers:
        for name in flag_names:
            row.setdefault(name, False)
        row["flags"] = "|".join(n[3:] for n in flag_names if row[n])
        row["is_clean"] = row["flags"] == ""

    outage_dates = sorted({r["date"] for r in transfers if r["is_null_row"]})
    return {
        "outlier_fence": fence,
        "outage_dates": outage_dates,
        "null_rows": sum(1 for r in transfers if r["is_null_row"]),
        "flagged": sum(1 for r in transfers if not r["is_clean"]),
    }


def _far_out_fence(amounts: Iterable[float]) -> float:
    """Tukey far-out fence: robust to the very outliers it is looking for,
    unlike a mean/stdev rule which the plants would drag upward."""
    values = sorted(amounts)
    if len(values) < 4:
        return float("inf")
    q1 = _quantile(values, 0.25)
    q3 = _quantile(values, 0.75)
    return q3 + IQR_FAR_OUT * (q3 - q1)


def _quantile(sorted_values: list[float], q: float) -> float:
    position = (len(sorted_values) - 1) * q
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (position - low) * (sorted_values[high] - sorted_values[low])


def _flag_reciprocal_pairs(rows: list[dict[str, Any]]) -> None:
    """A -> B and B -> A for the same amount inside a week: a wash-trade shape.

    Structural, so it fires regardless of amount -- a low-value round trip is
    caught even though the outlier rule would miss it.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        pair = tuple(sorted((row["sender_id"], row["recipient_id"]), key=lambda v: (v is None, v)))
        groups[(pair, row["amount"])].append(row)

    for group in groups.values():
        senders = {r["sender_id"] for r in group}
        dates = [r["date"] for r in group]
        if len(senders) > 1 and max(dates) - min(dates) <= RECIPROCAL_WINDOW:
            for row in group:
                row["is_reciprocal_pair"] = True


def _flag_fanout(rows: list[dict[str, Any]]) -> None:
    """One sender paying several recipients on a single day: a structuring shape."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["sender_id"], row["date"])].append(row)

    for group in groups.values():
        if len({r["recipient_id"] for r in group}) >= FANOUT_MIN_RECIPIENTS:
            for row in group:
                row["is_fanout"] = True
