"""The committed results bundle (results/) loads, validates, agrees with itself, and stays small
and free of personal data. Runs in CI; regenerate with `navigator_pipeline.publish`."""

import csv
import hashlib
import re

import pytest
from pydantic import TypeAdapter

from navigator_engine.rules_engine import TEMPLATES
from navigator_pipeline import bundle

R = bundle.RESULTS
pytestmark = pytest.mark.skipif(
    not (R / bundle.FILES["manifest"]).exists(), reason="no results bundle"
)
# Keys that would carry owner identity. The store drops these; the bundle must never have them.
PERSONAL_KEY = re.compile(r"owner(?!_type)|mail|taxpayer|grantee|grantor|buyer|seller", re.I)


@pytest.fixture(scope="module")
def b() -> bundle.Bundle:
    return bundle.load(R)  # validates every JSONL line against the contracts


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    with (R / bundle.FILES["summaries_csv"]).open() as f:
        return list(csv.DictReader(f))


def _keys(obj, out: set) -> set:
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)
    return out


def test_parcel_ids_agree_across_files(b: bundle.Bundle, rows: list[dict]) -> None:
    summaries = {s["parcel_id"] for s in b.summaries}
    candidates = {s["parcel_id"] for s in b.summaries if s["candidate"]}
    geometry = {f["properties"]["parcel_id"] for f in b.parcels["features"]}
    assert len(summaries) == len(b.summaries), "duplicate summaries"
    assert summaries == geometry
    assert candidates == set(b.analyses) == set(b.contexts)
    assert {r["parcel_id"] for r in rows} == candidates
    for pid, ctx in b.contexts.items():
        assert ctx.parcels[0].parcel_id == pid


def test_counts_match_the_manifest(b: bundle.Bundle, rows: list[dict]) -> None:
    c = b.manifest["counts"]
    assert c["parcels"] == len(b.summaries)
    assert c["candidates"] == len(b.analyses)
    assert c["csv_rows"] == len(rows)


def test_summaries_fit_the_api_models(b: bundle.Bundle) -> None:
    models = pytest.importorskip("navigator_api.models")
    TypeAdapter(list[models.ParcelSummary]).validate_python(b.summaries)
    models.MapFeatureCollection.model_validate(b.map_features)


def test_csv_has_one_row_per_building_type(b: bundle.Bundle, rows: list[dict]) -> None:
    assert list(rows[0]) == bundle.CSV_COLUMNS
    by_parcel: dict[str, list[dict]] = {}
    for r in rows:
        by_parcel.setdefault(r["parcel_id"], []).append(r)
    for pid, rs in by_parcel.items():
        assert sorted(r["product"] for r in rs) == sorted(TEMPLATES)
        leads = [r for r in rs if r["lead"] == "True"]
        a = b.analyses[pid]
        assert len(leads) == (1 if a.metrics else 0)
        if leads:  # the lead row repeats the engine's own analysis
            assert leads[0]["band"] == a.verdict.band
            assert float(leads[0]["score_p50"]) == round(a.verdict.score_range.p50, 1)


def test_summaries_copy_the_analysis(b: bundle.Bundle) -> None:
    for s in b.summaries:
        if s["candidate"]:
            a = b.analyses[s["parcel_id"]]
            assert (s["score"], s["band"]) == (a.verdict.score, a.verdict.band)
        else:
            assert s["score"] is None and s["band"] is None


def test_bundle_is_small() -> None:
    total = sum(p.stat().st_size for p in R.iterdir() if p.is_file())
    assert total < bundle.MAX_BYTES, f"{total / 1e6:.1f} MB"


def test_checksums_match(b: bundle.Bundle) -> None:
    for name, meta in b.manifest["files"].items():
        data = (R / name).read_bytes()
        assert len(data) == meta["bytes"], name
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name


def test_no_personal_data(b: bundle.Bundle, rows: list[dict]) -> None:
    keys = set(rows[0])
    for a in b.analyses.values():
        _keys(a.model_dump(), keys)
    for c in b.contexts.values():
        _keys(c.model_dump(), keys)
    _keys(b.summaries, keys)
    _keys(b.parcels["features"][0]["properties"], keys)
    assert not {k for k in keys if PERSONAL_KEY.search(k)}


def test_geometry_is_wgs84_and_rounded(b: bundle.Bundle) -> None:
    text = (R / bundle.FILES["parcels"]).read_text()
    assert not re.search(r"\d\.\d{7,}", text), "coordinates carry more than 6 decimals"
    for f in b.parcels["features"][:50]:
        ring = f["geometry"]["coordinates"][0]
        lon, lat = ring[0] if f["geometry"]["type"] == "Polygon" else ring[0][0]
        assert -81 < lon < -79 and 40 < lat < 41
