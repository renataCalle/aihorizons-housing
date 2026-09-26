import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.models import SearchFilters
from navigator_api.search.parse import parse
from navigator_api.settings import Settings


def filters_of(text: str, current: SearchFilters | None = None) -> dict:
    return parse(text, current).filters.model_dump(exclude_defaults=True)


def test_sample_prompt() -> None:
    result = parse("3 townhomes in Hazelwood under $25k, no hearing", None)
    assert result.filters.product.type == "townhome"
    assert result.filters.product.units == 3
    assert result.filters.areas == ["Hazelwood"]
    assert result.filters.approval_paths == ["by_right"]
    assert result.filters.max_land_price == 25000
    assert [c.label for c in result.chips] == [
        "Townhomes · 3", "Hazelwood", "By-right only", "Land ≤ $25k",
    ]  # fmt: skip
    assert {r.phrase for r in result.readings} >= {"no hearing", "under $25k"}
    assert result.parser == "rules"


def test_cheap_sorts_and_never_invents_a_price_cap() -> None:
    assert filters_of("cheap flat lots") == {"max_steep_slope_pct": 5, "sort": "cheapest"}


def test_nicknames_expand_but_exact_names_win() -> None:
    assert filters_of("lots in the Hill")["areas"] == [
        "Crawford-Roberts", "Middle Hill", "Upper Hill", "Terrace Village", "Bedford Dwellings",
    ]  # fmt: skip
    assert filters_of("Squirrel Hill South")["areas"] == ["Squirrel Hill South"]


def test_typos() -> None:
    assert filters_of("towhnomes in hazlewood") == {
        "product": {"type": "townhome"},
        "areas": ["Hazelwood"],
    }


def test_unsupported_asks_are_reported_not_guessed() -> None:
    result = parse("rental duplex near good schools in Mt Lebanon", None)
    assert set(result.not_understood) >= {"rental", "good schools", "Mt Lebanon"}
    assert result.filters.areas == []


def test_merges_with_current_filters() -> None:
    current = SearchFilters.model_validate(
        {"product": {"type": "duplex", "units": 2}, "areas": ["Greenfield"]}
    )
    merged = filters_of("3 homes by right", current)
    assert merged["product"] == {"type": "duplex", "units": 3}  # the type is kept
    assert merged["areas"] == ["Greenfield"]
    assert merged["approval_paths"] == ["by_right"]


@pytest.mark.parametrize("text", ["0088-B-00044", "3525 Beechwood Blvd", "16-E-25"])
def test_ids_and_addresses_are_never_parsed(text: str) -> None:
    result = parse(text, None)
    assert result.detected != "description"
    assert result.filters == SearchFilters()


def test_parse_endpoint() -> None:
    client = TestClient(create_app(Settings(_env_file=None, site_source="mock")))
    body = client.post("/api/search/parse", json={"text": "duplex lots in greenfield"}).json()
    assert body["filters"]["product"]["type"] == "duplex"
    assert body["chips"][0]["label"] == "Duplex"
