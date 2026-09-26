"""Clean raw downloads into analysis-ready tables in data/clean/.

    uv run python -m navigator_pipeline.build              # every layer whose raw data is present
    uv run python -m navigator_pipeline.build zoning sales  # specific layers

Conventions (from the spec):
- Geometry is PA State Plane South, US survey feet (EPSG:2272), so areas are square feet.
- Parcels are keyed by the 16-character county id (`parcel_id`); the dashed city block-lot
  is kept as `block_lot`.
- Every table is written as (Geo)Parquet. Personal data (owner mailing addresses) is dropped.
"""

import argparse
import json
import re
import zipfile
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from navigator_pipeline.settings import DATA_DIR as DATA

CRS = "EPSG:2272"

RAW = DATA / "raw"
CLEAN = DATA / "clean"
PITTSBURGH_MUNICODES = range(101, 133)  # assessment MUNICODE 101-132 = city wards 1-32


# ---------------------------------------------------------------- helpers


def raw_file(key: str, suffix: str | None = None) -> Path:
    files = sorted(p for p in (RAW / key).iterdir() if not p.name.startswith("_"))
    if suffix:
        files = [p for p in files if p.suffix == suffix]
    if not files:
        raise FileNotFoundError(f"no raw data for {key}; run navigator_pipeline.fetch {key}")
    return files[0]


def manifest(key: str) -> dict:
    return json.loads((RAW / key / "_manifest.json").read_text())


def read_geo(key: str) -> gpd.GeoDataFrame:
    path = raw_file(key)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            shp = next(n for n in z.namelist() if n.lower().endswith(".shp"))
        gdf = gpd.read_file(f"/vsizip/{path}/{shp}", engine="pyogrio")
    else:
        gdf = gpd.read_file(path, engine="pyogrio")
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    gdf = gdf.to_crs(CRS)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf["geometry"] = shapely.make_valid(gdf.geometry.values)
    return gdf


