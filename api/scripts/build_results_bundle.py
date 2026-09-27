"""Build the real-data results bundle the API serves with SITE_SOURCE=pipeline.

    NAVIGATOR_DATA_DIR=/path/to/data uv run python api/scripts/build_results_bundle.py

Reads the pipeline's runtime store (data/, see pipeline/README.md), builds a SiteContext for
every candidate lot in scope with `live=False` (reproducible), scores it with the engine, and
writes a small bundle to results/ in the format the API already reads for mock data:

    results/summaries.json.gz        ParcelSummary for every parcel in scope
    results/parcels.geojson.gz       parcel shapes, EPSG:4326, simplified, 6 decimals
    results/map_features.geojson.gz  frequent transit stops, parks, all 90 neighborhoods
    results/site_analysis.jsonl.gz   {"parcel_id", "analysis"} per candidate
    results/manifest.json            versions, sources' as-of dates, counts, scope

Scope: every parcel in the demo neighborhoods (drawn on the map); the candidates are their
vacant lots of 1,500-20,000 sq ft, plus the 8 golden parcels. Dev-only: the engine is imported
from sandbox/ until it moves to navigator_engine. The API never imports sandbox.
"""

import functools
import gzip
import io
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))  # for `sandbox`, which is not an installed package

from navigator_api.models import ParcelSummary  # noqa: E402
from navigator_api.summaries import summarize  # noqa: E402
from navigator_contracts import SiteAnalysis, SiteContext  # noqa: E402
from navigator_pipeline import site_context as sc  # noqa: E402
from navigator_pipeline.settings import DATA_DIR  # noqa: E402
from sandbox.engine_v0.analyze import analyze  # noqa: E402

OUT = REPO / "results"
SCOPE = ["Hazelwood", "Greenfield", "Glen Hazel"]
LOT_SQFT = (1_500, 20_000)
FREQUENT_TRIPS = 64  # weekday trips: the contract's "frequent transit"
SIMPLIFY_FT = 0.5
MAP_MARGIN_FT = 2_000


def _cache_store_reads() -> None:
    """site_context.build re-reads the store for every parcel; read it once for the batch."""
    sc._load = functools.lru_cache(None)(sc._load)
    original = gpd.read_parquet
    cached = functools.lru_cache(None)(
        lambda path, cols: original(path, columns=list(cols) if cols else None)
    )
    sc.gpd.read_parquet = lambda path, columns=None, **_: cached(
        str(path), tuple(columns) if columns else None
    ).copy()


def _name(address: str | None, block_lot: str) -> str:
    """ "3864 2ND AVE" -> "3864 2nd Ave"; no address -> "Lot 56-L-343"."""
    if not isinstance(address, str) or not address.strip():
        return f"Lot {block_lot}"
    titled = address.strip().title()
    return re.sub(r"\b(\d+)(St|Nd|Rd|Th)\b", lambda m: m.group(1) + m.group(2).lower(), titled)


def _feature_json(gdf: gpd.GeoDataFrame, props: list[str]) -> list[dict]:
    """GeoJSON features with coordinates rounded to 6 decimals (about 10 cm)."""
    raw = json.loads(gdf[[*props, "geometry"]].to_json(drop_id=True))
    text = json.dumps(raw["features"])
    return json.loads(text, parse_float=lambda s: round(float(s), 6))


def _write_gz(path: Path, text: str) -> None:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:  # mtime=0: reproducible bytes
        gz.write(text.encode())
    path.write_bytes(buf.getvalue())


def _golden_ids() -> list[str]:
    ids = []
    for path in sorted((REPO / "fixtures" / "golden" / "site_context").glob("*.json")):
        ids.append(json.loads(path.read_text())["parcels"][0]["parcel_id"])
    return ids


def _text(value) -> str:
    """Store text columns can be NaN; the summary wants a string."""
    return value if isinstance(value, str) else ""


def _summary_from_facts(row: pd.Series, centroid: tuple[float, float]) -> ParcelSummary:
    """Parcels that aren't candidates: facts only, straight from the store."""
    return ParcelSummary(
        parcel_id=row.parcel_id,
        block_lot=row.block_lot or None,
        display_name=_name(row.address, row.block_lot),
        address=row.address if isinstance(row.address, str) else None,
        municipality=_text(row.municipality),
        neighborhood=_text(row.neighborhood) or None,
        zoning=[row.zoning_primary] if isinstance(row.zoning_primary, str) else [],
        lot_area_sqft=float(row.lot_area_sqft_gis),
        current_use=_text(row.current_use),
        owner_type=row.owner_type,
        assessed_land=None if pd.isna(row.assessed_land) else float(row.assessed_land),
        centroid=centroid,
        candidate=False,
        illustrative=False,
        has_structure=bool(row.has_structure),
    )


def _source_dates() -> dict[str, str]:
    dates = {}
    for manifest in sorted((DATA_DIR / "raw").glob("*/_manifest.json")):
        data = json.loads(manifest.read_text())
        dates[data.get("key", manifest.parent.name)] = data.get("source_as_of") or data.get(
            "fetched_at"
        )
    return dates


