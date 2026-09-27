"""The committed real-data bundle (results/) loads and is consistent (results/README.md)."""

import json
import re
from pathlib import Path

import pytest

from navigator_api.sources.bundle import read_text
from navigator_api.sources.pipeline import PipelineSiteSource

RESULTS = Path(__file__).resolve().parents[2] / "results"


@pytest.fixture(scope="module")
def source() -> PipelineSiteSource:
    # Loading validates every summary and analysis against the models, and checks that
    # every candidate has an analysis and every parcel a shape.
    return PipelineSiteSource(RESULTS)


def test_bundle_matches_its_manifest(source: PipelineSiteSource) -> None:
    manifest = json.loads((RESULTS / "manifest.json").read_text())
    summaries = source.summaries()
    assert len(summaries) == manifest["counts"]["parcels"]
    assert sum(s.candidate for s in summaries) == manifest["counts"]["candidates_scored"]
    assert source.versions().schema_ == manifest["versions"]["schema"]


def test_bundle_is_real_data(source: PipelineSiteSource) -> None:
    assert not source.illustrative()
    # Candidates outside the city (a golden parcel in Wilkinsburg) have no city neighborhood
    # and are not scored: zoning isn't covered there.
    candidates = [s for s in source.summaries() if s.candidate]
    assert all(s.neighborhood or s.band == "not_scored" for s in candidates)


def test_parcel_shapes_are_wgs84(source: PipelineSiteSource) -> None:
    feature = source.parcels_geojson().features[0]
    lon, lat = feature.geometry["coordinates"][0][0][:2]
    assert -80.2 < lon < -79.8 and 40.3 < lat < 40.6


def test_no_owner_names() -> None:
    text = read_text(RESULTS / "summaries.json")
    assert not re.search(r'"owner(_name)?":', text), "owner type only, never owner names"


def test_examples_come_from_the_data(source: PipelineSiteSource) -> None:
    from navigator_api.search.lookup import lookup

    examples = source.examples()
    assert lookup(source.summaries(), examples.parcel_id).matches
    assert lookup(source.summaries(), examples.address).matches
