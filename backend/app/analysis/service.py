"""Assembles the metrics into a report.

Two audiences are served from the same numbers:
  * `headlines` -- plain sentences, for the non-technical view
  * everything else -- the underlying tables, for the technical view

Sections are addressable individually so a caller can refresh one panel
without recomputing the whole report.
"""
from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from . import metrics

# Section name -> the function that builds it.
SECTIONS: dict[str, Callable[[Session], dict[str, Any]]] = {
    "clients": metrics.client_base,
    "promotions": metrics.promotions,
    "turn_no_into_yes": metrics.turn_no_into_yes,
    "stores": metrics.stores_and_items,
    "transfers": metrics.transfers,
    "transfer_risk": metrics.transfer_risk,
    "channel_coverage": metrics.channel_coverage,
    "data_quality": metrics.data_quality,
}


def section(session: Session, name: str) -> dict[str, Any]:
    if name not in SECTIONS:
        raise KeyError(f"unknown section {name!r}; expected one of {sorted(SECTIONS)}")
    return SECTIONS[name](session)


def build_report(session: Session) -> dict[str, Any]:
    """The whole report, plus plain-language headlines derived from it."""
    report = {name: build(session) for name, build in SECTIONS.items()}
    report["headlines"] = _headlines(report)
    return report


def _headlines(report: dict[str, Any]) -> list[dict[str, str]]:
    """One sentence per finding, for readers who will not read a table.

    Written off the computed values rather than hardcoded, so they stay true
    when the data changes.
    """
    lines: list[dict[str, str]] = []

    clients = report["clients"]
    if clients["by_country"]:
        top = clients["by_country"][0]
        lines.append({
            "title": "Client base",
            "text": (f"{clients['summary']['clients']:,} clients across "
                     f"{clients['summary']['countries']} countries, median age "
                     f"{clients['summary']['median_age']:.0f}. "
                     f"{top['country']} is {top['pct']:.0f}% of the base."),
        })

    promo = report["promotions"]
    by_promo = promo["by_promotion"]
    if by_promo:
        best, worst = by_promo[0], by_promo[-1]
        lines.append({
            "title": "Promotions",
            "text": (f"Overall response {promo['overall']['response_rate']:.0%} across "
                     f"{promo['overall']['sent']} offers. Best: {best['promotion']} "
                     f"({best['response_rate']:.0%}); weakest: {worst['promotion']} "
                     f"({worst['response_rate']:.0%})."),
        })

    noyes = report["turn_no_into_yes"]
    if noyes["retarget_list"]:
        lines.append({
            "title": "Turning No into Yes",
            "text": (f"{len(noyes['retarget_list'])} clients declined an offer for an item "
                     f"they already buy (${noyes['addressable_spend']:,.0f} of existing "
                     f"spend). The product is not the problem -- the offer or channel is."),
        })

    stores = report["stores"]
    if stores["best_seller_by_revenue"]:
        rev, units = stores["best_seller_by_revenue"], stores["best_seller_by_units"]
        lines.append({
            "title": "Best seller",
            "text": (f"{rev['item']} leads revenue (${rev['revenue']:,.0f}); "
                     f"{units['item']} leads units ({units['units']:,.0f}). "
                     f"Ranking depends on the measure."),
        })
        store, basket = stores["top_store_by_revenue"], stores["top_store_by_basket_value"]
        lines.append({
            "title": "Stores",
            "text": (f"{store['store']} tops revenue (${store['revenue']:,.0f}); "
                     f"{basket['store']} has the best average order "
                     f"(${basket['avg_order_value']:,.2f}). No cost data, so this is "
                     f"revenue rather than profit."),
        })

    tf = report["transfers"]
    lines.append({
        "title": "Transfers",
        "text": (f"{tf['summary']['clean_transfers']:,} clean transfers moving "
                 f"${tf['summary']['value_moved']:,.0f}. "
                 f"{tf['participation']['participants']:,} clients participate "
                 f"({tf['participation']['participation_rate']:.0%}), and "
                 f"{tf['cross_sell_audience']['audience_size']:,} of them never buy in a "
                 f"store -- a cross-sell audience."),
    })

    risk = report["transfer_risk"]
    if risk["flagged"]:
        # Count from the flag totals, not from the truncated sample list.
        behavioural = report["data_quality"]["counts"]["behavioural_flagged"]
        lines.append({
            "title": "Risk",
            "text": (f"{behavioural} transfers carry behavioural tags "
                     f"(reciprocal round-trips, same-day fan-out, outlier amounts). "
                     f"They are retained, not deleted -- this is the fraud signal."),
        })

    quality = report["data_quality"]["counts"]
    lines.append({
        "title": "Data quality",
        "text": (f"{quality['orphan_transactions']} transactions match no client, "
                 f"{quality['items_needing_review']} line items had prices that "
                 f"disagreed with the source, {quality['null_transfers']} transfer rows "
                 f"were empty, and {report['channel_coverage']['invisible_clients']} "
                 f"clients show no activity in any channel."),
    })
    return lines
