"""The API loads the pipeline's committed results bundle (results/README.md)."""

import json
import re
from pathlib import Path

import pytest

from navigator_api.search.lookup import lookup
from navigator_api.sources.bundle import read_text
from navigator_api.sources.pipeline import PipelineSiteSource, tidy_name

RESULTS = Path(__file__).resolve().parents[2] / "results"


@pytest.fixture(scope="module")
def source() -> PipelineSiteSource:
    # Loading validates every summary, context and analysis against the models, and checks
    # that every candidate has an analysis and every parcel a shape.
    return PipelineSiteSource(RESULTS)


def test_bundle_matches_its_manifest(source: PipelineSiteSource) -> None:
    counts = json.loads((RESULTS / "manifest.json").read_text())["counts"]
    summaries = source.summaries()
    assert len(summaries) == counts["parcels"]
    assert sum(s.candidate for s in summaries) == counts["candidates"]


def test_candidates_carry_the_fields_search_filters_on(source: PipelineSiteSource) -> None:
    scored = [s for s in source.summaries() if s.candidate and s.band != "not_scored"]
    assert scored
    # Program fits come from rule_checks; lots where no residential program applies
    # (e.g. zoned industrial) have none, and that's the engine's answer.
    checked = [s for s in scored if source.analysis(s.parcel_id).rule_checks]
    assert len(checked) > len(scored) / 2
    assert all(s.programs for s in checked)
    assert all(s.steep_slope_share is not None or s.neighborhood is None for s in scored)


def test_bundle_is_real_data(source: PipelineSiteSource) -> None:
    assert not source.illustrative()
    candidates = [s for s in source.summaries() if s.candidate]
    # Outside the city (a golden parcel in Wilkinsburg): no neighborhood, not scored.
    assert all(s.neighborhood or s.band == "not_scored" for s in candidates)


def test_parcel_shapes_are_wgs84(source: PipelineSiteSource) -> None:
    feature = source.parcels_geojson().features[0]
    lon, lat = feature.geometry["coordinates"][0][0][:2]
    assert -80.2 < lon < -79.8 and 40.3 < lat < 40.6


def test_examples_come_from_the_data(source: PipelineSiteSource) -> None:
    examples = source.examples()
    assert lookup(source.summaries(), examples.parcel_id).matches
    assert lookup(source.summaries(), examples.address).matches


def test_names_are_tidied() -> None:
    assert tidy_name("3864 2Nd Ave") == "3864 2nd Ave"
    assert tidy_name("Bristol St") == "Bristol St"


def test_no_owner_names() -> None:
    text = read_text(RESULTS / "summaries.json")
    assert not re.search(r'"owner(_name)?":', text), "owner type only, never owner names"
