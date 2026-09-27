"""The evidence drawer for real Hazelwood lots, served from the results bundle."""

import pytest
from fastapi.testclient import TestClient

from navigator_api.evidence import build_evidence
from navigator_api.main import create_app
from navigator_api.settings import Settings
from navigator_contracts.site_context import ZbaCase

STEEP_SLOPE = "0055A00137000000"  # deal risk: 84% of the lot on 25%+ slope
CONTEXTUAL = "0055A00225000000"  # relies on contextual side setbacks
SIMILAR_CASE = "0055E00248000000"  # needs a variance, with a similar zoning board case nearby


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, site_source="pipeline")))


def get(client: TestClient, parcel_id: str, evidence_id: str, **params: object) -> dict:
    response = client.get(f"/api/parcels/{parcel_id}/evidence/{evidence_id}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_finding_carries_the_engines_judgments(client: TestClient) -> None:
    body = get(client, STEEP_SLOPE, "flag.steep_slope")
    report = client.get(f"/api/parcels/{STEEP_SLOPE}").json()["analysis"]
    flag = next(f for f in report["flags"] if f["id"] == "steep_slope")
    assert body["kind"] == "finding"
    assert body["illustrative"] is False
    assert (body["title"], body["severity"], body["confidence"]) == (
        flag["title"],
        "high",
        flag["confidence"],
    )
    assert (body["cost_usd"], body["months"]) == (flag["cost_usd"], flag["months"])
    assert body["how_to_resolve"] == flag["resolution"]
    [source] = body["sources"]
    assert source["code_section"] == "915.02"
    assert source["as_of"] == "2026-09-23"
    assert source["url"].startswith("https://data.wprdc.org/")
    [section] = body["code_sections"]
    assert section["section"] == "915.02"
    assert section["title"] and section["summary"] and section["url"]
    assert body["resolved_by"]["order"] == flag["resolved_by_step"] == 3
    assert body["resolved_by"]["action"] == "Geotechnical and grading feasibility study"
    assert body["precedent"] is None


def test_approvals_option_lists_the_failing_rules(client: TestClient) -> None:
    body = get(client, STEEP_SLOPE, "option.with_relief")
    assert body["kind"] == "approvals"
    assert (body["product_type"], body["units"]) == ("townhome", 2)
    checks = {c["check_id"]: c for c in body["rule_checks"]}
    assert set(checks) == {"use_allowed", "subdivision"}
    assert checks["use_allowed"]["relief_type"] == "special_exception"
    assert checks["use_allowed"]["section"] == "911.04.A.69A"
    assert all(c["status"] in ("needs_approval", "rejected") for c in body["rule_checks"])
    assert body["approval_prob"]["p10"] <= body["approval_prob"]["p90"]
    assert body["entitlement_basis"]


def test_approvals_option_says_how_to_get_them(client: TestClient) -> None:
    body = get(client, STEEP_SLOPE, "option.with_relief")
    report = client.get(f"/api/parcels/{STEEP_SLOPE}").json()["analysis"]
    option = next(o for o in report["options"] if o["label"] == "with_relief")
    assert body["how_to_resolve"] == option["resolution"]
    assert body["resolved_by"]["order"] == option["resolved_by_step"] == 1
    assert body["resolved_by"]["action"] == "Zoning pre-application meeting"
    # The failing rules' sections, then the procedure the resolution cites (922.07).
    cited = [c["section"] for c in body["code_sections"]]
    assert cited == ["911.04.A.69A", "911.02", "922.07"]


def test_no_similar_cases_is_an_empty_list_not_unavailable(client: TestClient) -> None:
    # 137 needs a special exception; the board decided cases nearby, none of them similar.
    precedent = get(client, STEEP_SLOPE, "option.with_relief")["precedent"]
    assert precedent["status"] == "available"
    assert precedent["nearby"] > 0
    assert (precedent["total"], precedent["granted"], precedent["cases"]) == (0, 0, [])
    assert precedent["as_of"] and precedent["source"] and precedent["rule"]


def test_similar_cases_are_listed_without_links(client: TestClient) -> None:
    body = get(client, SIMILAR_CASE, "option.with_relief")
    report = client.get(f"/api/parcels/{SIMILAR_CASE}").json()["analysis"]
    option = next(o for o in report["options"] if o["label"] == "with_relief")
    precedent = body["precedent"]
    assert [c["case_id"] for c in precedent["cases"]] == option["similar_cases"]
    assert precedent["total"] == len(option["similar_cases"])
    case = precedent["cases"][0]
    assert case["decided"] and case["relief_types"] and case["outcome"]
    # Decisions name applicants: no links until that's settled (hackathon README limitations).
    assert all(c["source_url"] is None for c in precedent["cases"])


def test_code_rule_finding_is_dated_by_the_code_text(client: TestClient) -> None:
    body = get(client, CONTEXTUAL, "flag.contextual_setbacks")
    [source] = body["sources"]
    ruleset_as_of = body["versions"]["ruleset_as_of"]
    assert (source["code_section"], source["as_of"]) == ("925.06.C", ruleset_as_of)
    assert source["as_of_from_provenance"] is False
    [section] = body["code_sections"]
    assert (section["section"], section["as_of"]) == ("925.06.C", ruleset_as_of)
    assert body["resolved_by"]["order"] == 1


def test_no_zoning_board_cases_when_no_approval_goes_to_the_board(client: TestClient) -> None:
    # Administrator exceptions are decided by the Zoning Administrator, not the board.
    body = get(client, CONTEXTUAL, "option.with_relief")
    assert {r.split(" (")[0] for r in body["relief"]} == {"administrator_exception"}
    assert body["precedent"] is None


def test_evidence_follows_the_reports_building(client: TestClient) -> None:
    # Scored as a single-family home, the lot's option is by right: no approvals option.
    params = {"product_type": "single_family"}
    report = client.get(f"/api/parcels/{STEEP_SLOPE}", params=params).json()["analysis"]
    assert not any(o["label"] == "with_relief" for o in report["options"])
    url = f"/api/parcels/{STEEP_SLOPE}/evidence/option.with_relief"
    assert client.get(url, params=params).status_code == 404
    assert get(client, STEEP_SLOPE, "flag.steep_slope", **params)["severity"] == "high"


@pytest.mark.parametrize("evidence_id", ["flag.flood_zone", "option.by_right", "nope"])
def test_unknown_evidence_is_404(client: TestClient, evidence_id: str) -> None:
    url = f"/api/parcels/{STEEP_SLOPE}/evidence/{evidence_id}"
    assert client.get(url).status_code == 404


def test_only_the_cases_the_engine_judged_similar_are_listed(client: TestClient) -> None:
    source = client.app.state.source
    analysis = source.analysis(STEEP_SLOPE)
    analysis = analysis.model_copy(
        update={
            "options": [
                o.model_copy(update={"similar_cases": ["41 of 2025", "12 of 2026"]})
                if o.label == "with_relief"
                else o
                for o in analysis.options
            ]
        }
    )
    context = source.context(STEEP_SLOPE).model_copy(
        update={
            "zba_cases_nearby": [
                ZbaCase(
                    case_id="41 of 2025",
                    decision_date=None,
                    relief_types=["special_exception"],
                    district="R1D-M",
                    outcome="approved_with_conditions",
                    days_to_decision=122,
                    distance_ft=900,
                ),
                ZbaCase(
                    case_id="12 of 2026",
                    decision_date=None,
                    relief_types=["variance"],
                    district="R1D-M",
                    outcome="denied",
                    days_to_decision=None,
                    distance_ft=300,
                ),
                ZbaCase(
                    case_id="3 of 2019",
                    decision_date=None,
                    relief_types=["variance"],
                    district="R3-M",
                    outcome="approved",
                    days_to_decision=60,
                    distance_ft=100,
                ),
            ]
        }
    )
    body = build_evidence(
        "option.with_relief",
        STEEP_SLOPE,
        analysis,
        context,
        illustrative=False,
        mock_precedent=None,
    )
    assert body is not None and body.precedent is not None
    p = body.precedent
    assert (p.status, p.granted, p.total, p.median_months) == ("available", 1, 2, 4.0)
    assert [c.case_id for c in p.cases] == ["12 of 2026", "41 of 2025"]  # nearest first
    assert p.cases[1].outcome == "granted"
    assert p.rule
