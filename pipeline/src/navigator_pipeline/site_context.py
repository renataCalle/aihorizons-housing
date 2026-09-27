"""Assemble a SiteContext-shaped dict for one parcel or an assemblage, from the pipeline's data.

    uv run python -m navigator_pipeline.site_context 0001B00024000000
    uv run python -m navigator_pipeline.site_context 12-A-34 --out x.json

Mirrors the spec's SiteContext fields. Tables are loaded once per process and reloaded when
the refresh rewrites them, so building many contexts (navigator_pipeline.publish) is fast.
"""

import argparse
import json
import math
import threading
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from navigator_pipeline import live as live_lookups
from navigator_pipeline.build import VALID_SALE_CODES, owner_type
from navigator_pipeline.features import COVERAGE_NOTE
from navigator_pipeline.settings import DATA_DIR as DATA

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


def _manifest(key: str) -> dict:
    cache = _store.setdefault("manifests", {})
    if key not in cache:
        cache[key] = json.loads((RAW / key / "_manifest.json").read_text())
    return cache[key]


def _source(keys: list[str]) -> dict:
    ms = [_manifest(k) for k in keys]
    as_of = [m["source_as_of"] for m in ms if m.get("source_as_of")]
    fetched = [m.get("fetched_at") for m in ms if m.get("fetched_at")]
    return {
        "name": "; ".join(m.get("dataset_title") or m["key"] for m in ms),
        "url": ms[0]["url"] if len(ms) == 1 else None,
        "as_of": min(as_of)[:10] if as_of else None,  # oldest input governs
        "note": None,
        "retrieved": "snapshot",
        "retrieved_at": min(fetched) if fetched else None,
    }


# Records that can be looked up live per parcel -> the stored source behind them.
LIVE_RECORDS = {
    "assessment": "assessments",
    "tax_liens": "tax_liens",
    "condemned": "condemned",
    "city_inventory": "city_owned",
    "permits": "pli_permits",
    "recent_sales": "sales",
}
PENDING = {"PLB Transfer": "land_bank", "URA Transfer": "ura"}


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


_store: dict = {}
_store_lock = threading.Lock()
PARCEL_COLUMNS = [
    "parcel_id",
    "geometry",
    "lot_area_sqft_gis",
    "living_area_sqft",
    "property_class",
    "year_built",
    "has_structure",
    "address",
]


def _signature() -> tuple:
    return tuple(
        (p.name, p.stat().st_mtime_ns) for d in (CLEAN, FEAT) for p in sorted(d.glob("*.parquet"))
    )


def store() -> dict:
    """The tables build() reads, loaded once per process and reloaded when the files change."""
    sig = _signature()
    with _store_lock:
        if _store.get("sig") != sig:
            sales = pd.read_parquet(CLEAN / "sales.parquet")
            _store.clear()
            _store.update(
                sig=sig,
                facts=_load("parcel_facts").set_index("parcel_id"),
                parcels=gpd.read_parquet(CLEAN / "parcels.parquet", columns=PARCEL_COLUMNS),
                zoning=_load("parcel_zoning").drop_duplicates(),
                flood=_load("parcel_flood").drop_duplicates(),
                env=_load("parcel_env_nearby").drop_duplicates(),
                sales=sales[sales["arms_length"] & ~sales["multi_parcel"]],
                permits=pd.read_parquet(
                    CLEAN / "pli_permits.parquet",
                    columns=[
                        "parcel_id",
                        "permit_id",
                        "permit_type",
                        "work_type",
                        "issue_date",
                        "status",
                    ],
                ),
                manifests={},
            )
            _ = _store["parcels"].sindex  # build the spatial index once
        return _store


def _within(gdf: gpd.GeoDataFrame, geom, distance: float) -> gpd.GeoDataFrame:
    """Rows within `distance` of geom, in table order (same result as a dwithin scan)."""
    idx = gdf.sindex.query(geom, predicate="dwithin", distance=distance)
    return gdf.iloc[np.sort(idx)]


