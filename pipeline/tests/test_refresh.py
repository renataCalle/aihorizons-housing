"""Refresh decisions, offline."""

from datetime import UTC, datetime, timedelta

from navigator_pipeline.catalog import SOURCES, refresh_days
from navigator_pipeline.refresh import FEATURE_INPUTS, has_changed, is_due, tables_for

NOW = datetime(2026, 9, 27, 3, 0, tzinfo=UTC)


def _manifest(days_ago: float, as_of: str = "2026-09-20") -> dict:
    return {"fetched_at": (NOW - timedelta(days=days_ago)).isoformat(), "source_as_of": as_of}


def test_due_follows_the_cadence() -> None:
    assert is_due(None, 1, NOW)  # never fetched
    assert not is_due(_manifest(0.5), 1, NOW)
    assert is_due(_manifest(1.5), 1, NOW)
    assert not is_due(_manifest(10), 30, NOW)


def test_checked_at_resets_the_clock() -> None:
    m = _manifest(40) | {"checked_at": (NOW - timedelta(days=2)).isoformat()}
    assert not is_due(m, 30, NOW)


def test_change_detection() -> None:
    assert not has_changed(_manifest(3, "2026-09-20"), "2026-09-20")
    assert has_changed(_manifest(3, "2026-09-20"), "2026-09-26")
    assert has_changed(_manifest(3), None)  # the source can't say: re-fetch
    assert has_changed(None, "2026-09-26")


def test_rebuilds_only_dependent_tables() -> None:
    assert tables_for({"sales"}) == ["sales"]
    assert tables_for({"assessments"}) == ["parcels"]
    assert tables_for({"dep_aml_sites"}) == ["dep_aml"]
    assert "sales" not in FEATURE_INPUTS  # a sales refresh does not recompute parcel facts


def test_every_source_has_a_cadence() -> None:
    assert {refresh_days(s.key) for s in SOURCES} <= {1, 7, 30, 365}
    assert refresh_days("sales") == 1 and refresh_days("parcels") == 30
