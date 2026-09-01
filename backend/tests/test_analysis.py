"""Analysis module shape checks.

These assert structure, not values: the numbers depend on what has been
uploaded, but the contract the frontend consumes must not drift.
"""
import pytest

from app.analysis.service import SECTIONS, build_report

pytest.importorskip("sqlalchemy")


@pytest.fixture(scope="module")
def session():
    """Skips cleanly when no database is configured."""
    from app.config import settings
    if not settings.database_url:
        pytest.skip("DATABASE_URL not set")
    from app.db.session import session_scope
    with session_scope() as s:
        yield s


@pytest.mark.parametrize("name", sorted(SECTIONS))
def test_every_section_runs(session, name):
    result = SECTIONS[name](session)
    assert isinstance(result, dict) and result


def test_report_has_every_section_plus_headlines(session):
    report = build_report(session)
    assert set(SECTIONS) <= set(report)
    assert report["headlines"] and all(
        {"title", "text"} <= set(h) for h in report["headlines"])


def test_rates_are_fractions_not_percentages(session):
    """Presentation is the caller's job; the API returns 0.45, not '45%'."""
    report = build_report(session)
    for row in report["promotions"]["by_promotion"]:
        assert 0.0 <= row["response_rate"] <= 1.0


def test_revenue_is_named_revenue_not_profit(session):
    """There is no cost data, so nothing may be labelled profit."""
    stores = SECTIONS["stores"](session)
    assert "profit" not in str(stores["by_store"]).lower()
    assert "not margin" in stores["measure_note"]


# ------------------------------------------------------------- upload modes
def test_mode_must_be_append_or_replace(session):
    """A typo must not silently fall back to a destructive default."""
    from app.services.ingest_service import ingest_upload
    import pytest as _pytest
    with _pytest.raises(ValueError):
        ingest_upload(session, filename="x.csv", content=b"a,b\n1,2\n", mode="wipe")


def test_append_is_the_default(session):
    """Defaulting to append means a re-upload can never destroy rows."""
    import inspect
    from app.services.ingest_service import ingest_upload
    assert inspect.signature(ingest_upload).parameters["mode"].default == "append"
