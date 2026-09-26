import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.settings import Settings

SAMPLE_LOT_A = "0000X00000000000"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, site_source="mock")))


def ids(body: dict) -> list[str]:
    return [m["parcel"]["parcel_id"] for m in body["matches"]]


def test_partial_dashed_county_id_finds_sample_lot_a(client: TestClient) -> None:
    body = client.get("/api/lookup", params={"q": "0000-X-00000"}).json()
    assert body["kind"] == "parcel_id" and body["format"] == "county"
    assert ids(body)[0] == SAMPLE_LOT_A
    assert body["matches"][0]["parcel"]["display_name"] == "Sample lot A"


def test_short_prefix_is_capped_at_eight(client: TestClient) -> None:
    body = client.get("/api/lookup", params={"q": "0000X0"}).json()
    assert len(body["matches"]) == 8


def test_block_lot_exact_match_first(client: TestClient) -> None:
    body = client.get("/api/lookup", params={"q": "55-A-137"}).json()
    assert body["format"] == "block_lot"
    assert ids(body) == ["0055A00137000000"]


def test_address_ignores_case_and_suffix_spelling(client: TestClient) -> None:
    body = client.get("/api/lookup", params={"q": "123 sample street"}).json()
    assert body["kind"] == "address"
    assert ids(body)[0] == SAMPLE_LOT_A


def test_description_is_not_looked_up(client: TestClient) -> None:
    body = client.get("/api/lookup", params={"q": "3 townhomes in Hazelwood"}).json()
    assert body == {"kind": "description", "format": None, "matches": []}


def test_unknown_id_returns_no_matches(client: TestClient) -> None:
    assert client.get("/api/lookup", params={"q": "9999-Z-99999"}).json()["matches"] == []


def test_text_starting_with_a_house_number_is_looked_up_as_an_address(client: TestClient) -> None:
    body = client.get("/api/lookup", params={"q": "123 sample"}).json()
    assert body["kind"] == "description"
    assert ids(body)[0] == SAMPLE_LOT_A
    assert body["matches"][0]["matched_on"] == "address"
