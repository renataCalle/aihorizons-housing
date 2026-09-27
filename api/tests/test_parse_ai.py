"""The AI parser with a stand-in client: no network, no key. The live check is the eval
(`uv run pytest -m eval -s` with ANTHROPIC_API_KEY set)."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from navigator_api.main import create_app
from navigator_api.models import SearchFilters
from navigator_api.search.parse import parse
from navigator_api.search.parse_ai import AIParser, filters_schema
from navigator_api.search.vocabulary import NEIGHBORHOODS
from navigator_api.settings import Settings


class FakeMessages:
    def __init__(self, answer):
        self.answer = answer
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def tool_answer(tool_input: dict) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name="apply_filters", input=tool_input)
    return SimpleNamespace(content=[block], stop_reason="tool_use")


def parser(answer) -> tuple[AIParser, FakeMessages]:
    ai = AIParser("test-key", "claude-haiku-4-5")
    fake = FakeMessages(answer)
    ai.client = SimpleNamespace(messages=fake)
    return ai, fake


def test_schema_is_inline_and_names_only_real_neighborhoods() -> None:
    schema = filters_schema()
    assert "$ref" not in str(schema) and "$defs" not in schema
    assert schema["properties"]["areas"]["items"]["enum"] == NEIGHBORHOODS
    assert "default" not in str(schema["properties"]["sort"])


def test_forced_tool_call_fills_only_the_asked_fields() -> None:
    ai, fake = parser(
        tool_answer(
            {
                "filters": {
                    "product": {"type": "townhome", "units": 3},
                    "areas": ["Hazelwood"],
                    "max_land_price": 25000,
                },
                "readings": [{"phrase": "3 townhomes", "interpreted_as": "Townhomes, 3+"}],
                "not_understood": ["good schools"],
            }
        )
    )
    current = SearchFilters(vacant_only=True)
    result = parse("3 townhomes in Hazelwood under $25k with good schools", current, ai)
    assert result.parser == "ai"
    assert result.filters.product.type == "townhome" and result.filters.product.units == 3
    assert result.filters.areas == ["Hazelwood"]
    assert result.filters.max_land_price == 25000
    assert result.filters.vacant_only  # kept from the current filters
    assert result.not_understood == ["good schools"]
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "apply_filters"}
    assert '"vacant_only":true' in call["messages"][0]["content"]


def test_aliases_expand_and_unknown_places_are_set_aside() -> None:
    ai, _ = parser(
        tool_answer(
            {"filters": {"areas": ["Lawrenceville", "Atlantis"]}, "readings": [],
             "not_understood": []}
        )
    )  # fmt: skip
    result = parse("lots in Lawrenceville or Atlantis", None, ai)
    assert result.filters.areas == [
        "Lower Lawrenceville", "Central Lawrenceville", "Upper Lawrenceville",
    ]  # fmt: skip
    assert "Atlantis" in result.not_understood


def test_invalid_values_go_to_not_understood() -> None:
    ai, _ = parser(
        tool_answer(
            {"filters": {"min_score": 500, "sort": "cheapest"}, "readings": [],
             "not_understood": []}
        )
    )  # fmt: skip
    result = parse("cheap lots scoring 500", None, ai)
    assert result.filters.sort == "cheapest"
    assert result.filters.min_score is None
    assert "min_score" in result.not_understood


def test_api_errors_fall_back_to_the_rules() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    ai, _ = parser(anthropic.APIConnectionError(request=request))
    result = parse("3 townhomes in Hazelwood", None, ai)
    assert result.parser == "rules"
    assert result.filters.product.type == "townhome"


def test_no_tool_call_falls_back_to_the_rules() -> None:
    ai, _ = parser(SimpleNamespace(content=[], stop_reason="end_turn"))
    assert parse("flat lots", None, ai).parser == "rules"


def test_answers_are_cached_and_not_changed_by_merging() -> None:
    ai, fake = parser(
        tool_answer({"filters": {"product": {"units": 2}}, "readings": [], "not_understood": []})
    )
    current = SearchFilters.model_validate({"product": {"type": "duplex"}})
    first = parse("2 homes", current, ai)
    second = parse("2 homes", current, ai)
    assert len(fake.calls) == 1
    assert first.filters == second.filters
    assert first.filters.product.type == "duplex"


def test_ids_and_addresses_never_reach_the_model() -> None:
    ai, fake = parser(tool_answer({"filters": {}, "readings": [], "not_understood": []}))
    parse("52-H-93", None, ai)
    parse("3525 Beechwood Blvd", None, ai)
    assert fake.calls == []


@pytest.mark.parametrize("key", [None, "test-key"])
def test_health_says_whether_ai_search_is_on(key: str | None) -> None:
    app = create_app(Settings(_env_file=None, site_source="pipeline", anthropic_api_key=key))
    assert TestClient(app).get("/api/health").json()["ai_search"] is (key is not None)


def test_what_the_rules_cannot_map_is_always_reported() -> None:
    ai, _ = parser(
        tool_answer({"filters": {"product": {"type": "duplex"}}, "readings": [],
                     "not_understood": []})
    )  # fmt: skip
    result = parse("rental duplex", None, ai)
    assert result.parser == "ai"
    assert result.not_understood == ["rental"]
    # The cached answer is not changed by it.
    assert parse("rental duplex", None, ai).not_understood == ["rental"]


def test_readings_nested_in_the_filters_are_lifted_out() -> None:
    ai, _ = parser(
        tool_answer(
            {"filters": {"vacant_only": True, "not_understood": ["views"],
                         "readings": [{"phrase": "vacant", "interpreted_as": "Vacant only"}]}}
        )
    )  # fmt: skip
    result = parse("vacant lots with views", None, ai)
    assert result.filters.vacant_only
    assert result.not_understood[0] == "views"
    assert [r.phrase for r in result.readings] == ["vacant"]
