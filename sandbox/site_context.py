"""Assemble a SiteContext-shaped dict for one parcel or an assemblage, from sandbox data.

    uv run python -m sandbox.site_context 0001B00024000000
    uv run python -m sandbox.site_context 12-A-34 --out fixtures/golden/site_context/x.json

Mirrors the spec's SiteContext fields so the output can seed golden-parcel fixtures. It is a
research convenience, not the production feature builder (that lives in pipeline/).
"""

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from sandbox.features import COVERAGE_NOTE

DATA = Path(__file__).parent / "data"
CLEAN = DATA / "clean"
FEAT = DATA / "features"
RAW = DATA / "raw"

SCHEMA_VERSION = "0.1.0"
COMPS_RADIUS_FT = 2_640  # half a mile
COMPS_YEARS = 3

# SiteContext.provenance keys -> raw sources behind them
PROVENANCE = {
    "parcels": ["parcels", "assessments"],
    "zoning": [
        "zoning",
        "historic_districts",
        "height_overlay",
        "parking_reduction_overlay",
        "riverfront_overlay",
        "uptown_ipod",
        "greenways",
    ],
    "steep_slope": ["steep_slope"],
    "landslide_prone": ["landslide_prone"],
    "undermined": ["undermined", "dep_digitized_mined_area", "dep_aml_sites", "dep_aml_polygons"],
    "flood": ["fema_flood_zones"],
    "environmental": [
        "dep_land_recycling",
        "dep_storage_tanks_active",
        "dep_storage_tanks_inactive",
    ],
    "sewer": ["combined_sewershed"],
    "frontage": ["street_centerlines", "city_steps"],
    "transit": ["transit_stops"],
    "market_sales": ["sales"],
    "market_rents": ["hud_safmr", "hud_fmr_metro"],
    "zba_cases": [],
}


