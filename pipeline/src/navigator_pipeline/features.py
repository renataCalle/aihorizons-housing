"""Per-parcel facts (SiteContext-shaped) computed from the clean tables.

    uv run python -m navigator_pipeline.features            # City of Pittsburgh parcels
    uv run python -m navigator_pipeline.features --county   # every parcel in Allegheny County

Outputs in data/features/:
- parcel_facts.parquet     one row per parcel: shares, distances, frontage, flags
- parcel_zoning.parquet    long table: parcel_id, code, kind (district|overlay), share
- parcel_flood.parquet     long table: parcel_id, flood_zone, sfha, share
- parcel_env_nearby.parquet long table: parcel_id, site_type, site_id, name, distance_ft
                           (DEP sites within ENV_RADIUS_FT)

Only facts: shares of lot area (0-1), distances in feet, counts. No thresholds, severities,
or costs; those are judgments for the engine. A layer that does not cover a parcel's
municipality yields null (not zero); see COVERAGE.
"""

import argparse
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from navigator_pipeline.settings import DATA_DIR as DATA

CLEAN = DATA / "clean"
OUT = DATA / "features"

ENV_RADIUS_FT = 1_000  # radius for listing nearby DEP sites
FRONTAGE_RADIUS_FT = 60  # centerline within this distance of the lot counts as frontage
TRANSIT_TIERS = {"any": 1, "30min": 32, "15min": 64}  # weekday trips at the stop

# Layers that exist only for the City of Pittsburgh: outside the city their share is null.
CITY_ONLY = {
    "steep_slope",
    "landslide_prone",
    "undermined",
    "zoning",
    "historic_districts",
    "greenways",
    "height_overlay",
    "parking_reduction_overlay",
    "riverfront_overlay",
    "uptown_ipod",
    "combined_sewershed",
    "neighborhoods",
    "city_steps",
}
COVERAGE_NOTE = "layer covers the City of Pittsburgh only"


def read(name: str) -> gpd.GeoDataFrame | pd.DataFrame:
    path = CLEAN / f"{name}.parquet"
    try:
        return gpd.read_parquet(path)
    except ValueError:  # not a GeoParquet file
        return pd.read_parquet(path)


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:6.0f}s] {msg}", flush=True)


# ---------------------------------------------------------------- geometry kernels


TILE_FT = 2_000


def _tile(geom: shapely.Geometry) -> np.ndarray:
    """Cut a (dissolved) geometry into grid tiles so each parcel intersects small pieces.

    Tiles do not overlap, so summed intersection areas stay exact.
    """
    xmin, ymin, xmax, ymax = geom.bounds
    xs = np.arange(xmin, xmax + TILE_FT, TILE_FT)
    ys = np.arange(ymin, ymax + TILE_FT, TILE_FT)
    cells = shapely.box(*np.meshgrid(xs[:-1], ys[:-1]), *np.meshgrid(xs[1:], ys[1:])).ravel()
    cells = cells[shapely.intersects(cells, geom)]
    shapely.prepare(geom)
    parts = shapely.intersection(geom, cells)
    parts = shapely.get_parts(parts[~shapely.is_empty(parts)])
    return parts[np.isin(shapely.get_type_id(parts), [3, 6])]  # polygons only


def _pieces(layer: gpd.GeoDataFrame, by: str | None) -> gpd.GeoDataFrame:
    """Dissolve a layer (optionally per category) and tile it into non-overlapping pieces,
    so shares never double count overlapping source polygons."""
    if by is None:
        parts = _tile(shapely.union_all(layer.geometry.values))
        return gpd.GeoDataFrame({"geometry": parts}, crs=layer.crs)
    frames = []
    for value, sub in layer.groupby(by):
        parts = _tile(shapely.union_all(sub.geometry.values))
        frames.append(gpd.GeoDataFrame({by: value, "geometry": parts}, crs=layer.crs))
    return pd.concat(frames, ignore_index=True)


