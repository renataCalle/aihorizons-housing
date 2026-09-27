import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.settings import Settings

SAMPLE_LOT_A = "0000X00000000000"
GOLDEN_STEEP_SLOPE = "0055A00137000000"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, site_source="mock")))


def test_health_reports_source_and_versions(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["site_source"] == "mock"
    assert body["illustrative"] is True
    assert body["parcels"] > 200
    assert set(body["versions"]) == {"engine", "ruleset", "schema", "data_as_of"}


@pytest.mark.parametrize("parcel_id", [SAMPLE_LOT_A, "0000-X-00000-0000-00", "0000x00000000000"])
def test_report_accepts_compact_and_dashed_ids(client: TestClient, parcel_id: str) -> None:
    response = client.get(f"/api/parcels/{parcel_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["parcel"]["parcel_id"] == SAMPLE_LOT_A
    assert body["parcel"]["display_name"] == "Sample lot A"
    assert body["parcel"]["illustrative"] is True
    assert body["analysis"]["verdict"]["score"] == body["parcel"]["score"]


def test_golden_parcel_is_real_engine_output(client: TestClient) -> None:
    body = client.get(f"/api/parcels/{GOLDEN_STEEP_SLOPE}").json()
    assert body["parcel"]["illustrative"] is False
    assert body["parcel"]["block_lot"] == "55-A-137"
    assert body["analysis"]["versions"]["schema"] == "0.1.0"
    assert body["analysis"]["rule_checks"]["programs"]
    # The golden context is a stored copy: no live lookups, parcels dated.
    assert body["freshness"]["live"] == []
    assert body["freshness"]["parcels_as_of"]


def test_report_scores_the_requested_building(client: TestClient) -> None:
    pick = client.get(f"/api/parcels/{GOLDEN_STEEP_SLOPE}").json()
    assert pick["program"] is None
    body = client.get(
        f"/api/parcels/{GOLDEN_STEEP_SLOPE}", params={"product_type": "townhome", "units": 2}
    ).json()
    assert body["program"] == {"product_type": "townhome", "units": 2}
    lead = body["analysis"]["options"]
    assert not lead or any(o["product_type"] == "townhome" for o in lead)
    # Without a building type the stored analysis is served unchanged.
    assert pick["analysis"] == client.get(f"/api/parcels/{GOLDEN_STEEP_SLOPE}").json()["analysis"]


def test_requested_building_needs_stored_facts(client: TestClient) -> None:
    body = client.get(f"/api/parcels/{SAMPLE_LOT_A}", params={"product_type": "duplex"}).json()
    assert body["program"] is None


def test_generated_lot_has_no_stored_facts(client: TestClient) -> None:
    assert client.get(f"/api/parcels/{SAMPLE_LOT_A}").json()["freshness"] is None


def test_non_candidate_has_no_analysis(client: TestClient) -> None:
    features = client.get("/api/map/parcels").json()["features"]
    other = next(f["properties"] for f in features if not f["properties"]["candidate"])
    body = client.get(f"/api/parcels/{other['parcel_id']}").json()
    assert body["analysis"] is None
    assert body["parcel"]["band"] is None


def test_unknown_parcel_is_404(client: TestClient) -> None:
    assert client.get("/api/parcels/9999Z99999999999").status_code == 404


def test_block_lot_is_not_a_county_id(client: TestClient) -> None:
    assert client.get("/api/parcels/55-A-137").status_code == 422


def test_map_parcels_are_wgs84_with_band_and_score(client: TestClient) -> None:
    body = client.get("/api/map/parcels").json()
    assert body["type"] == "FeatureCollection"
    sample = next(f for f in body["features"] if f["properties"]["parcel_id"] == SAMPLE_LOT_A)
    lon, lat = sample["geometry"]["coordinates"][0][0]
    assert -80.1 < lon < -79.8 and 40.3 < lat < 40.6  # Pittsburgh, not State Plane feet
    assert sample["properties"]["band"] is not None
    assert sample["properties"]["score"] is not None


def test_map_features_include_transit_and_neighborhoods(client: TestClient) -> None:
    kinds = {f["properties"]["kind"] for f in client.get("/api/map/features").json()["features"]}
    assert {"transit_stop", "park", "neighborhood"} <= kinds


def test_generated_lot_gets_the_illustrative_cases(client: TestClient) -> None:
    body = client.get("/api/parcels/0000X00012000000/evidence/option.with_relief").json()
    assert body["illustrative"] is True
    assert body["precedent"]["status"] == "illustrative"
    assert body["precedent"]["cases"]


def test_golden_lot_never_gets_the_illustrative_cases(client: TestClient) -> None:
    # A real parcel served by the mock source: its decisions are unavailable, not mocked.
    body = client.get(f"/api/parcels/{GOLDEN_STEEP_SLOPE}/evidence/option.with_relief").json()
    assert body["illustrative"] is False
    assert body["precedent"]["status"] == "unavailable"
    assert body["precedent"]["cases"] == []


def test_cors_allows_the_web_dev_server(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_mock_examples_are_the_mockups(client: TestClient) -> None:
    assert client.get("/api/examples").json() == {
        "parcel_id": "0000-X-00000",
        "address": "123 Sample St",
        "prompt": "3 townhomes in Hazelwood under $25k",
    }
