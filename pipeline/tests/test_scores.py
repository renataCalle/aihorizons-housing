"""The stored-results dataset (score_all -> scores), built from the golden contexts so it runs
without the data store."""

import json
from pathlib import Path

import pandas as pd
import pytest

from navigator_engine import analyze
from navigator_engine.rules_engine import TEMPLATES
from navigator_pipeline import score_all, scores

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden" / "site_context"


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> scores.Scores:
    out = tmp_path_factory.mktemp("scores")
    parts = out / "_parts"
    parts.mkdir()
    rows: dict[str, list] = {t: [] for t in score_all.TABLES}
    for p in sorted(GOLDEN.glob("*.json")):
        r = score_all.score_context(json.loads(p.read_text()))
        rows["parcels"].append(r["parcels"])
        rows["programs"].extend(r["programs"])
        rows["analyses"].append(r["analyses"])
        rows["contexts"].append(r["contexts"])
    facts = pd.Series({"block_lot": "9-Z-9", "lot_area_sqft_gis": 1000.0, "has_assessment": False})
    rows["parcels"].append(score_all.failed_row("0009Z00009000000", facts, "no record"))
    score_all.write_part(rows, parts, 0)
    score_all.merge(parts, out)
    return scores.load(out)


def test_lookup_returns_the_engine_output(store: scores.Scores) -> None:
    ctx = json.loads((GOLDEN / "clean_by_right.json").read_text())
    pid = ctx["parcels"][0]["parcel_id"]
    assert store.analysis(pid) == json.loads(json.dumps(analyze(ctx), default=str))
    assert store.context(pid)["parcels"][0]["parcel_id"] == pid


def test_lookup_by_block_lot(store: scores.Scores) -> None:
    s = store.summary("52-h-93")
    assert s["parcel_id"] == "0052H00093000000"
    assert s["status"] == "scored" and s["band"] and s["score"] is not None


def test_one_program_row_per_building_type(store: scores.Scores) -> None:
    rows = store.programs("0052H00093000000")
    assert sorted(r["product"] for r in rows) == sorted(TEMPLATES)
    assert sum(r["lead"] for r in rows) == 1


def test_unscorable_parcels_are_kept_with_the_reason(store: scores.Scores) -> None:
    s = store.summary("0009Z00009000000")
    assert s["status"] == "error" and s["error"] == "no record"
    assert store.analysis("0009Z00009000000") is None
    outside = store.summary("0176C00275000000")  # Wilkinsburg: zoning not covered
    assert outside["status"] == "not_scored"


def test_unknown_ids_and_sql(store: scores.Scores) -> None:
    assert store.summary("0000A00000000000") is None
    assert store.resolve("not-a-parcel") is None
    counts = store.sql("SELECT status, count(*) AS n FROM parcels GROUP BY 1")
    assert sum(r["n"] for r in counts) == len(list(GOLDEN.glob("*.json"))) + 1


def test_missing_dataset_says_how_to_build_it(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="score_all"):
        scores.load(tmp_path)


def test_a_parcel_without_comparable_sales_is_not_priced() -> None:
    ctx = json.loads((GOLDEN / "clean_by_right.json").read_text())
    ctx["market"]["sales"], ctx["market"]["rent_benchmarks"] = [], []
    with pytest.raises(score_all.NotPriced, match="comparable sales"):
        score_all.score_context(ctx)
