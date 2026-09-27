"""The searched lots at a glance (POST /api/search/summary), on the real results bundle."""

import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.search.area import MAX_BLOCKERS, driver_of
from navigator_api.settings import Settings


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, site_source="pipeline")))


def post(client: TestClient, path: str, filters: dict) -> dict:
    response = client.post(path, json=filters)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "filters", [{"areas": ["Hazelwood"]}, {"areas": ["Hazelwood"], "product": {"type": "townhome"}}]
)
def test_counts_match_the_search(client: TestClient, filters: dict) -> None:
    summary = post(client, "/api/search/summary", filters)
    results = post(client, "/api/search", filters)
    assert summary["lots"] == results["total"]
    assert sum(summary["bands"].values()) == results["total"]
    ranked = [r["scored"]["band"] for r in results["results"]]
    for band, count in summary["bands"].items():
        assert ranked.count(band) == count
    near = post(client, "/api/search", {**filters, "show_near_misses": True})
    assert summary["near_misses"] == len(near["near_misses"])


def test_blockers_add_up_the_engines_breakdown(client: TestClient) -> None:
    filters = {"areas": ["Hazelwood"]}
    summary = post(client, "/api/search/summary", filters)
    blockers = summary["blockers"]
    assert 0 < len(blockers) <= MAX_BLOCKERS
    totals = [b["lots"] * b["avg_points"] for b in blockers]
    assert totals == sorted(totals, reverse=True)
    # Recount the top breakdown driver from each result's stored analysis (land headroom is
    # checked in its own test).
    top = next(b for b in blockers if b["driver"] != "land_headroom")
    source = client.app.state.source
    ids = [r["parcel"]["parcel_id"] for r in post(client, "/api/search", filters)["results"]]
    hit = [
        pid
        for pid in ids
        if any(
            driver_of(i.driver_flag_id) == top["driver"] and i.points_lost > 0
            for i in source.analysis(pid).score_breakdown
        )
    ]
    assert top["lots"] == len(hit)
    assert top["label"] and top["label"] != top["driver"]


def test_no_results_means_empty_counts(client: TestClient) -> None:
    summary = post(client, "/api/search/summary", {"areas": ["Hazelwood"], "min_score": 99})
    assert (summary["lots"], summary["bands"], summary["blockers"]) == (0, {}, [])


def test_land_headroom_counts_the_component_shortfall(client: TestClient) -> None:
    filters = {"areas": ["Hazelwood"]}
    summary = post(client, "/api/search/summary", filters)
    source = client.app.state.source
    ids = [r["parcel"]["parcel_id"] for r in post(client, "/api/search", filters)["results"]]
    lost = [
        c.max_points - c.points
        for pid in ids
        if (a := source.analysis(pid))
        for c in a.verdict.components
        if c.key == "land_headroom" and c.points < c.max_points
    ]
    land = next(b for b in summary["blockers"] if b["driver"] == "land_headroom")
    assert land["lots"] == len(lost)
    assert land["avg_points"] == round(sum(lost) / len(lost), 1)
