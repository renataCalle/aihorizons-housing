"""Pick the eight golden parcels (spec: Validation > Golden parcels) from sandbox facts.

    uv run python -m sandbox.golden            # print candidates and the pick per case
    uv run python -m sandbox.golden --export   # also write fixtures/golden/site_context/*.json

Each case isolates the condition it tests: the named flag is on and the others are off, so a
golden parcel exercises one engine path. Among matches, vacant land in stronger markets
(URA MVA types A-E) is preferred, since a pro forma needs local comparable sales; ties are
broken by a seeded shuffle so the pick is reproducible.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from sandbox import site_context
from sandbox.engine_v0.analyze import analyze

ROOT = Path(__file__).resolve().parents[1]
FEAT = Path(__file__).parent / "data" / "features"
CLEAN = Path(__file__).parent / "data" / "clean"
FIXTURES = ROOT / "fixtures" / "golden" / "site_context"
ANALYSES = ROOT / "fixtures" / "golden" / "site_analysis"
SUBURB = "WILKINSBURG"  # adjacent borough with infill demand; zoning not covered in v1

RES = r"^(R1D|R1A|R2|R3|RM)-|^H$"
STRONG_MARKET = list("ABCDE")


def load() -> pd.DataFrame:
    f = pd.read_parquet(FEAT / "parcel_facts.parquet")
    f["residential_zone"] = f["zoning_primary"].fillna("").str.match(RES)
    f["infill_size"] = f["lot_area_sqft_gis"].between(2_400, 15_000)
    f["vacant_land"] = f["current_use"].eq("VACANT LAND") & f["has_structure"].eq(False)
    f["env_clear"] = (
        (f["dist_land_recycling_act2_ft"].fillna(np.inf) > 1_000)
        & (f["dist_storage_tank_active_ft"].fillna(np.inf) > 500)
        & (f["dist_storage_tank_inactive_ft"].fillna(np.inf) > 500)
    )
    f["physical_clear"] = (
        f["steep_slope_share"].eq(0)
        & f["landslide_prone_share"].eq(0)
        & f["undermined_share"].eq(0)
        & f["deep_mined_share"].eq(0)
        & f["aml_share"].eq(0)
        & f["flood_sfha_share"].eq(0)
    )
    f["title_clear"] = ~f["condemned"] & f["tax_lien_count"].eq(0)
    f["simple_zoning"] = f["zoning_district_count"].eq(1) & f["historic_district_share"].eq(0)
    f["street"] = f["frontage_type"].eq("street")
    rules = pd.read_csv(Path(__file__).parent / "rules" / "residential_draft.csv")
    min_lot = rules[rules["standard"].eq("min_lot_size")].groupby("district")["value"].first()
    need = f["zoning_primary"].map(min_lot)
    f["meets_min_lot"] = need.isna() | (f["lot_area_sqft_gis"] >= need)
    return f


def cases(f: pd.DataFrame) -> dict[str, pd.Series]:
    lot_ok = f["meets_min_lot"]  # isolate cases from the undersized-lot variance
    base = f["residential_zone"] & f["infill_size"] & f["vacant_land"] & f["title_clear"]
    clean = f["physical_clear"] & f["env_clear"] & f["simple_zoning"] & f["street"]
    other_physical_clear = f["landslide_prone_share"].eq(0) & f["flood_sfha_share"].eq(0)
    rm = f["zoning_primary"].fillna("").str.startswith("RM-")
    r2l_undersized = f["zoning_primary"].eq("R2-L") & (f["lot_area_sqft_gis"] < 3_000)
    zshares = pd.read_parquet(FEAT / "parcel_zoning.parquet")
    districts = zshares[zshares["kind"] == "district"]
    balanced = districts[districts["share"] >= 0.3].groupby("parcel_id").size() >= 2
    split = f["parcel_id"].map(balanced).fillna(False).astype(bool)
    return {
        "clean_by_right": base & clean & rm & f["owner_type"].eq("private") & lot_ok,
        "steep_slope": base
        & lot_ok
        & (f["steep_slope_share"] >= 0.5)
        & f["undermined_share"].eq(0)
        & other_physical_clear
        & f["env_clear"]
        & f["simple_zoning"],
        "undermined": base
        & lot_ok
        & (f["undermined_share"] >= 0.9)
        & f["steep_slope_share"].eq(0)
        & other_physical_clear
        & f["env_clear"]
        & f["simple_zoning"]
        & (rm | f["zoning_primary"].fillna("").str.startswith("R3-")),
        "needs_variance": base & clean & r2l_undersized,
        "flood_zone": f["residential_zone"]
        & f["infill_size"]
        & lot_ok
        & (f["flood_sfha_share"] >= 0.5)
        & f["flood_floodway_share"].eq(0)
        & f["undermined_share"].eq(0)
        & f["steep_slope_share"].eq(0)
        & f["owner_type"].eq("private"),
        "split_zoned": f["infill_size"] & f["title_clear"] & split & f["physical_clear"],
        "public_vacant": base
        & lot_ok
        & f["owner_type"].eq("city")
        & f["city_inventory_status"].eq("Available for Sale")
        & clean,
    }


def rank(f: pd.DataFrame, mask: pd.Series, seed: int = 7) -> pd.DataFrame:
    c = f[mask].copy()
    c["_strong"] = c["mva_market_type"].isin(STRONG_MARKET)
    c["_r"] = np.random.default_rng(seed).random(len(c))
    return c.sort_values(["_strong", "_r"], ascending=[False, True])


def suburban_pick() -> str:
    p = pd.read_parquet(
        CLEAN / "parcels.parquet",
        columns=[
            "parcel_id",
            "municipality",
            "current_use",
            "has_structure",
            "lot_area_sqft_gis",
            "owner_type",
            "property_class",
        ],
    )
    c = p[
        p["municipality"].fillna("").str.upper().str.contains(SUBURB)
        & p["current_use"].eq("VACANT LAND")
        & p["has_structure"].eq(False)
        & p["lot_area_sqft_gis"].between(3_000, 10_000)
        & p["owner_type"].eq("private")
    ]
    c = c.assign(_r=np.random.default_rng(7).random(len(c))).sort_values("_r")
    return c["parcel_id"].iloc[0]


SHOW = [
    "parcel_id",
    "block_lot",
    "address",
    "zoning_primary",
    "lot_area_sqft_gis",
    "neighborhood",
    "mva_market_type",
    "steep_slope_share",
    "undermined_share",
    "flood_sfha_share",
    "zoning_district_count",
    "owner_type",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()
    f = load()
    picks: dict[str, str] = {}
    for name, mask in cases(f).items():
        r = rank(f, mask)
        print(f"\n== {name}: {len(r)} candidates")
        print(r[SHOW].head(3).round(2).to_string(index=False))
        if r.empty:
            sys.exit(f"no candidate for {name}; loosen its filter")
        picks[name] = r["parcel_id"].iloc[0]
    sub = suburban_pick()
    picks["outside_city"] = sub
    print(f"\n== outside_city: {sub} ({SUBURB.title()})")

    out = Path(__file__).parent / "golden_parcels.json"
    out.write_text(json.dumps(picks, indent=2) + "\n")
    print(f"\nwrote {out}")

    if args.export:
        # Suburban parcels are not in the city facts table: compute their facts first.
        subprocess.run(
            [sys.executable, "-m", "sandbox.features", "--ids", sub, "--tag", "golden"], check=True
        )
        FIXTURES.mkdir(parents=True, exist_ok=True)
        ANALYSES.mkdir(parents=True, exist_ok=True)
        for name, pid in picks.items():
            ctx = site_context.build([pid])
            path = FIXTURES / f"{name}.json"
            path.write_text(json.dumps(ctx, indent=2, default=str) + "\n")
            result = analyze(json.loads(path.read_text()))
            apath = ANALYSES / f"{name}.json"
            apath.write_text(json.dumps(result, indent=2, default=str) + "\n")
            print(f"wrote {path.relative_to(ROOT)} and {apath.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
