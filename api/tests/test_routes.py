import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.settings import Settings

SAMPLE_LOT_A = "0000-X-00000-0000-00"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, site_source="mock")))


def test_health_reports_source_and_versions(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["site_source"] == "mock"
    assert body["illustrative"] is True
    assert set(body["versions"]) == {"engine", "ruleset", "schema_version", "data_as_of"}


@pytest.mark.parametrize("parcel_id", [SAMPLE_LOT_A, "0000X00000000000", "0000-x-00000-0000-00"])
def test_analysis_accepts_dashed_and_compact_ids(client: TestClient, parcel_id: str) -> None:
    response = client.get(f"/api/parcels/{parcel_id}/analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["parcel"]["parcel_id"] == SAMPLE_LOT_A
    assert body["meta"]["illustrative"] is True


def test_analysis_unknown_parcel_is_404(client: TestClient) -> None:
    assert client.get("/api/parcels/9999-Z-99999-9999-99/analysis").status_code == 404


def test_analysis_rejects_non_parcel_id(client: TestClient) -> None:
    assert client.get("/api/parcels/16-E-25/analysis").status_code == 422


def test_evidence_linked_from_sample_lot_a(client: TestClient) -> None:
    analysis = client.get(f"/api/parcels/{SAMPLE_LOT_A}/analysis").json()
    evidence_id = analysis["best_with_approvals"]["evidence_id"]
    body = client.get(f"/api/evidence/{evidence_id}").json()
    assert body["id"] == evidence_id
    assert client.get("/api/evidence/nope").status_code == 404


def test_cors_allows_the_web_dev_server(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