def area_shares(
    parcels: gpd.GeoDataFrame, layer: gpd.GeoDataFrame, by: str | None = None
) -> pd.DataFrame:
    """Share of each parcel's area covered by `layer` (per `by` category if given).

    Returns parcel_id[, by], share for every parcel/category pair with share > 0.
    """
    # Only the part of the layer near these parcels matters (big win for small subsets).
    near = layer.sindex.query(shapely.box(*parcels.total_bounds), predicate="intersects")
    layer = layer.iloc[near]
    if layer.empty:
        return pd.DataFrame(columns=["parcel_id", *([by] if by else []), "share"])
    pieces = _pieces(layer, by)
    p_idx, l_idx = pieces.sindex.query(parcels.geometry.values, predicate="intersects")
    if len(p_idx) == 0:
        return pd.DataFrame(columns=["parcel_id", *([by] if by else []), "share"])
    inter = shapely.intersection(parcels.geometry.values[p_idx], pieces.geometry.values[l_idx])
    df = pd.DataFrame(
        {
            "parcel_id": parcels["parcel_id"].values[p_idx],
            "area": shapely.area(inter),
            "lot": parcels["lot_area_sqft_gis"].values[p_idx],
        }
    )
    if by:
        df[by] = pieces[by].values[l_idx]
    keys = ["parcel_id", by] if by else ["parcel_id"]
    g = df.groupby(keys, as_index=False).agg(area=("area", "sum"), lot=("lot", "first"))
    g["share"] = (g["area"] / g["lot"]).clip(0, 1)
    return g.loc[g["share"] > 0, [*keys, "share"]]


def nearest_distance(
    parcels: gpd.GeoDataFrame, layer: gpd.GeoDataFrame, max_ft: float = 26_400
) -> np.ndarray:
    """Distance (ft) from each parcel polygon to the nearest feature; NaN beyond max_ft."""
    if layer.empty:
        return np.full(len(parcels), np.nan)
    p_idx, l_idx = layer.sindex.nearest(
        parcels.geometry.values, max_distance=max_ft, return_all=False
    )
    d = np.full(len(parcels), np.nan)
    d[p_idx] = shapely.distance(parcels.geometry.values[p_idx], layer.geometry.values[l_idx])
    return d


def within(parcels: gpd.GeoDataFrame, layer: gpd.GeoDataFrame, radius_ft: float) -> pd.DataFrame:
    """All (parcel, feature) pairs within radius, with distance."""
    p_idx, l_idx = layer.sindex.query(
        parcels.geometry.values, predicate="dwithin", distance=radius_ft
    )
    d = shapely.distance(parcels.geometry.values[p_idx], layer.geometry.values[l_idx])
    return pd.DataFrame(
        {"parcel_id": parcels["parcel_id"].values[p_idx], "_l": l_idx, "distance_ft": d}
    )


def containing_value(parcels: gpd.GeoDataFrame, layer: gpd.GeoDataFrame, column: str) -> pd.Series:
    """Value of `column` for the polygon containing each parcel's representative point."""
    pts = gpd.GeoDataFrame(
        {"parcel_id": parcels["parcel_id"].values},
        geometry=parcels.geometry.representative_point().values,
        crs=parcels.crs,
    )
    j = gpd.sjoin(pts, layer[[column, "geometry"]], predicate="within", how="left")
    return j.drop_duplicates("parcel_id").set_index("parcel_id")[column]


# ---------------------------------------------------------------- feature groups


def physical(parcels: gpd.GeoDataFrame, facts: pd.DataFrame) -> None:
    for name, col in [
        ("steep_slope", "steep_slope_share"),
        ("landslide_prone", "landslide_prone_share"),
        ("undermined", "undermined_share"),
        ("dep_digitized_mined_area", "deep_mined_share"),
        ("dep_aml", "aml_share"),
        ("parks", "park_share"),
        ("greenways", "greenway_share"),
        ("historic_districts", "historic_district_share"),
        ("combined_sewershed", "combined_sewershed_share"),
    ]:
        layer = read(name)
        s = area_shares(parcels, layer).set_index("parcel_id")["share"]
        facts[col] = facts.index.map(s).fillna(0.0)
        if name in CITY_ONLY:
            facts.loc[~facts["in_pittsburgh"], col] = np.nan
    obs = read("landslides_observed")
    facts["observed_landslides_within_500ft"] = (
        within(parcels, obs, 500).groupby("parcel_id").size().reindex(facts.index).fillna(0)
    )