def build(ids: list[str], live: bool = False) -> dict:
    """SiteContext for one parcel or an assemblage.

    live=False: everything from the refreshed store (reproducible; used for fixtures).
    live=True: fast-changing records are fetched from the source APIs for these parcels,
    falling back to the stored copy per record if a lookup fails (see navigator_pipeline.live).
    """
    st = store()
    facts = st["facts"]
    ids = resolve_ids(ids, facts)
    f = facts.loc[ids]
    pts = st["parcels"]
    geoms = pts[pts["parcel_id"].isin(ids)].set_index("parcel_id").loc[ids]
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
    z = st["zoning"]
    z = z[z["parcel_id"].isin(ids)].merge(
        f["lot_area_sqft_gis"].rename("lot"), left_on="parcel_id", right_index=True
    )
    z["a"] = z["share"] * z["lot"]
    zoning = [
        {"code": code, "kind": kind, "share": round(a / lot.sum(), 4)}
        for (code, kind), a in z.groupby(["code", "kind"])["a"].sum().items()
    ]

    fl = st["flood"]
    fl = fl[fl["parcel_id"].isin(ids)].merge(
        f["lot_area_sqft_gis"].rename("lot"), left_on="parcel_id", right_index=True
    )
    fl["a"] = fl["share"] * fl["lot"]
    flood_zones = [
        {"code": zc, "share": round(a / lot.sum(), 4)}
        for zc, a in fl.groupby("flood_zone")["a"].sum().items()
    ]

    env = st["env"]
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
    sales = st["sales"]
    cutoff = pd.Timestamp.today() - pd.DateOffset(years=COMPS_YEARS)
    sales = sales[sales["sale_date"] >= cutoff]
    near = _within(pts, site, COMPS_RADIUS_FT)[
        [
            "parcel_id",
            "geometry",
            "lot_area_sqft_gis",
            "living_area_sqft",
            "property_class",
            "year_built",
        ]
    ]
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
    touch = _within(pts, site, 1.0)
    touch = touch[~touch["parcel_id"].isin(ids)]
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

    for record, key in LIVE_RECORDS.items():
        provenance[record] = _source([key])

    permits = st["permits"]
    permits = permits[permits["parcel_id"].isin(ids)].sort_values("issue_date", ascending=False)
    recent_permits = [
        {
            "permit_id": str(r.permit_id),
            "permit_type": _clean(r.permit_type),
            "work_type": _clean(r.work_type),
            "issue_date": _clean(r.issue_date),
            "status": _clean(r.status),
        }
        for r in permits.head(20).itertuples()
    ]

    zba_note = provenance["zba_cases"]
    ctx = {
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
            "recent_permits": recent_permits,
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
    if live:
        _apply_live(ctx, ids, near)
    return ctx


def _apply_live(ctx: dict, ids: list[str], near: pd.DataFrame) -> None:
    """Overlay live records on a snapshot SiteContext; mark provenance per record."""
    res = live_lookups.fetch_all(ids)
    prov = ctx["provenance"]
    title = ctx["title"]

    for record, r in res.items():
        if r["ok"]:
            prov[record].update(
                retrieved="live", retrieved_at=r["at"], as_of=r["at"][:10], note=None
            )
        else:
            prov[record]["note"] = (
                f"Live lookup failed ({r['error']}); using the stored copy "
                f"from {prov[record]['as_of']}."
            )

    if res["assessment"]["ok"]:
        for p in ctx["parcels"]:
            rows = res["assessment"]["data"].get(p["parcel_id"]) or []
            if rows:
                fields = live_lookups.assessment_fields(rows[0])
                municode = fields.pop("municode")
                p.update({k: v for k, v in fields.items() if v is not None})
                p["owner_type"] = owner_type(
                    p["current_use"], municode in range(101, 133) if municode else False
                )

    if res["city_inventory"]["ok"]:
        rows = [r for pid in ids for r in res["city_inventory"]["data"].get(pid, [])]
        title["city_inventory_status"] = rows[0].get("current_status") if rows else None
        title["pending_transfer_to"] = PENDING.get(rows[0].get("inventory_type")) if rows else None
        if rows:
            for p in ctx["parcels"]:
                p["owner_type"] = "city"

    if res["tax_liens"]["ok"]:
        title["tax_lien_total_usd"] = float(
            sum(
                live_lookups._num(r.get("total_amount"))
                for pid in ids
                for r in res["tax_liens"]["data"].get(pid, [])
            )
        )
    if res["condemned"]["ok"]:
        title["condemned"] = any(res["condemned"]["data"].get(pid) for pid in ids)
    if res["permits"]["ok"]:
        title["recent_permits"] = live_lookups.permit_rows(
            [r for pid in ids for r in res["permits"]["data"].get(pid, [])]
        )

    if res["recent_sales"]["ok"]:
        sales = ctx["market"]["sales"]
        seen = {(s["parcel_id"], str(s["sale_date"]), float(s["price"])) for s in sales}
        cutoff = (pd.Timestamp.today() - pd.DateOffset(years=COMPS_YEARS)).date().isoformat()
        info = near.set_index("parcel_id")
        added = 0
        for r in res["recent_sales"]["data"]:
            pid, day = r.get("PARID"), str(r.get("SALEDATE"))[:10]
            price = live_lookups._num(r.get("PRICE"))
            code = str(r.get("SALECODE") or "").strip()
            if (
                pid not in info.index
                or pid in ids
                or code not in VALID_SALE_CODES
                or price <= 1000
                or day < cutoff
                or (pid, day, price) in seen
            ):
                continue
            n = info.loc[pid]
            sales.append(
                {
                    "parcel_id": pid,
                    "sale_date": day,
                    "price": price,
                    "lot_area_sqft": _clean(n["lot_area_sqft_gis"]),
                    "building_sqft": _clean(n["living_area_sqft"]),
                    "property_class": _clean(n["property_class"]),
                    "year_built": _clean(n["year_built"]),
                    "sale_code": code,
                    "distance_ft": round(float(n["distance_ft"]), 1),
                }
            )
            seen.add((pid, day, price))
            added += 1
        sales.sort(key=lambda s: str(s["sale_date"]), reverse=True)
        del sales[200:]
        prov["recent_sales"]["note"] = f"{added} sale(s) newer than the stored copy added."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parcel_ids", nargs="+", help="county ids or dashed block-lots")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--live", action="store_true", help="look up fast-changing records live")
    args = ap.parse_args()
    ctx = build(args.parcel_ids, live=args.live)
    text = json.dumps(ctx, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