def main() -> None:
    started = time.time()
    _cache_store_reads()
    facts = sc._load("parcel_facts")
    golden = _golden_ids()

    in_scope = facts[facts.neighborhood.isin(SCOPE)]
    vacant = in_scope[
        (in_scope.current_use == "VACANT LAND")
        & in_scope.lot_area_sqft_gis.between(*LOT_SQFT)
        & in_scope.in_pittsburgh
    ]
    candidates = list(dict.fromkeys([*vacant.parcel_id, *golden]))
    shown = set(in_scope.parcel_id) | set(golden)

    shapes = gpd.read_parquet(
        DATA_DIR / "clean" / "parcels.parquet", columns=["parcel_id", "geometry"]
    )
    shapes = shapes[shapes.parcel_id.isin(shown)].copy()
    shapes["geometry"] = shapes.geometry.simplify(SIMPLIFY_FT)
    shapes_4326 = shapes.to_crs(4326)
    centroids = {
        pid: (round(pt.x, 6), round(pt.y, 6))
        for pid, pt in zip(shapes.parcel_id, shapes.geometry.centroid.to_crs(4326), strict=True)
    }

    summaries: dict[str, ParcelSummary] = {}
    analyses: list[str] = []
    versions = None
    failed: dict[str, str] = {}
    for i, pid in enumerate(candidates, 1):
        try:
            context = SiteContext.model_validate(sc.build([pid], live=False))
            analysis = SiteAnalysis.model_validate(analyze(context.model_dump(mode="json"), {}))
        except Exception as error:  # a parcel the store can't build: shown, not scored
            failed[pid] = f"{type(error).__name__}: {error}"[:200]
            continue
        parcel = context.parcels[0]
        summaries[pid] = summarize(
            context,
            analysis,
            display_name=_name(parcel.address, parcel.block_lot),
            centroid=centroids[pid],
            candidate=True,
            illustrative=False,
        )
        analyses.append(
            json.dumps(
                {"parcel_id": pid, "analysis": analysis.model_dump(mode="json", by_alias=True)},
                separators=(",", ":"),
            )
        )
        versions = analysis.versions
        if i % 100 == 0:
            print(f"  {i}/{len(candidates)} scored")

    for row in facts[facts.parcel_id.isin(shown - set(summaries))].itertuples(index=False):
        summaries[row.parcel_id] = _summary_from_facts(
            pd.Series(row._asdict()), centroids[row.parcel_id]
        )

    # Map layers near the scope only, except the 90 neighborhood outlines (search areas).
    area = shapes.geometry.union_all().buffer(MAP_MARGIN_FT)
    stops = gpd.read_parquet(DATA_DIR / "clean" / "transit_stops.parquet")
    stops = stops[(stops.trips_weekday >= FREQUENT_TRIPS) & stops.intersects(area)].copy()
    stops["kind"], stops["name"] = "transit_stop", stops.stop_name.str.title()
    parks = gpd.read_parquet(DATA_DIR / "clean" / "parks.parquet")
    parks = parks[parks.intersects(area)].copy()
    parks["kind"] = "park"
    parks["geometry"] = parks.geometry.simplify(5)
    hoods = gpd.read_parquet(DATA_DIR / "clean" / "neighborhoods.parquet")
    hoods["kind"], hoods["name"] = "neighborhood", hoods.neighborhood
    hoods["geometry"] = hoods.geometry.simplify(20)
    features = []
    for layer in (hoods, parks, stops):
        layer = layer[layer.geometry.geom_type.isin(["Point", "Polygon"])]
        features += _feature_json(layer.to_crs(4326), ["kind", "name"])

    OUT.mkdir(exist_ok=True)
    ordered = [summaries[pid] for pid in sorted(summaries)]
    _write_gz(OUT / "summaries.json.gz", json.dumps([s.model_dump(mode="json") for s in ordered]))
    _write_gz(
        OUT / "parcels.geojson.gz",
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": _feature_json(shapes_4326.sort_values("parcel_id"), ["parcel_id"]),
            }
        ),
    )
    _write_gz(
        OUT / "map_features.geojson.gz",
        json.dumps({"type": "FeatureCollection", "features": features}),
    )
    _write_gz(OUT / "site_analysis.jsonl.gz", "\n".join(sorted(analyses)) + "\n")

    bands: dict[str, int] = {}
    for s in ordered:
        if s.candidate:
            bands[str(s.band)] = bands.get(str(s.band), 0) + 1
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "script": "api/scripts/build_results_bundle.py",
        "scope": {"neighborhoods": SCOPE, "candidates": "vacant land, "
                  f"{LOT_SQFT[0]:,}-{LOT_SQFT[1]:,} sq ft, plus the golden parcels"},
        "versions": versions.model_dump(mode="json", by_alias=True) if versions else None,
        "counts": {
            "parcels": len(ordered),
            "candidates_scored": sum(s.candidate for s in ordered),
            "failed_to_build": len(failed),
            "bands": bands,
            "map_features": len(features),
        },
        "failed": failed,
        "source_as_of": _source_dates(),
    }  # fmt: skip
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"Wrote {OUT.relative_to(REPO)} in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
