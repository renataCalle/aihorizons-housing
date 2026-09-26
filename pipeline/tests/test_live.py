"""Live lookups, offline: the datastore API is stubbed."""

import pandas as pd
import pytest

from navigator_pipeline import live, site_context

PID = "0015L00194000000"
NEIGHBOR = "0015L00195000000"


def _ctx() -> dict:
    snap = {
        "name": "stored",
        "url": None,
        "as_of": "2026-09-01",
        "note": None,
        "retrieved": "snapshot",
        "retrieved_at": "2026-09-01T00:00:00+00:00",
    }
    return {
        "parcels": [
            {
                "parcel_id": PID,
                "current_use": "VACANT LAND",
                "has_structure": False,
                "assessed_land": 1000.0,
                "assessed_total": 1000.0,
                "owner_type": "private",
            }
        ],
        "title": {
            "tax_lien_total_usd": 0.0,
            "condemned": False,
            "city_inventory_status": None,
            "pending_transfer_to": None,
            "recent_permits": [],
        },
        "market": {"sales": [], "comps_radius_ft": 2640, "comps_years": 3},
        "provenance": {k: dict(snap) for k in site_context.LIVE_RECORDS},
    }


NEAR = pd.DataFrame(
    [
        {
            "parcel_id": NEIGHBOR,
            "lot_area_sqft_gis": 2500.0,
            "living_area_sqft": 1400.0,
            "property_class": "RESIDENTIAL",
            "year_built": 2019.0,
            "distance_ft": 120.0,
        }
    ]
)


def _stub(monkeypatch, fail: bool = False) -> None:
    today = pd.Timestamp.today().date().isoformat()
    canned = {
        "assessments": [
            {
                "USEDESC": "MUNICIPAL GOVERNMENT",
                "FAIRMARKETBUILDING": 0,
                "FINISHEDLIVINGAREA": 0,
                "FAIRMARKETLAND": "5000",
                "FAIRMARKETTOTAL": "5000",
                "MUNICODE": "118",
            }
        ],
        "tax_liens": [{"total_amount": "2533.25"}],
        "condemned": [{"parcel_id": PID}],
        "city_owned": [{"current_status": "Available for Sale", "inventory_type": "PLB Transfer"}],
        "pli_permits": [
            {"permit_id": "A", "issue_date": "2024-01-01"},
            {"permit_id": "B", "issue_date": "2026-05-01"},
        ],
        "sales": [
            {"PARID": NEIGHBOR, "SALEDATE": today, "PRICE": "250000", "SALECODE": "0"},
            {"PARID": NEIGHBOR, "SALEDATE": today, "PRICE": "1", "SALECODE": "3"},
        ],
    }
    rid_to_key = {live.BY_KEY[k].resource_id: k for k in canned}

    def fake(params: dict) -> list[dict]:
        if fail:
            raise ConnectionError("down")
        return canned[rid_to_key[params["resource_id"]]]

    live.clear_cache()
    monkeypatch.setattr(live, "_datastore", fake)


def test_live_records_overlay_the_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch)
    ctx = _ctx()
    site_context._apply_live(ctx, [PID], NEAR)
    p, t = ctx["parcels"][0], ctx["title"]
    assert p["assessed_land"] == 5000.0
    assert p["owner_type"] == "city"  # municipal government in the city, and in inventory
    assert t["tax_lien_total_usd"] == pytest.approx(2533.25)
    assert t["condemned"] is True
    assert t["pending_transfer_to"] == "land_bank"
    assert [x["permit_id"] for x in t["recent_permits"]] == ["B", "A"]  # newest first
    assert len(ctx["market"]["sales"]) == 1  # the nominal $1 transfer is not a comp
    assert all(v["retrieved"] == "live" for v in ctx["provenance"].values())


def test_failed_lookups_keep_the_stored_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, fail=True)
    ctx = _ctx()
    site_context._apply_live(ctx, [PID], NEAR)
    assert ctx["parcels"][0]["assessed_land"] == 1000.0
    assert ctx["title"]["condemned"] is False
    for v in ctx["provenance"].values():
        assert v["retrieved"] == "snapshot"
        assert v["note"].startswith("Live lookup failed")


def test_results_are_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    live.clear_cache()
    monkeypatch.setattr(live, "_datastore", lambda params: calls.append(1) or [])
    live.parcel_records("condemned", PID)
    live.parcel_records("condemned", PID)
    assert len(calls) == 1


def test_user_agent_is_exact() -> None:
    from navigator_pipeline.http import USER_AGENT, client

    assert USER_AGENT == "market-data-client/1.0"
    with client() as http:
        assert http.headers["User-Agent"] == "market-data-client/1.0"
