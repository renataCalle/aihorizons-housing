import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.models import SearchFilters
from navigator_api.search.query import approval_path
from navigator_api.search.vocabulary import chip_labels, without
from navigator_api.settings import Settings

SAMPLE = {
    "product": {"type": "townhome", "units": 3},
    "areas": ["Hazelwood"],
    "approval_paths": ["by_right"],
    "max_land_price": 25000,
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, site_source="mock")))


def post(client: TestClient, filters: dict) -> dict:
    response = client.post("/api/search", json=filters)
    assert response.status_code == 200, response.text
    return response.json()


def test_no_filters_returns_every_candidate_ranked_by_score(client: TestClient) -> None:
    body = post(client, {})
    scores = [
        r["parcel"]["score"] if r["parcel"]["score"] is not None else -1 for r in body["results"]
    ]
    assert body["total"] == len(body["results"]) > 50
    assert scores == sorted(scores, reverse=True)
    assert [r["rank"] for r in body["results"]] == list(range(1, body["total"] + 1))
    assert all(r["parcel"]["candidate"] for r in body["results"])


def test_sample_prompt_is_empty_by_right_and_suggests_what_to_drop(client: TestClient) -> None:
    body = post(client, SAMPLE)
    assert body["total"] == 0
    assert [c["label"] for c in body["chips"]] == [
        "Townhomes · 3",
        "Hazelwood",
        "By-right only",
        "Land ≤ $25k",
    ]
    assert body["suggestion"]["remove"] == {"key": "approval_paths", "label": "By-right only"}


def test_without_by_right_sample_lot_a_ranks_first(client: TestClient) -> None:
    body = post(client, {**SAMPLE, "approval_paths": []})
    first = body["results"][0]
    assert first["parcel"]["display_name"] == "Sample lot A"
    assert first["fit"]["product_type"] == "townhome" and first["fit"]["units"] >= 3
    assert all(r["parcel"]["neighborhood"] == "Hazelwood" for r in body["results"])
    assert all(r["parcel"]["assessed_land"] <= 25000 for r in body["results"])


def test_near_misses_fail_exactly_one_filter(client: TestClient) -> None:
    body = post(client, {**SAMPLE, "show_near_misses": True})
    assert body["near_misses"]
    matched = {r["parcel"]["parcel_id"] for r in body["results"]}
    assert all(n["parcel"]["parcel_id"] not in matched for n in body["near_misses"])


def test_unknown_facts_only_pass_when_unknowns_are_included(client: TestClient) -> None:
    flat = post(client, {"max_steep_slope_pct": 5})
    strict = post(client, {"max_steep_slope_pct": 5, "include_unknowns": False})
    unknown = [r for r in flat["results"] if r["parcel"]["steep_slope_share"] is None]
    assert unknown, "the mock data has lots with unknown slope (outside the city)"
    assert all(r["parcel"]["steep_slope_share"] is not None for r in strict["results"])


def test_filters_without_data_are_reported_not_applied(client: TestClient) -> None:
    body = post(client, {"near": [{"feature": "grocery", "within_ft": 1320}]})
    assert [c["key"] for c in body["not_applied"]] == ["near:grocery"]
    assert body["total"] == post(client, {})["total"]


@pytest.mark.parametrize("sort", ["headroom_desc", "fastest", "cheapest"])
def test_every_sort_returns_the_same_sites(client: TestClient, sort: str) -> None:
    ids = {r["parcel"]["parcel_id"] for r in post(client, {"sort": sort})["results"]}
    assert ids == {r["parcel"]["parcel_id"] for r in post(client, {})["results"]}


def test_cheapest_sorts_by_land_value(client: TestClient) -> None:
    land = [r["parcel"]["assessed_land"] for r in post(client, {"sort": "cheapest"})["results"]]
    known = [v for v in land if v is not None]
    assert known == sorted(known)


@pytest.mark.parametrize(
    ("outcome", "reliefs", "path"),
    [
        ("by_right", [], "by_right"),
        ("needs_approval", ["subdivision"], "administrative"),
        ("needs_approval", ["special_exception", "subdivision"], "special_exception"),
        ("needs_approval", ["variance", "subdivision"], "variance"),
        ("rejected", ["implausible"], "not_allowed"),
    ],
)
def test_approval_paths(outcome: str, reliefs: list[str], path: str) -> None:
    assert approval_path(outcome, reliefs) == path


def test_removing_each_chip_removes_only_that_chip() -> None:
    f = SearchFilters.model_validate(
        {**SAMPLE, "areas": ["Hazelwood", "Greenfield"], "exclude_constraints": ["undermined"]}
    )
    for key, _ in chip_labels(f):
        remaining = [k for k, _ in chip_labels(without(f, key))]
        assert key not in remaining
        assert len(remaining) == len(chip_labels(f)) - 1


def test_neighborhoods_lists_all_90_with_candidate_counts(client: TestClient) -> None:
    body = client.get("/api/neighborhoods").json()
    assert len(body) == 90
    assert next(n for n in body if n["name"] == "Hazelwood")["candidates"] > 0


def test_several_areas_match_lots_in_any_of_them(client: TestClient) -> None:
    def total(areas: list[str]) -> int:
        body = client.post("/api/search", json={"areas": areas}).json()
        return body["total"]

    hazelwood, greenfield = total(["Hazelwood"]), total(["Greenfield"])
    assert hazelwood > 0 and greenfield > 0
    assert total(["Hazelwood", "Greenfield"]) == hazelwood + greenfield


def test_several_areas_are_suggested_for_removal_together() -> None:
    f = SearchFilters.model_validate({"areas": ["Hazelwood", "Greenfield"]})
    assert without(f, "areas").areas == []