def keep(gdf: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    """Select and rename columns; geometry is always kept."""
    cols = {k: v for k, v in columns.items() if k in gdf.columns}
    out = gdf[list(cols) + (["geometry"] if "geometry" in gdf.columns else [])]
    return out.rename(columns=cols)


def polygons_only(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """make_valid can return collections; keep only the polygonal parts."""
    gdf = gdf.copy()
    gdf["geometry"] = [
        shapely.union_all([p for p in shapely.get_parts(g) if p.geom_type.endswith("Polygon")])
        if g.geom_type == "GeometryCollection"
        else g
        for g in gdf.geometry
    ]
    return gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"]) & ~gdf.geometry.is_empty]


_county: gpd.GeoSeries | None = None


def county() -> shapely.Geometry:
    global _county
    if _county is None:
        _county = gpd.read_parquet(CLEAN / "municipalities.parquet").union_all()
    return _county


def clip_county(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf[gdf.intersects(county())].copy()


def write(df: pd.DataFrame, name: str) -> Path:
    CLEAN.mkdir(parents=True, exist_ok=True)
    out = CLEAN / f"{name}.parquet"
    df = df.reset_index(drop=True)
    if isinstance(df, gpd.GeoDataFrame):
        df.to_parquet(out, index=False)
    else:
        df.to_parquet(out, index=False)
    return out


def _date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()


# ---------------------------------------------------------------- base geography


def build_municipalities() -> gpd.GeoDataFrame:
    g = polygons_only(read_geo("municipalities"))
    g = keep(
        g, {"NAME": "name", "TYPE": "type", "MUNICODE": "municode", "FIPS": "fips", "COG": "cog"}
    )
    g["is_pittsburgh"] = g["name"].str.upper().eq("PITTSBURGH")
    return g


def build_neighborhoods() -> gpd.GeoDataFrame:
    g = polygons_only(read_geo("neighborhoods"))
    return g.dissolve(by="hood", as_index=False)[["hood", "geometry"]].rename(
        columns={"hood": "neighborhood"}
    )


def owner_type(current_use: str | None, in_pittsburgh: bool) -> str:
    """Owner type per the contract, from the assessor's land use (OWNERDESC is the ownership
    form, not public/private). Refined later with the city-owned inventory."""
    use = current_use.upper() if isinstance(current_use, str) else ""
    if use == "MUNICIPAL URBAN RENEWAL":
        return "ura"
    if use == "MUNICIPAL GOVERNMENT" and in_pittsburgh:
        return "city"
    if any(
        k in use for k in ("GOVERNMENT", "METRO HOUSING", "PUBLIC PARK", "MUNICIPAL IMPROVEMENT")
    ):
        return "other_public"
    return "private"


def build_parcels() -> gpd.GeoDataFrame:
    """Parcel polygons joined to the latest assessment record for each parcel."""
    g = polygons_only(read_geo("parcels"))
    g = keep(g, {"PIN": "parcel_id", "MAPBLOCKLO": "block_lot", "MUNICODE": "municode_gis"})
    g["parcel_id"] = g["parcel_id"].str.strip()
    # Some PINs have several polygons (multipart parcels drawn as rows): merge them.
    g = g.dissolve(by="parcel_id", as_index=False, aggfunc="first")
    g["lot_area_sqft_gis"] = g.geometry.area

    a = pd.read_csv(raw_file("assessments"), dtype=str, low_memory=False)
    a = a.drop(columns=[c for c in a.columns if c.startswith("CHANGENOTICEADDRESS")])
    num = [
        "LOTAREA",
        "FAIRMARKETLAND",
        "FAIRMARKETBUILDING",
        "FAIRMARKETTOTAL",
        "COUNTYLAND",
        "COUNTYTOTAL",
        "SALEPRICE",
        "YEARBLT",
        "STORIES",
        "FINISHEDLIVINGAREA",
        "BEDROOMS",
        "PROPERTYHOUSENUM",
        "MUNICODE",
    ]
    for c in num:
        a[c] = pd.to_numeric(a[c], errors="coerce")
    a["address"] = (
        a["PROPERTYHOUSENUM"].fillna(0).astype(int).astype(str).replace("0", "")
        + " "
        + a["PROPERTYADDRESS"].fillna("").str.strip()
    ).str.strip()
    a = a.rename(
        columns={
            "PARID": "parcel_id",
            "MUNICODE": "municode",
            "MUNIDESC": "municipality",
            "PROPERTYZIP": "zip",
            "NEIGHCODE": "assessor_neighborhood_code",
            "CLASSDESC": "property_class",
            "USEDESC": "current_use",
            "USECODE": "use_code",
            "OWNERDESC": "owner_class",
            "LOTAREA": "lot_area_sqft_assessor",
            "FAIRMARKETLAND": "assessed_land",
            "FAIRMARKETBUILDING": "assessed_building",
            "FAIRMARKETTOTAL": "assessed_total",
            "SALEDATE": "last_sale_date",
            "SALEPRICE": "last_sale_price",
            "SALEDESC": "last_sale_type",
            "YEARBLT": "year_built",
            "STORIES": "stories",
            "FINISHEDLIVINGAREA": "living_area_sqft",
            "BEDROOMS": "bedrooms",
            "CONDITIONDESC": "condition",
            "TAXDESC": "tax_status",
        }
    )
    a["last_sale_date"] = _date(a["last_sale_date"])
    a["has_structure"] = (a["assessed_building"].fillna(0) > 0) | (
        a["living_area_sqft"].fillna(0) > 0
    )
    cols = [
        "parcel_id",
        "address",
        "municode",
        "municipality",
        "zip",
        "assessor_neighborhood_code",
        "property_class",
        "use_code",
        "current_use",
        "owner_class",
        "tax_status",
        "lot_area_sqft_assessor",
        "assessed_land",
        "assessed_building",
        "assessed_total",
        "has_structure",
        "year_built",
        "stories",
        "living_area_sqft",
        "bedrooms",
        "condition",
        "last_sale_date",
        "last_sale_price",
        "last_sale_type",
    ]
    a = a[cols].drop_duplicates("parcel_id")

    p = g.merge(a, on="parcel_id", how="left")
    p["municode"] = p["municode"].fillna(pd.to_numeric(p["municode_gis"], errors="coerce"))
    p["in_pittsburgh"] = p["municode"].isin(PITTSBURGH_MUNICODES)
    p["has_assessment"] = p["address"].notna()
    p["owner_type"] = [
        owner_type(u, c) for u, c in zip(p["current_use"], p["in_pittsburgh"], strict=True)
    ]
    p["as_of_parcels"] = manifest("parcels")["source_as_of"]
    p["as_of_assessments"] = manifest("assessments")["source_as_of"]
    return p.drop(columns=["municode_gis"])


# ---------------------------------------------------------------- overlays (shares of lot)


def _overlay(key: str, columns: dict[str, str], clip: bool = True) -> Callable:
    def build() -> gpd.GeoDataFrame:
        g = polygons_only(read_geo(key))
        if clip:
            g = clip_county(g)
        return keep(g, columns)

    build.__name__ = f"build_{key}"
    return build


def build_zoning() -> gpd.GeoDataFrame:
    g = polygons_only(read_geo("zoning"))
    g = keep(
        g,
        {
            "zon_new": "district",
            "full_zoning_type": "district_name",
            "legendtype": "legend_type",
            "municode": "code_url",
            "status": "status",
        },
    )
    g["district"] = g["district"].str.strip()
    return g


def build_fema_flood_zones() -> gpd.GeoDataFrame:
    g = clip_county(polygons_only(read_geo("fema_flood_zones")))
    g = keep(
        g,
        {
            "FLD_ZONE": "flood_zone",
            "ZONE_SUBTY": "zone_subtype",
            "SFHA_TF": "sfha",
            "STATIC_BFE": "static_bfe",
        },
    )
    g["sfha"] = g["sfha"].eq("T")  # Special Flood Hazard Area = 1% annual chance
    g["floodway"] = g["zone_subtype"].fillna("").str.contains("FLOODWAY")
    g["shaded_x_500yr"] = g["zone_subtype"].fillna("").str.contains("0.2 PCT")
    return g


def build_hud_safmr() -> gpd.GeoDataFrame:
    g = clip_county(polygons_only(read_geo("hud_safmr")))
    cols = {"ZCTA5": "zip", "Metro_Name": "metro"} | {
        f"SAFMR_{b}BR": f"safmr_{b}br" for b in range(5)
    }
    return keep(g, cols)


# ---------------------------------------------------------------- points


def build_dep_land_recycling() -> gpd.GeoDataFrame:
    g = clip_county(read_geo("dep_land_recycling"))
    g = g.rename(columns=str.lower)
    media = g.groupby("primary_facility_id")["sub_facility_type"].agg(
        lambda s: sorted(set(s.dropna()))
    )
    g = g.drop_duplicates("primary_facility_id").set_index("primary_facility_id")
    g["media"] = media
    g = g.reset_index()
    return keep(
        g,
        {
            "primary_facility_id": "site_id",
            "primary_facility_name": "name",
            "site_status": "site_status",
            "primary_facility_status": "status",
            "media": "media",
        },
    ).assign(site_type="land_recycling_act2")


def _tanks(key: str, status: str) -> gpd.GeoDataFrame:
    g = clip_county(read_geo(key))
    g = keep(
        g,
        {
            "FACILITY_ID": "site_id",
            "FACILITY_NAME": "name",
            "FACILITY_MUNICIPALITY": "municipality",
            "TANK_INFORMATION": "tanks",
        },
    )
    return g.drop_duplicates("site_id").assign(site_type=f"storage_tank_{status}")


def build_dep_storage_tanks() -> gpd.GeoDataFrame:
    return pd.concat(
        [
            _tanks("dep_storage_tanks_active", "active"),
            _tanks("dep_storage_tanks_inactive", "inactive"),
        ],
        ignore_index=True,
    )


def build_dep_aml() -> gpd.GeoDataFrame:
    """Abandoned mine land: inventory sites and problem-area polygons, as one layer."""
    sites = keep(
        clip_county(polygons_only(read_geo("dep_aml_sites"))),
        {"PF_ID": "site_id", "NAME": "name", "PF_TYPE": "feature_type", "PF_STATUS": "status"},
    ).assign(kind="aml_site")
    polys = keep(
        clip_county(polygons_only(read_geo("dep_aml_polygons"))),
        {
            "SF_ID": "site_id",
            "SF_NAME": "name",
            "SF_PROBLEM_CODE_DESCRIPTION": "feature_type",
            "SF_STATUS": "status",
            "SF_PRIORITY": "priority",
        },
    ).assign(kind="aml_problem_area")
    out = pd.concat([sites, polys], ignore_index=True)
    out["site_id"] = out["site_id"].astype(str)
    return out


def build_landslides_observed() -> gpd.GeoDataFrame:
    g = clip_county(read_geo("landslides_observed"))
    g = keep(
        g,
        {
            "ev_id": "event_id",
            "ev_date": "event_date",
            "ls_cat": "category",
            "ls_trig": "trigger",
            "ls_size": "size",
            "loc_accu": "location_accuracy",
            "src_name": "source",
        },
    )
    g["event_date"] = _date(g["event_date"])
    return g


def build_transit_stop_frequency() -> gpd.GeoDataFrame:
    """One row per stop with total weekday trips across routes (for frequent transit)."""
    g = clip_county(read_geo("transit_stops"))
    g["trips_wd"] = pd.to_numeric(g["trips_wd"], errors="coerce").fillna(0)
    agg = g.groupby("stop_id").agg(
        stop_name=("stop_name", "first"),
        mode=("mode", lambda s: ",".join(sorted(set(s.dropna())))),
        routes=("route_code", lambda s: sorted(set(s.dropna().astype(str)))),
        trips_weekday=("trips_wd", "sum"),
        geometry=("geometry", "first"),
    )
    return gpd.GeoDataFrame(agg.reset_index(), geometry="geometry", crs=CRS)


# ---------------------------------------------------------------- streets and frontage

# Census feature class codes in the county centerlines -> contract frontage types.
FRONTAGE_CLASS = {
    "A1": "street",
    "A2": "street",
    "A3": "street",
    "A4": "street",
    "A71": "walkway",
    "A72": "steps",
    "A73": "alley",
    "A74": "private_drive",
    "A6": "ramp",
}


def _frontage_class(fcc: str) -> str:
    fcc = str(fcc or "")
    for prefix in ("A71", "A72", "A73", "A74", "A6", "A1", "A2", "A3", "A4"):
        if fcc.startswith(prefix):
            return FRONTAGE_CLASS[prefix]
    return "other"


def build_street_centerlines() -> gpd.GeoDataFrame:
    g = read_geo("street_centerlines")
    g = keep(
        g,
        {
            "FULL_NAME": "name",
            "FCC": "fcc",
            "LMUNI": "municipality_left",
            "RMUNI": "municipality_right",
            "ONEWAY": "oneway",
        },
    )
    g["frontage_class"] = g["fcc"].map(_frontage_class)
    return g


def build_city_steps() -> gpd.GeoDataFrame:
    g = read_geo("city_steps")
    name = next((c for c in ("name", "Name", "NAME") if c in g.columns), None)
    g = g.rename(columns={name: "name"}) if name else g.assign(name=None)
    return g[["name", "geometry"]].assign(frontage_class="steps")


# ---------------------------------------------------------------- other polygons


def build_combined_sewershed() -> gpd.GeoDataFrame:
    g = polygons_only(read_geo("combined_sewershed"))
    return keep(
        g,
        {
            "CSO_SHED": "sewershed",
            "MOD_BASIN": "basin",
            "CITYOFPGH": "city_of_pittsburgh",
            "PRIORITYSS": "priority_sewershed",
        },
    )


def build_market_value_analysis() -> gpd.GeoDataFrame:
    g = polygons_only(read_geo("market_value_analysis"))
    return keep(
        g,
        {
            "geoid": "block_group",
            "MVA21": "mva_market_type",
            "MSP1719": "median_sale_price_2017_19",
            "VSP1719": "sale_price_variance_2017_19",
            "PHHOO": "pct_owner_occupied",
            "PROSubHH": "pct_subsidized_rental",
            "PViolAddre": "pct_code_violations",
            "pforc1719": "pct_foreclosure_2017_19",
            "PVacLot": "pct_vacant_lots",
        },
    )


def build_hud_dda() -> gpd.GeoDataFrame:
    g = clip_county(polygons_only(read_geo("hud_dda")))
    return keep(g, {"ZCTA5": "zip", "DDA_NAME": "dda_name", "DDA_TYPE": "dda_type"})


def build_dep_digitized_mined_area() -> gpd.GeoDataFrame:
    g = clip_county(polygons_only(read_geo("dep_digitized_mined_area")))
    return keep(
        g,
        {
            "COAL_SEAM": "coal_seam",
            "OPERATION": "operation",
            "LASTMINED": "last_mined",
            "SOURCE": "source",
        },
    )


# ---------------------------------------------------------------- tabular


def _csv(key: str, **kw) -> pd.DataFrame:
    return pd.read_csv(raw_file(key, ".csv"), low_memory=False, **kw)


def build_address_points() -> gpd.GeoDataFrame:
    g = read_geo("address_points")
    g = keep(
        g,
        {
            "ADDRESS_ID": "address_id",
            "FULL_ADDRE": "address",
            "PARCELID": "parcel_id",
            "MUNICIPALI": "municipality",
            "ZIP_CODE": "zip",
            "ADDRESS_TY": "address_type",
            "STATUS": "status",
        },
    )
    return g


VALID_SALE_CODES = {"0", "16", "DT"}  # valid; building not yet assessed (new build); date lag


def build_sales() -> pd.DataFrame:
    d = _csv("sales", dtype={"PARID": str, "SALECODE": str, "MUNICODE": str})
    d = d.rename(
        columns={
            "PARID": "parcel_id",
            "SALEDATE": "sale_date",
            "RECORDDATE": "record_date",
            "PRICE": "price",
            "SALECODE": "sale_code",
            "SALEDESC": "sale_type",
            "INSTRTYPDESC": "instrument",
            "MUNICODE": "municode",
            "MUNIDESC": "municipality",
            "PROPERTYZIP": "zip",
            "FULL_ADDRESS": "address",
        }
    )
    d["sale_date"] = _date(d["sale_date"])
    d["record_date"] = _date(d["record_date"])
    d["price"] = pd.to_numeric(d["price"], errors="coerce")
    d["arms_length"] = d["sale_code"].str.strip().isin(VALID_SALE_CODES) & (d["price"] > 1000)
    d["multi_parcel"] = d["sale_code"].str.strip().eq("H")
    d["municode"] = pd.to_numeric(d["municode"], errors="coerce")
    d["in_pittsburgh"] = d["municode"].isin(PITTSBURGH_MUNICODES)
    return d[
        [
            "parcel_id",
            "sale_date",
            "record_date",
            "price",
            "sale_code",
            "sale_type",
            "instrument",
            "arms_length",
            "multi_parcel",
            "municode",
            "municipality",
            "zip",
            "in_pittsburgh",
            "address",
        ]
    ]


def build_pli_permits() -> pd.DataFrame:
    d = _csv("pli_permits", dtype={"parcel_num": str})
    d = d.drop(columns=[c for c in ("owner_name", "contractor_name", "_id") if c in d.columns])
    d = d.rename(columns={"parcel_num": "parcel_id"})
    d["issue_date"] = _date(d["issue_date"])
    d["total_project_value"] = pd.to_numeric(d["total_project_value"], errors="coerce")
    wt = d["work_type"].fillna("").str.upper()
    desc = d["work_description"].fillna("").str.upper()
    d["is_new_construction"] = wt.str.contains("NEW CONSTRUCTION|^NEW$", regex=True)
    d["is_demolition"] = wt.str.contains("DEMOLITION") | d["permit_type"].eq("Demolition Permit")
    d["is_residential"] = d["commercial_or_residential"].fillna("").str.contains(
        "Resid", case=False
    ) | desc.str.contains("DWELLING|RESIDEN|TOWNHO|APARTMENT|DUPLEX")
    return d


def build_condemned() -> pd.DataFrame:
    d = _csv("condemned", dtype={"parcel_id": str})
    d = d.drop(columns=[c for c in ("owner", "_id") if c in d.columns])
    d["create_date"] = _date(d["create_date"])
    return d


def build_city_owned() -> pd.DataFrame:
    d = _csv("city_owned", dtype={"pin": str})
    d = d.rename(
        columns={"pin": "parcel_id", "parc_sq_ft": "lot_area_sqft", "class": "property_class"}
    )
    for c in ("acquisition_date", "last_updated"):
        d[c] = _date(d[c])
    return d.drop(columns=["_id"], errors="ignore")


def build_tax_liens() -> pd.DataFrame:
    d = _csv("tax_liens", dtype={"pin": str})
    return d.rename(
        columns={"pin": "parcel_id", "number": "lien_count", "total_amount": "lien_total_usd"}
    ).drop(columns=["_id"])


def build_water_providers() -> pd.DataFrame:
    d = _csv("water_providers_by_parcel", dtype=str)
    return d.rename(columns={"PIN": "parcel_id", "PROVIDER": "water_provider"})


def build_hud_fmr_metro() -> pd.DataFrame:
    g = read_geo("hud_fmr_metro")
    d = pd.DataFrame(g.drop(columns="geometry"))
    d = d[d["FMR_AREANAME"].str.contains("Pittsburgh", na=False)]
    return d.rename(
        columns={"FMR_AREANAME": "fmr_area", "FMR_CODE": "fmr_code"}
        | {f"FMR_{b}BDR": f"fmr_{b}br" for b in range(5)}
    )[["fmr_code", "fmr_area"] + [f"fmr_{b}br" for b in range(5)]]


_CODE_SECTION = r"(9\d{2}\.\d{2}(?:\.[A-Z0-9]+)*)"


def build_council_zoning_matters() -> pd.DataFrame:
    """Council zoning legislation, classified, with filing-to-decision durations."""
    m = json.loads(raw_file("council_zoning_matters").read_text())
    rows = []
    for x in m:
        title = x.get("MatterTitle") or ""
        t = title.lower()
        if "conditional use" in t and "application" in t:
            category = "conditional_use"
        elif "zoning map" in t:
            category = "zoning_map_amendment"
        elif "planned unit" in t or "specially planned" in t:
            category = "planned_development"
        elif "zoning" in t or "title nine" in t:
            category = "code_text_amendment"
        else:
            category = "other"
        hist = sorted(x["histories"], key=lambda h: h.get("MatterHistoryActionDate") or "")
        actions = [h.get("MatterHistoryActionName") for h in hist]
        hearing = next(
            (
                h["MatterHistoryActionDate"]
                for h in hist
                if (h.get("MatterHistoryActionName") or "").startswith("Public Hearing Held")
            ),
            None,
        )
        rows.append(
            {
                "matter_id": x["MatterId"],
                "file": x.get("MatterFile"),
                "type": x.get("MatterTypeName"),
                "category": category,
                "status": x.get("MatterStatusName"),
                "title": title,
                "intro_date": x.get("MatterIntroDate"),
                "hearing_date": hearing,
                "passed_date": x.get("MatterPassedDate"),
                "enactment_number": x.get("MatterEnactmentNumber"),
                "code_sections": sorted(set(re.findall(_CODE_SECTION, title))),
                "actions": actions,
            }
        )
    d = pd.DataFrame(rows)
    for c in ("intro_date", "hearing_date", "passed_date"):
        d[c] = _date(d[c])
    d["approved"] = d["status"].isin(["Passed Finally", "Approved"])
    d["denied_or_died"] = d["status"].str.contains(
        "Defeated|Died|Withdrawn|Veto", case=False, na=False
    )
    d["days_to_decision"] = (d["passed_date"] - d["intro_date"]).dt.days
    return d


# ---------------------------------------------------------------- registry

BUILDERS: dict[str, Callable[[], pd.DataFrame]] = {
    # order matters: municipalities first (county boundary for clipping)
    "municipalities": build_municipalities,
    "neighborhoods": build_neighborhoods,
    "parcels": build_parcels,
    "address_points": build_address_points,
    # zoning and overlays
    "zoning": build_zoning,
    "historic_districts": _overlay(
        "historic_districts", {"historic_name": "name", "type": "type"}, clip=False
    ),
    "historic_sites": _overlay(
        "historic_sites",
        {"name": "name", "address": "address", "lotblock": "block_lot"},
        clip=False,
    ),
    "greenways": _overlay("greenways", {"name": "name"}, clip=False),
    "parks": _overlay("parks", {"updatepknm": "name", "final_cat": "category"}, clip=False),
    "height_overlay": _overlay(
        "height_overlay",
        {"hlimit": "height_limit", "Min_Base_Height": "min_base_height"},
        clip=False,
    ),
    "parking_reduction_overlay": _overlay(
        "parking_reduction_overlay", {"name": "name", "reduction": "reduction"}, clip=False
    ),
    "riverfront_overlay": _overlay(
        "riverfront_overlay", {"zone": "zone", "type": "type"}, clip=False
    ),
    "uptown_ipod": _overlay("uptown_ipod", {"uptown_ipod": "name"}, clip=False),
    # physical
    "steep_slope": _overlay("steep_slope", {"slope25": "slope25"}, clip=False),
    "landslide_prone": _overlay("landslide_prone", {"code": "code"}, clip=False),
    "undermined": _overlay("undermined", {"undermined": "undermined"}, clip=False),
    "landslides_observed": build_landslides_observed,
    "fema_flood_zones": build_fema_flood_zones,
    # environmental
    "dep_aml": build_dep_aml,
    "dep_digitized_mined_area": build_dep_digitized_mined_area,
    "dep_land_recycling": build_dep_land_recycling,
    "dep_storage_tanks": build_dep_storage_tanks,
    # infrastructure and access
    "combined_sewershed": build_combined_sewershed,
    "water_providers": build_water_providers,
    "street_centerlines": build_street_centerlines,
    "city_steps": build_city_steps,
    "transit_stops": build_transit_stop_frequency,
    # market
    "sales": build_sales,
    "hud_safmr": build_hud_safmr,
    "hud_fmr_metro": build_hud_fmr_metro,
    "market_value_analysis": build_market_value_analysis,
    # entitlement and timelines
    "council_zoning_matters": build_council_zoning_matters,
    "pli_permits": build_pli_permits,
    "condemned": build_condemned,
    # planner and financing
    "city_owned": build_city_owned,
    "tax_liens": build_tax_liens,
    "hud_qct": _overlay("hud_qct", {"GEOID": "tract_geoid"}),
    "hud_dda": build_hud_dda,
    "opportunity_zones": _overlay("opportunity_zones", {"GEOID10": "tract_geoid"}),
}

# Raw sources each clean table depends on (when not the same name).
DEPENDS = {
    "dep_aml": ["dep_aml_sites", "dep_aml_polygons"],
    "dep_storage_tanks": ["dep_storage_tanks_active", "dep_storage_tanks_inactive"],
    "parcels": ["parcels", "assessments"],
    "water_providers": ["water_providers_by_parcel"],
}


def available(name: str) -> bool:
    return all((RAW / k / "_manifest.json").exists() for k in DEPENDS.get(name, [name]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()
    for name, fn in BUILDERS.items():
        if args.names and name not in args.names:
            continue
        if not available(name):
            print(f"skip {name} (raw data missing)")
            continue
        df = fn()
        out = write(df, name)
        print(f"ok   {name}: {len(df):,} rows -> {out.relative_to(DATA.parent)}", flush=True)


if __name__ == "__main__":
    main()