def _clean(v):
    """JSON-safe scalars: NaN -> None, numpy -> python, timestamps -> ISO date."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, np.generic):
        return _clean(v.item())
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return None if pd.isna(v) else v.date().isoformat() if hasattr(v, "date") else str(v)
    return v


def _source(keys: list[str]) -> dict:
    ms = [json.loads((RAW / k / "_manifest.json").read_text()) for k in keys]
    as_of = [m["source_as_of"] for m in ms if m.get("source_as_of")]
    return {
        "name": "; ".join(m.get("dataset_title") or m["key"] for m in ms),
        "url": ms[0]["url"] if len(ms) == 1 else None,
        "as_of": min(as_of)[:10] if as_of else None,  # oldest input governs
        "note": None,
    }


def resolve_ids(ids: list[str], parcels: pd.DataFrame) -> list[str]:
    """Accept county ids or dashed block-lots."""
    out = []
    for i in ids:
        i = i.strip().upper()
        if i in parcels.index:
            out.append(i)
            continue
        hit = parcels.index[parcels["block_lot"].str.upper() == i]
        if len(hit) == 0:
            raise KeyError(f"parcel {i!r} not found by county id or block-lot")
        out.append(hit[0])
    return out


def _load(stem: str) -> pd.DataFrame:
    """A feature table plus any --ids subsets (parcel_facts_<tag>.parquet), deduplicated."""
    frames = [pd.read_parquet(p) for p in sorted(FEAT.glob(f"{stem}*.parquet"))]
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates("parcel_id", keep="last") if stem == "parcel_facts" else df


def build(ids: list[str]) -> dict:
    facts = _load("parcel_facts").set_index("parcel_id")
    ids = resolve_ids(ids, facts)
    f = facts.loc[ids]
    geoms = gpd.read_parquet(CLEAN / "parcels.parquet", columns=["parcel_id", "geometry"])
    geoms = geoms[geoms["parcel_id"].isin(ids)].set_index("parcel_id").loc[ids]
    site = shapely.union_all(geoms.geometry.values)
    lot = f["lot_area_sqft_gis"].to_numpy()
    in_city = bool(f["in_pittsburgh"].all())

    def wshare(col: str):
        """Lot-area-weighted share across the assemblage; None if any parcel lacks it."""
        v = f[col].to_numpy(dtype=float)
        return None if np.isnan(v).any() else float((v * lot).sum() / lot.sum())

    parcels = [
        {
            "parcel_id": pid,
            "block_lot": row["block_lot"],
            "municipality": row["municipality"],
            "address": row["address"],
            "geometry": json.loads(gpd.GeoSeries([geoms.geometry[pid]]).to_json())["features"][0][
                "geometry"
            ],
            "lot_area_sqft": _clean(row["lot_area_sqft_gis"]),
            "frontage_ft": None,
            "current_use": row["current_use"],
            "has_structure": bool(row["has_structure"]),
            "assessed_land": _clean(row["assessed_land"]),
            "assessed_total": _clean(row["assessed_total"]),
            "owner_type": row["owner_type"],
        }
        for pid, row in f.iterrows()
    ]

    # zoning: lot-area-weighted shares over the assemblage
    z = _load("parcel_zoning").drop_duplicates()
    z = z[z["parcel_id"].isin(ids)].merge(
        f["lot_area_sqft_gis"].rename("lot"), left_on="parcel_id", right_index=True
    )
    z["a"] = z["share"] * z["lot"]
    zoning = [
        {"code": code, "kind": kind, "share": round(a / lot.sum(), 4)}
        for (code, kind), a in z.groupby(["code", "kind"])["a"].sum().items()
    ]

    fl = _load("parcel_flood").drop_duplicates()
    fl = fl[fl["parcel_id"].isin(ids)].merge(
        f["lot_area_sqft_gis"].rename("lot"), left_on="parcel_id", right_index=True
    )
    fl["a"] = fl["share"] * fl["lot"]
    flood_zones = [
        {"code": zc, "share": round(a / lot.sum(), 4)}
        for zc, a in fl.groupby("flood_zone")["a"].sum().items()
    ]

    env = _load("parcel_env_nearby").drop_duplicates()
    env = (
        env[env["parcel_id"].isin(ids)]
        .sort_values("distance_ft")
        .drop_duplicates(["site_type", "site_id"])
    )
    environmental = [
        {
            "site_type": r.site_type,
            "site_id": str(r.site_id),
            "name": r.name,
            "distance_ft": round(float(r.distance_ft), 1),
        }
        for r in env.itertuples()
    ]

    frontage_rank = {"street": 0, "alley": 1, "steps": 2, "none": 3}
    frontage = min(f["frontage_type"], key=lambda t: frontage_rank.get(t, 9))

    # market: arm's-length sales within radius over the last N years
    sales = pd.read_parquet(CLEAN / "sales.parquet")
    cutoff = pd.Timestamp.today() - pd.DateOffset(years=COMPS_YEARS)
    sales = sales[sales["arms_length"] & ~sales["multi_parcel"] & (sales["sale_date"] >= cutoff)]
    pts = gpd.read_parquet(
        CLEAN / "parcels.parquet",
        columns=[
            "parcel_id",
            "geometry",
            "lot_area_sqft_gis",
            "living_area_sqft",
            "property_class",
            "year_built",
        ],
    )
    near = pts[pts.geometry.dwithin(site, COMPS_RADIUS_FT)]
    near = near.assign(distance_ft=near.geometry.distance(site))
    comps = sales.merge(near.drop(columns="geometry"), on="parcel_id")
    comps = comps[~comps["parcel_id"].isin(ids)].sort_values("sale_date", ascending=False)
    sale_rows = [
        {
            "parcel_id": r.parcel_id,
            "sale_date": _clean(r.sale_date),
            "price": _clean(r.price),
            "lot_area_sqft": _clean(r.lot_area_sqft_gis),
            "building_sqft": _clean(r.living_area_sqft),
            "property_class": _clean(r.property_class),
            "year_built": _clean(r.year_built),
            "sale_code": _clean(r.sale_code),
            "distance_ft": round(float(r.distance_ft), 1),
        }
        for r in comps.head(200).itertuples()
    ]
    # Adjacent parcels (touching the site) and whether they carry a structure: contextual side
    # setbacks (925.06.C) are available only next to built lots.
    ptab = gpd.read_parquet(
        CLEAN / "parcels.parquet", columns=["parcel_id", "geometry", "has_structure", "address"]
    )
    touch = ptab[ptab.geometry.dwithin(site, 1.0) & ~ptab["parcel_id"].isin(ids)]
    adjacent = [
        {
            "parcel_id": r.parcel_id,
            "address": _clean(r.address),
            "has_structure": None if pd.isna(r.has_structure) else bool(r.has_structure),
            "shared_edge_ft": round(float(r.geometry.intersection(site.buffer(1.0)).length / 2), 1),
        }
        for r in touch.itertuples()
    ]
    first = f.iloc[0]
    rent_benchmarks = [
        {
            "source": "HUD SAFMR",
            "geography": str(first["zip"]),
            "bedrooms": b,
            "monthly_rent": _clean(first[f"safmr_{b}br"]),
            "as_of": _source(["hud_safmr"])["as_of"],
        }
        for b in range(5)
        if pd.notna(first[f"safmr_{b}br"])
    ]

    provenance = {
        k: _source(v)
        if v
        else {
            "name": "Zoning Board of Adjustment decisions",
            "url": None,
            "as_of": None,
            "note": "Not available: pittsburghpa.gov blocks this client (HTTP 403).",
        }
        for k, v in PROVENANCE.items()
    }
    if not in_city:
        for k in ("zoning", "steep_slope", "landslide_prone", "sewer"):
            provenance[k]["note"] = COVERAGE_NOTE

    zba_note = provenance["zba_cases"]
    return {
        "schema_version": SCHEMA_VERSION,
        "parcels": parcels,
        "zoning": zoning,
        "physical": {
            "steep_slope_share": wshare("steep_slope_share"),
            "landslide_prone_share": wshare("landslide_prone_share"),
            "undermined_share": wshare("undermined_share"),
            "deep_mined_share": wshare("deep_mined_share"),
            "aml_share": wshare("aml_share"),
            "flood_zones": flood_zones,
            "observed_landslides_within_500ft": int(f["observed_landslides_within_500ft"].sum()),
        },
        "environmental": environmental,
        "infrastructure": {
            "combined_sewershed": None
            if not in_city
            else bool((f["combined_sewershed_share"] > 0).any()),
            "frontage_type": frontage,
            "water_provider": _clean(first["water_provider"]),
        },
        "access": {"frequent_transit_distance_ft": _clean(f["dist_transit_15min_ft"].min())},
        "adjacent": adjacent,
        "title": {
            "tax_lien_total_usd": float(f["tax_lien_total_usd"].sum()),
            "condemned": bool(f["condemned"].any()),
            "city_inventory_status": _clean(first["city_inventory_status"]),
            "pending_transfer_to": _clean(first["pending_transfer_to"]),
        },
        "area": {
            "neighborhood": _clean(first["neighborhood"]),
            "mva_market_type": _clean(first["mva_market_type"]),
            "in_qct": bool(f["in_qct"].any()),
            "in_opportunity_zone": bool(f["in_opportunity_zone"].any()),
        },
        "market": {
            "sales": sale_rows,
            "rent_benchmarks": rent_benchmarks,
            "comps_radius_ft": COMPS_RADIUS_FT,
            "comps_years": COMPS_YEARS,
        },
        # None = not available (reason in provenance["zba_cases"]); [] = none nearby.
        "zba_cases_nearby": None if zba_note.get("note") else [],
        "provenance": provenance,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parcel_ids", nargs="+", help="county ids or dashed block-lots")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    ctx = build(args.parcel_ids)
    text = json.dumps(ctx, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
