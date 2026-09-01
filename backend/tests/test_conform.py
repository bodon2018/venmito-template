"""Conforming, entity resolution and the flag rules. No database involved."""
import pytest

from app.conform.identity import resolve_identities
from app.conform.normalize import parse_dob, parse_id, split_city, split_name
from app.conform.people import merge_people
from app.conform import pipeline as conform
from app.ingestion import detect_format, read_file


@pytest.fixture(scope="module")
def merged(source_files):
    batches = [(name, read_file(source_files[name],
                                detect_format(source_files[name], name), "people").records)
               for name in ("people.json", "people.yml")]
    return merge_people(batches, precedence=("people.json", "people.yml"))


@pytest.fixture(scope="module")
def resolution(merged):
    return resolve_identities(merged)


# ------------------------------------------------------------- normalisation
def test_normalisers_handle_both_source_conventions():
    assert parse_id("0001") == parse_id(1) == 1
    assert parse_dob("05/20/2000") == parse_dob("May 20, 2000")
    assert split_name("Jamie Bright") == ("Jamie", "Bright")
    # rpartition, so a comma inside the city name survives
    assert split_city("Santa Claus, USA") == ("Santa Claus", "USA")


# -------------------------------------------------------------------- people
def test_outer_join_keeps_every_id(merged):
    assert len(merged.people) == 1002
    assert not set(range(1, 1003)) - set(merged.people)


def test_outer_join_keeps_countries_absent_from_json(merged):
    """Taking either file alone silently drops whole countries."""
    countries = {p["country"] for p in merged.people.values()}
    assert {"France", "Spain"} <= countries


def test_conflicts_are_reported_not_silently_resolved(merged):
    assert len(merged.conflicts) == 1
    assert merged.conflicts[0]["id"] == 998


# ------------------------------------------------------------------ identity
def test_duplicate_entity_is_collapsed(resolution):
    assert resolution.canonical[1002] == 998
    assert len({v for v in resolution.canonical.values()}) == 1001


def test_retired_keys_still_resolve(resolution):
    """A merged duplicate's old email must still find the surviving entity."""
    assert resolution.resolve_email("fey_kuser@example.com") == 998
    assert resolution.resolve_email("fey.kuser@example.com") == 998


# ---------------------------------------------------------------- promotions
def test_every_promotion_resolves_to_a_person(source_files, resolution):
    records = read_file(source_files["promotions.csv"], "csv", "promotions").records
    batch = conform.conform_promotions(records, resolution)
    assert batch.stats["promotions"] == 236
    assert batch.stats["resolved"] == 236
    assert batch.stats["ambiguous_source_ids"] == 26


# -------------------------------------------------------------- transactions
def test_prices_are_recomputed_and_flagged_not_dropped(source_files, resolution):
    records = read_file(source_files["transactions.xml"], "xml", "transactions").records
    batch = conform.conform_transactions(records, resolution)
    assert batch.stats["line_items"] == 360          # nothing dropped
    assert batch.stats["items_needing_review"] == 2
    assert batch.stats["duplicates"] == 1
    assert batch.stats["orphans"] == 4

    bad = [i for t in batch.rows for i in t["items"] if i["needs_review"]]
    assert {i["price_reported"] for i in bad} == {0.0, -50.0}
    assert all(i["price"] > 0 for i in bad)          # recomputed values are sane


# ------------------------------------------------------------------ transfers
def test_transfer_flags(source_files, resolution):
    records = read_file(source_files["transfers.csv"], "csv", "transfers").records
    batch = conform.conform_transfers(records, resolution)
    assert batch.stats["transfers"] == 614           # nothing dropped
    assert batch.stats["null_rows"] == 15
    assert len(batch.notes) == 3                     # one outage note per date

    flags = lambda name: sum(1 for r in batch.rows if r[name])  # noqa: E731
    assert flags("is_self_transfer") == 56           # 55 collapse from the merged entity
    assert flags("is_reciprocal_pair") == 5          # the 777<->888 wash pattern
    assert flags("is_fanout") == 3                   # same-day structuring


def test_outlier_fence_is_derived_not_hardcoded(source_files, resolution):
    records = read_file(source_files["transfers.csv"], "csv", "transfers").records
    batch = conform.conform_transfers(records, resolution)
    assert 160 < batch.stats["outlier_fence"] < 170