def flood(parcels: gpd.GeoDataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    fz = read("fema_flood_zones")
    fz["zone"] = np.where(
        fz["floodway"], "FLOODWAY", np.where(fz["shaded_x_500yr"], "X500", fz["flood_zone"])
    )
    long = area_shares(parcels, fz[fz["zone"] != "X"], by="zone")
    wide = long.pivot_table(index="parcel_id", columns="zone", values="share", aggfunc="sum")
    sfha = wide.reindex(columns=["A", "AE", "FLOODWAY"]).sum(axis=1)
    facts["flood_sfha_share"] = facts.index.map(sfha).fillna(0.0)
    facts["flood_floodway_share"] = facts.index.map(
        wide["FLOODWAY"] if "FLOODWAY" in wide else pd.Series(dtype=float)
    ).fillna(0.0)
    facts["flood_500yr_share"] = facts.index.map(
        wide["X500"] if "X500" in wide else pd.Series(dtype=float)
    ).fillna(0.0)
    return long.rename(columns={"zone": "flood_zone"})


def zoning(parcels: gpd.GeoDataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    """Base district shares plus overlay shares, in one long table (the contract's shape)."""
    city = parcels[parcels["in_pittsburgh"]]
    z = read("zoning")
    district = area_shares(city, z, by="district").rename(columns={"district": "code"})
    district["kind"] = "district"
    overlays = []
    for name, label in [
        ("historic_districts", "HISTORIC"),
        ("height_overlay", "HEIGHT"),
        ("parking_reduction_overlay", "PARKING_REDUCTION"),
        ("riverfront_overlay", "RIVERFRONT"),
        ("uptown_ipod", "UPTOWN_IPOD"),
        ("greenways", "GREENWAY"),
    ]:
        s = area_shares(city, read(name))
        s["code"], s["kind"] = label, "overlay"
        overlays.append(s)
    long = pd.concat([district, *overlays], ignore_index=True)
    top = (
        district.sort_values("share", ascending=False)
        .drop_duplicates("parcel_id")
        .set_index("parcel_id")
    )
    facts["zoning_primary"] = facts.index.map(top["code"])
    facts["zoning_primary_share"] = facts.index.map(top["share"])
    facts["zoning_district_count"] = facts.index.map(district.groupby("parcel_id").size()).fillna(0)
    facts.loc[~facts["in_pittsburgh"], "zoning_district_count"] = np.nan
    return long[["parcel_id", "code", "kind", "share"]]


def environmental(parcels: gpd.GeoDataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in ("dep_land_recycling", "dep_storage_tanks"):
        layer = read(name).reset_index(drop=True)
        for site_type, sub in layer.groupby("site_type"):
            sub = sub.reset_index(drop=True)
            facts[f"dist_{site_type}_ft"] = nearest_distance(parcels, sub)
            w = within(parcels, sub, ENV_RADIUS_FT)
            w["site_type"] = site_type
            w["site_id"] = sub["site_id"].astype(str).values[w["_l"]]
            w["name"] = sub["name"].values[w["_l"]]
            rows.append(w.drop(columns="_l"))
    aml = read("dep_aml").reset_index(drop=True)
    facts["dist_aml_ft"] = nearest_distance(parcels, aml)
    return pd.concat(rows, ignore_index=True)


def infrastructure(parcels: gpd.GeoDataFrame, facts: pd.DataFrame) -> None:
    streets = read("street_centerlines")
    steps = pd.concat(
        [
            streets[streets["frontage_class"] == "steps"][["geometry"]],
            read("city_steps")[["geometry"]],
        ],
        ignore_index=True,
    )
    for cls, layer in [
        ("street", streets[streets["frontage_class"] == "street"]),
        ("alley", streets[streets["frontage_class"] == "alley"]),
        ("walkway", streets[streets["frontage_class"] == "walkway"]),
        ("steps", gpd.GeoDataFrame(steps, crs=streets.crs)),
    ]:
        facts[f"dist_{cls}_centerline_ft"] = nearest_distance(
            parcels, layer.reset_index(drop=True), max_ft=2_000
        )
    # Frontage type per the contract: the best access within FRONTAGE_RADIUS_FT.
    near = {
        c: facts[f"dist_{c}_centerline_ft"] <= FRONTAGE_RADIUS_FT
        for c in ("street", "alley", "steps", "walkway")
    }
    facts["frontage_type"] = np.select(
        [near["street"], near["alley"], near["steps"] | near["walkway"]],
        ["street", "alley", "steps"],
        default="none",
    )
    water = read("water_providers").drop_duplicates("parcel_id").set_index("parcel_id")
    facts["water_provider"] = facts.index.map(water["water_provider"])


def access(parcels: gpd.GeoDataFrame, facts: pd.DataFrame) -> None:
    stops = read("transit_stops")
    for tier, min_trips in TRANSIT_TIERS.items():
        sub = stops[stops["trips_weekday"] >= min_trips].reset_index(drop=True)
        facts[f"dist_transit_{tier}_ft"] = nearest_distance(parcels, sub)


def context(parcels: gpd.GeoDataFrame, facts: pd.DataFrame) -> None:
    hoods = read("neighborhoods")
    facts["neighborhood"] = facts.index.map(containing_value(parcels, hoods, "neighborhood"))
    facts.loc[~facts["in_pittsburgh"], "neighborhood"] = None
    mva = read("market_value_analysis")
    facts["mva_market_type"] = facts.index.map(containing_value(parcels, mva, "mva_market_type"))
    for name, col in [
        ("hud_qct", "in_qct"),
        ("opportunity_zones", "in_opportunity_zone"),
        ("hud_dda", "in_dda"),
    ]:
        s = area_shares(parcels, read(name)).set_index("parcel_id")["share"]
        facts[col] = facts.index.map(s).fillna(0) > 0.5
    safmr = read("hud_safmr")
    for b in range(5):
        facts[f"safmr_{b}br"] = facts.index.map(containing_value(parcels, safmr, f"safmr_{b}br"))


def ownership(facts: pd.DataFrame) -> None:
    city = read("city_owned").drop_duplicates("parcel_id").set_index("parcel_id")
    facts["city_inventory_type"] = facts.index.map(city["inventory_type"])
    facts["city_inventory_status"] = facts.index.map(city["current_status"])
    facts.loc[facts["city_inventory_status"].notna(), "owner_type"] = "city"
    # Pending transfers: title may not have moved yet, so these stay flagged separately.
    facts["pending_transfer_to"] = facts["city_inventory_type"].map(
        {"PLB Transfer": "land_bank", "URA Transfer": "ura"}
    )
    liens = read("tax_liens").set_index("parcel_id")
    facts["tax_lien_count"] = facts.index.map(liens["lien_count"]).fillna(0)
    facts["tax_lien_total_usd"] = facts.index.map(liens["lien_total_usd"]).fillna(0)
    condemned = set(read("condemned")["parcel_id"].dropna())
    facts["condemned"] = facts.index.isin(condemned)
    permits = read("pli_permits")
    new = permits[permits["is_new_construction"]].groupby("parcel_id")["issue_date"].max()
    facts["last_new_construction_permit"] = facts.index.map(new)


# ---------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", action="store_true", help="all county parcels, not just city")
    ap.add_argument("--ids", nargs="+", help="only these parcel ids (written with a suffix)")
    ap.add_argument("--tag", default="ids", help="output suffix for --ids runs")
    args = ap.parse_args()
    t0 = time.time()
    parcels = read("parcels")
    suffix = ""
    if args.ids:
        parcels = parcels[parcels["parcel_id"].isin(args.ids)]
        suffix = f"_{args.tag}"
    elif not args.county:
        parcels = parcels[parcels["in_pittsburgh"]]
    parcels = parcels[parcels["lot_area_sqft_gis"] > 0].reset_index(drop=True)
    log(f"{len(parcels):,} parcels", t0)

    base = [
        "parcel_id",
        "block_lot",
        "address",
        "municode",
        "municipality",
        "zip",
        "in_pittsburgh",
        "has_assessment",
        "property_class",
        "current_use",
        "owner_class",
        "owner_type",
        "has_structure",
        "year_built",
        "lot_area_sqft_gis",
        "lot_area_sqft_assessor",
        "assessed_land",
        "assessed_total",
        "last_sale_date",
        "last_sale_price",
        "as_of_parcels",
        "as_of_assessments",
    ]
    facts = pd.DataFrame(parcels[base]).set_index("parcel_id")
    OUT.mkdir(parents=True, exist_ok=True)

    physical(parcels, facts)
    log("physical shares", t0)
    flood(parcels, facts).to_parquet(OUT / f"parcel_flood{suffix}.parquet", index=False)
    log("flood", t0)
    zoning(parcels, facts).to_parquet(OUT / f"parcel_zoning{suffix}.parquet", index=False)
    log("zoning", t0)
    environmental(parcels, facts).to_parquet(
        OUT / f"parcel_env_nearby{suffix}.parquet", index=False
    )
    log("environmental", t0)
    infrastructure(parcels, facts)
    log("infrastructure", t0)
    access(parcels, facts)
    log("access", t0)
    context(parcels, facts)
    log("context", t0)
    ownership(facts)
    log("ownership", t0)

    facts["coverage_note"] = np.where(facts["in_pittsburgh"], None, COVERAGE_NOTE)
    out = OUT / f"parcel_facts{suffix}.parquet"
    facts.reset_index().to_parquet(out, index=False)
    log(f"wrote {out} ({facts.shape[1]} columns)", t0)


if __name__ == "__main__":
    main()
