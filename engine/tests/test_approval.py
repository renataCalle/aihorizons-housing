"""The Zoning Board approval model: shared features, predictions, and the fallback."""

import json
from pathlib import Path

import numpy as np
import pytest

from navigator_engine import approval, entitlement

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden" / "site_context"


def test_features_describe_the_hearing() -> None:
    x = approval.features(
        [
            {"type": "variance", "section": "903.03.C.2", "rule": "lot_size"},
            {"type": "special_exception", "section": "911.02", "rule": "use"},
            {"type": "administrator_exception", "section": "925.01.C.2"},  # not at the hearing
        ],
        {"district": "R2-L", "mva": "C", "lot_sqft": 3_000, "vacant": True},
    )
    assert x["intercept"] == 1 and x["special_exception_only"] == 0
    assert x["rule_lot_size"] == 1 and x["rule_use"] == 1 and x["rule_setback"] == 0
    assert x["extra_approvals"] == 1  # two hearing items
    assert x["residential_district"] == 1 and x["strong_market"] == 1
    assert x["log_lot_area"] == pytest.approx(0.0)
    assert x["vacant_lot"] == 1 and x["steep_slope"] == 0 and x["flood_zone"] == 0
    only_se = approval.features(
        [{"type": "special_exception", "section": "911.02"}], {"district": "H"}
    )
    assert only_se["special_exception_only"] == 1 and only_se["strong_market"] == 0


def test_parcel_inputs_come_from_the_site_context() -> None:
    ctx = json.loads((GOLDEN / "steep_slope.json").read_text())
    site = approval.site_features(ctx)
    assert site["district"] == "R1D-M"
    assert site["mva"] == ctx["area"]["mva_market_type"]
    assert site["lot_sqft"] == pytest.approx(ctx["parcels"][0]["lot_area_sqft"])
    assert site["vacant"] is True
    x = approval.features([{"type": "variance", "rule": "setback"}], site)
    assert x["steep_slope"] == 1 and x["residential_district"] == 1


def test_past_cases_and_engine_checks_map_to_the_same_rules() -> None:
    assert approval.rule_of("903.03.C.2", "1,800 sf minimum lot size per unit") == "lot_size"
    assert approval.rule_of("903.03.D", "15' exterior side setback required") == "setback"
    assert approval.rule_of("911.02", "") == "use"
    assert approval.rule_of("914.02.A", "two parking stalls") == "parking"
    assert approval.rule_of("912.04.K", "fence height") == "other"  # a fence, not a building
    assert approval.CHECK_RULES["min_lot_size"] == "lot_size"
    assert approval.is_housing("Conversion of a single-family house into a duplex")
    assert not approval.is_housing("Projecting sign") and not approval.is_housing(None)


@pytest.mark.skipif(not approval.available(), reason="no fitted model in config/models/")
def test_model_predictions_are_probabilities_with_spread() -> None:
    x = approval.features(
        [{"type": "variance", "rule": "setback"}],
        {"district": "R1D-M", "mva": "D", "lot_sqft": 3_000},
    )
    p = approval.sample(x, 2_000, np.random.default_rng(0))
    assert p.shape == (2_000,) and np.all((p > 0) & (p < 1))
    assert np.percentile(p, 90) > np.percentile(p, 10)


@pytest.mark.skipif(not approval.available(), reason="no fitted model in config/models/")
def test_entitlement_uses_the_model_for_hearings_only() -> None:
    relief = [
        {"type": "variance", "section": "903.03", "check": "fits_envelope"},
        {"type": "subdivision", "section": "911.02"},
    ]
    out = entitlement.sample(relief, 500, np.random.default_rng(1), {"district": "R2-L"})
    assert any(s.startswith("Zoning Board hearing: model of") for s in out["sources"])
    assert "subdivision: PLACEHOLDER prior" in out["sources"]
    assert not any(s.startswith("variance:") for s in out["sources"])


def test_without_a_model_the_placeholders_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(approval, "MODEL", None)
    out = entitlement.sample(
        [{"type": "variance", "section": "903.03"}], 500, np.random.default_rng(1)
    )
    assert out["sources"] == ["variance: PLACEHOLDER prior (ZBA)"]
