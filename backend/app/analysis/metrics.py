"""The individual metrics, grouped by the question they answer.

Every function takes a Session and returns JSON-ready data. Percentages are
returned as fractions (0.45), not pre-formatted strings -- presentation is the
caller's job.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import queries as q


def _rows(session: Session, sql: str, **params) -> list[dict[str, Any]]:
    result = session.execute(text(sql), params or None).mappings().all()
    return [_clean(dict(row)) for row in result]


def _one(session: Session, sql: str, **params) -> dict[str, Any]:
    rows = _rows(session, sql, **params)
    return rows[0] if rows else {}


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    """Decimal and date are not JSON types; convert once, here."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            out[key] = float(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


# ------------------------------------------------------------- 1. clients
def client_base(session: Session) -> dict[str, Any]:
    """Who the clients are: size, geography, devices, age shape."""
    return {
        "summary": _one(session, q.CLIENT_BASE),
        "by_country": _rows(session, q.CLIENTS_BY_COUNTRY),
        "by_city": _rows(session, q.CLIENTS_BY_CITY),
        "devices": _rows(session, q.DEVICE_ADOPTION),
        "age_histogram": _rows(session, q.AGE_HISTOGRAM),
    }


# ---------------------------------------------------------- 2. promotions
def promotions(session: Session, roster_limit: int = 25) -> dict[str, Any]:
    """Which clients hold what, and how each promotion performed."""
    return {
        "overall": _one(session, q.PROMOTION_OVERALL),
        "by_promotion": _rows(session, q.PROMOTION_PERFORMANCE),
        "client_roster": _rows(session, q.CLIENT_PROMOTION_ROSTER, limit=roster_limit),
        "by_channel": _rows(session, q.PROMOTION_BY_CHANNEL),
        "by_month": _rows(session, q.PROMOTION_BY_MONTH),
    }


def turn_no_into_yes(session: Session) -> dict[str, Any]:
    """The 'No' responses worth chasing.

    A client who declined an offer for an item they already buy is not a
    product rejection -- the offer or the channel failed. That subset is the
    most actionable list the data supports.
    """
    affinity = _rows(session, q.PROMOTION_AFFINITY)
    retarget = _rows(session, q.RETARGET_LIST)

    by_promotion: dict[str, dict[str, Any]] = {}
    for row in retarget:
        entry = by_promotion.setdefault(row["promotion"],
                                        {"promotion": row["promotion"], "clients": 0, "spend": 0.0})
        entry["clients"] += 1
        entry["spend"] = round(entry["spend"] + (row["spend_on_item"] or 0), 2)

    rates = {r["segment"]: r["response_rate"] for r in affinity}
    lift = None
    if len(rates) == 2:
        lift = round(rates.get("has bought item", 0) - rates.get("never bought item", 0), 4)

    return {
        "affinity": affinity,
        "affinity_lift": lift,
        "retarget_list": retarget,
        "retarget_by_promotion": sorted(by_promotion.values(),
                                        key=lambda r: r["spend"], reverse=True),
        "addressable_spend": round(sum(r["spend_on_item"] or 0 for r in retarget), 2),
    }


# ----------------------------------------------------- 3. stores and items
def stores_and_items(session: Session) -> dict[str, Any]:
    """Best sellers and store performance.

    Revenue, not profit: the source has price but no cost, so margin cannot
    be derived. Named `revenue` throughout to keep that honest.
    """
    items = _rows(session, q.ITEM_PERFORMANCE)
    stores = _rows(session, q.STORE_PERFORMANCE)
    return {
        "best_seller_by_revenue": items[0] if items else None,
        "best_seller_by_units": max(items, key=lambda r: r["units"]) if items else None,
        "top_store_by_revenue": stores[0] if stores else None,
        "top_store_by_basket_value": (max(stores, key=lambda r: r["avg_order_value"])
                                      if stores else None),
        "by_item": items,
        "by_store": stores,
        "item_by_store": _rows(session, q.ITEM_BY_STORE),
        "monthly": _rows(session, q.MONTHLY_SALES),
        "spend_concentration": _one(session, q.SPEND_CONCENTRATION),
        "measure_note": "revenue = price x quantity; no cost data, so this is not margin",
    }


# ------------------------------------------------------------ 4. transfers
def transfers(session: Session, top_n: int = 10) -> dict[str, Any]:
    """What the transfer file supports beyond a running total."""
    flow = _rows(session, q.TRANSFER_NET_FLOW)
    participation = _one(session, q.TRANSFER_PARTICIPATION)
    participants = participation.get("participants") or 0
    clients = participation.get("clients") or 1

    return {
        "summary": _one(session, q.TRANSFER_SUMMARY),
        "participation": {
            **participation,
            "participation_rate": round(participants / clients, 4),
        },
        "top_net_receivers": sorted(flow, key=lambda r: r["net_flow"], reverse=True)[:top_n],
        "top_net_senders": sorted(flow, key=lambda r: r["net_flow"])[:top_n],
        "monthly": _rows(session, q.TRANSFER_MONTHLY),
        "cross_sell_audience": _one(session, q.CROSS_SELL_AUDIENCE),
    }


def transfer_risk(session: Session, limit: int = 25) -> dict[str, Any]:
    """Flagged transfers, kept deliberately.

    These rows are excluded from the revenue and behaviour metrics but are
    reported here: the wash-trade and fan-out patterns are the fraud signal.
    """
    return {
        "tags": _rows(session, q.RISK_TAGS),
        "flagged": _rows(session, q.FLAGGED_TRANSFERS, limit=limit),
    }


# ------------------------------------------------------- 5. cross-channel
def channel_coverage(session: Session) -> dict[str, Any]:
    """How much we actually know about each client, across the three channels."""
    rows = _rows(session, q.CHANNEL_COVERAGE)
    total = sum(r["clients"] for r in rows) or 1
    for row in rows:
        row["pct"] = round(100.0 * row["clients"] / total, 1)
    return {
        "by_channel_count": rows,
        "invisible_clients": next((r["clients"] for r in rows if r["channels"] == 0), 0),
    }


def data_quality(session: Session) -> dict[str, Any]:
    """What the ingestion flagged. Surfaced so a number is never quietly wrong."""
    return {
        "counts": _one(session, q.DATA_QUALITY),
        "outages": _rows(session, q.OUTAGE_DATES),
    }
