"""Building-type-aware ranking on the real results bundle (results/)."""

import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.settings import Settings

BIGELOW_356 = "0055F00286000000"  # 356 Bigelow St: single-family 61 (the pick), townhomes 43


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, site_source="pipeline")))


def search(client: TestClient, **filters) -> dict:
    return client.post("/api/search", json={"areas": ["Hazelwood"], **filters}).json()


def result(body: dict, parcel_id: str) -> dict:
    return next(r for r in body["results"] if r["parcel"]["parcel_id"] == parcel_id)


def test_townhome_search_ranks_by_the_townhome_score(client: TestClient) -> None:
    body = search(client, product={"type": "townhome"})
    assert body["ranked_for"] == {"type": "townhome", "units": None}
    lot = result(body, BIGELOW_356)
    assert lot["scored"]["product_type"] == "townhome"
    assert lot["scored"]["score"] == 43
    assert lot["scored"]["basis"] == "up_to" and lot["scored"]["units"] == 2
    # The pick is another type, so it's offered as the better fit.
    assert lot["better_fit"]["product_type"] == "single_family"
    assert lot["better_fit"]["score"] == 61
    scores = [r["scored"]["score"] for r in body["results"]]
    assert scores == sorted(scores, key=lambda s: -(s if s is not None else -1))
    # Ranked below every lot with a better townhome score.
    assert lot["rank"] == 1 + sum(1 for s in scores if s is not None and s > 43)


def test_search_without_a_type_ranks_by_the_pick(client: TestClient) -> None:
    body = search(client)
    assert body["ranked_for"] is None
    lot = result(body, BIGELOW_356)
    assert lot["scored"] == {**lot["scored"], "basis": "pick", "score": 61}
    assert lot["scored"]["product_type"] == "single_family"
    assert lot["better_fit"] is None


def test_exact_unit_count_is_marked_exact(client: TestClient) -> None:
    lot = result(search(client, product={"type": "townhome", "units": 2}), BIGELOW_356)
    assert lot["scored"]["basis"] == "exact"


def test_band_filter_reads_the_searched_type(client: TestClient) -> None:
    # 356 Bigelow is "with conditions" as a single-family home but high risk for townhomes.
    body = search(client, product={"type": "townhome"}, bands=["feasible_with_conditions"])
    assert BIGELOW_356 not in {r["parcel"]["parcel_id"] for r in body["results"]}
    assert all(r["scored"]["band"] == "feasible_with_conditions" for r in body["results"])


def test_mock_data_without_rows_falls_back_to_the_pick() -> None:
    mock = TestClient(create_app(Settings(_env_file=None, site_source="mock")))
    body = mock.post("/api/search", json={"product": {"type": "townhome"}}).json()
    assert body["results"]
    assert all(r["scored"]["basis"] == "pick" for r in body["results"])
