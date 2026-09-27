"""What the land price defaults to, and how it moves the score."""

import json
from pathlib import Path

import pytest

from navigator_engine import analyze

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden" / "site_context"
NAMES = sorted(p.stem for p in GOLDEN.glob("*.json"))


def _ctx(name: str) -> dict:
    return json.loads((GOLDEN / f"{name}.json").read_text())


def test_a_built_lot_is_bought_with_its_building() -> None:
    ctx = _ctx("split_zoned")  # a house on the lot
    p = ctx["parcels"][0]
    assert p["has_structure"]
    land = analyze(ctx)["metrics"]["land_basis"]
    assert land["value"] == p["assessed_total"]
    assert land["source"].startswith("county assessed total value")


def test_a_vacant_lot_uses_the_land_value() -> None:
    ctx = _ctx("clean_by_right")
    land = analyze(ctx)["metrics"]["land_basis"]
    assert land["value"] == ctx["parcels"][0]["assessed_land"]


@pytest.mark.parametrize("name", NAMES)
def test_a_pricier_lot_never_scores_higher(name: str) -> None:
    ctx = _ctx(name)
    scores = [analyze(ctx, {"land_price": x})["verdict"]["score"] for x in (0, 50_000, 300_000)]
    if scores[0] is None:
        return  # not scored (zoning not covered)
    assert scores == sorted(scores, reverse=True), scores
