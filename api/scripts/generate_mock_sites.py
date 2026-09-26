"""Generate illustrative mock parcels for the map, search and report (docs/06-mock-data.md).

    uv run python api/scripts/generate_mock_sites.py

Synthetic lots on rotated street grids around real neighborhood centers. Each lot gets a
valid SiteContext (facts only, EPSG:2272, shares 0-1, unknowns as null with a provenance
note); market comps are borrowed from the nearest golden parcel. The candidates are scored
by the real engine, so every judgment is engine output on fake facts. The 8 golden parcels
are included as real, non-illustrative sites.

Output (committed; regenerate after changing this script or the engine):
    fixtures/mock/generated/summaries.json          ParcelSummary for every lot
    fixtures/mock/generated/parcels.geojson         lot geometry, EPSG:4326
    fixtures/mock/generated/map_features.geojson    transit stops, parks, school, neighborhoods
    fixtures/mock/generated/site_analysis/*.json    SiteAnalysis for each synthetic candidate

Dev-only: the engine is imported from sandbox/ until it moves to navigator_engine. The API
never imports sandbox.
"""

import copy
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import transform, unary_union

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))  # for `sandbox`, which is not an installed package

from navigator_api.summaries import summarize  # noqa: E402
from navigator_contracts import SCHEMA_VERSION, SiteAnalysis, SiteContext  # noqa: E402
from sandbox.engine_v0.analyze import analyze  # noqa: E402

SEED = 20260926
GOLDEN = REPO / "fixtures" / "golden"
OUT = REPO / "fixtures" / "mock" / "generated"

TO_2272 = Transformer.from_crs("EPSG:4326", "EPSG:2272", always_xy=True)
TO_4326 = Transformer.from_crs("EPSG:2272", "EPSG:4326", always_xy=True)

STREET_FT = 50
LOTS_PER_ROW = 7


@dataclass(frozen=True)
class Area:
    name: str
    lon: float
    lat: float
    lots: int
    rotation_deg: float
    in_city: bool = True


AREAS = [
    Area("Hazelwood", -79.943, 40.405, 120, -16),
    Area("Greenfield", -79.938, 40.423, 90, 8),
    Area("Glen Hazel", -79.927, 40.398, 60, -28),
    Area("Mt. Lebanon", -80.049, 40.373, 5, 12, in_city=False),
]

DISTRICTS = (["R1D-M", "R2-M", "R3-M", "RM-M", "LNC"], [0.20, 0.35, 0.25, 0.15, 0.05])
OWNERS = (["private", "land_bank", "ura", "city"], [0.70, 0.15, 0.08, 0.07])
CANDIDATE_SHARE = 0.15


@dataclass
class Lot:
    parcel_id: str
    block_lot: str
    area: Area
    polygon: Polygon  # EPSG:2272
    row: int  # lots in the same row and block share side lot lines
    block: int
    candidate: bool = False
    display_name: str = ""
    assembly_id: str | None = None
    overrides: dict | None = None


# ---------------------------------------------------------------- geometry


def layout(area: Area, rng: np.random.Generator, first_index: int) -> list[Lot]:
    """Blocks of 2 rows x 7 lots on a rotated grid centered on the area."""
    cx, cy = TO_2272.transform(area.lon, area.lat)
    n_blocks = math.ceil(area.lots / (2 * LOTS_PER_ROW))
    cols = max(1, round(math.sqrt(n_blocks * 1.6)))
    theta = math.radians(area.rotation_deg)

    def place(x: float, y: float) -> tuple[float, float]:
        return (
            cx + x * math.cos(theta) - y * math.sin(theta),
            cy + x * math.sin(theta) + y * math.cos(theta),
        )

    # One lot depth per area and the same widths on both sides of a block, so lot lines line
    # up across the block and blocks tile into a regular grid (MapBase.dc.html).
    depth = float(rng.uniform(90, 125))
    block_len = LOTS_PER_ROW * 34.0
    block_w, block_h = block_len + STREET_FT, 2 * depth + STREET_FT
    rows_of_blocks = math.ceil(n_blocks / cols)
    x0, y0 = -cols * block_w / 2, -rows_of_blocks * block_h / 2
    lots: list[Lot] = []
    for b in range(n_blocks):
        bx, by = x0 + (b % cols) * block_w, y0 + (b // cols) * block_h
        raw = rng.uniform(28, 40, LOTS_PER_ROW)
        widths = [float(w) for w in raw / raw.sum() * block_len]
        for row in range(2):
            x = bx
            y = by + row * depth
            for width in widths:
                if len(lots) == area.lots:
                    return lots
                corners = [(x, y), (x + width, y), (x + width, y + depth), (x, y + depth)]
                n = first_index + len(lots)
                lots.append(
                    Lot(
                        parcel_id=f"0000X{n:05d}000000",
                        block_lot=f"0-X-{n + 1}",
                        area=area,
                        polygon=Polygon([place(px, py) for px, py in corners]),
                        row=row,
                        block=first_index + b,
                    )
                )
                x += width
    return lots


def to_4326(geom):
    return transform(lambda x, y, z=None: TO_4326.transform(x, y), geom)


def rounded(geom_4326) -> dict:
    """GeoJSON with coordinates rounded to ~1 cm, to keep the committed files small."""
    return json.loads(json.dumps(mapping(geom_4326)), parse_float=lambda s: round(float(s), 7))


# ---------------------------------------------------------------- facts


def load_golden() -> list[tuple[str, dict, dict]]:
    out = []
    for path in sorted((GOLDEN / "site_context").glob("*.json")):
        ctx = json.loads(path.read_text())
        analysis = json.loads((GOLDEN / "site_analysis" / path.name).read_text())
        out.append((path.stem, ctx, analysis))
    return out


def nearest_template(point: Point, golden: list[tuple[str, dict, dict]], in_city: bool) -> dict:
    """Market comps and provenance come from the nearest golden parcel in the same coverage."""
    pool = [g for g in golden if bool(g[1]["zoning"]) == in_city] or golden
    return min(pool, key=lambda g: shape(g[1]["parcels"][0]["geometry"]).distance(point))[1]


def pick(rng: np.random.Generator, choices: tuple[list, list[float]]):
    values, weights = choices
    return values[int(rng.choice(len(values), p=weights))]


def build_context(
    lot: Lot,
    template: dict,
    neighbors: list[Lot],
    transit: list[Point],
    rng: np.random.Generator,
) -> dict:
    ctx = copy.deepcopy(template)
    poly = lot.polygon
    vacant = lot.candidate and rng.random() < 0.7
    assessed_land = float(round(rng.uniform(4_000, 40_000), -2))
    in_city = lot.area.in_city

    slope_roll = rng.random()
    slope = (
        0.0
        if slope_roll < 0.60
        else rng.uniform(0.05, 0.15)
        if slope_roll < 0.85
        else rng.uniform(0.25, 0.60)
    )
    undermined = float(rng.uniform(0.1, 1.0)) if rng.random() < 0.20 else 0.0
    flood = (
        [{"code": "AE", "share": round(float(rng.uniform(0.1, 0.5)), 3)}]
        if rng.random() < 0.05
        else []
    )
    frontage = None if rng.random() < 0.15 else "street"
    lien = float(round(rng.uniform(1_000, 15_000), -2)) if rng.random() < 0.12 else 0.0

    ctx["schema_version"] = SCHEMA_VERSION
    ctx["parcels"] = [
        {
            "parcel_id": lot.parcel_id,
            "block_lot": lot.block_lot,
            "municipality": "PITTSBURGH" if in_city else lot.area.name.upper(),
            "address": "",
            "geometry": mapping(poly),
            "lot_area_sqft": round(poly.area, 1),
            "frontage_ft": None,
            "current_use": "VACANT LAND" if vacant else "SINGLE FAMILY",
            "has_structure": not vacant,
            "assessed_land": assessed_land,
            "assessed_total": assessed_land
            if vacant
            else assessed_land + float(round(rng.uniform(20_000, 90_000), -2)),
            "owner_type": pick(rng, OWNERS) if lot.candidate else "private",
        }
    ]
    ctx["zoning"] = (
        [{"code": pick(rng, DISTRICTS), "kind": "district", "share": 1.0}] if in_city else []
    )
    ctx["physical"] = {
        "steep_slope_share": round(float(slope), 3) if in_city else None,
        "landslide_prone_share": round(float(slope) * 0.5, 3) if in_city else None,
        "undermined_share": round(undermined, 3) if in_city else None,
        "deep_mined_share": round(undermined, 3),
        "aml_share": 0.0,
        "flood_zones": flood,
        "observed_landslides_within_500ft": int(rng.integers(0, 3)) if slope > 0.2 else 0,
    }
    ctx["environmental"] = []
    ctx["infrastructure"] = {
        "combined_sewershed": bool(rng.random() < 0.70),
        "frontage_type": frontage,
        "water_provider": template["infrastructure"]["water_provider"],
    }
    ctx["access"] = {
        "frequent_transit_distance_ft": round(min(poly.centroid.distance(s) for s in transit), 1)
        if transit
        else None
    }
    ctx["adjacent"] = [
        {
            "parcel_id": n.parcel_id,
            "address": None,
            "has_structure": not n.candidate,
            "shared_edge_ft": round(poly.intersection(n.polygon.buffer(0.5)).length / 2, 1),
        }
        for n in neighbors
    ]
    ctx["title"] = {
        "tax_lien_total_usd": lien,
        "condemned": False,
        "city_inventory_status": "Available for Sale"
        if ctx["parcels"][0]["owner_type"] == "city"
        else None,
        "pending_transfer_to": None,
    }
    ctx["area"] = {**template["area"], "neighborhood": lot.area.name if in_city else None}
    ctx["zba_cases_nearby"] = None
    ctx["provenance"] = {
        **template["provenance"],
        "mock": {
            "name": "Illustrative mock generator (api/scripts/generate_mock_sites.py)",
            "url": None,
            "as_of": None,
            "note": "Synthetic lot: facts are generated, not measured. Market data is "
            "borrowed from the nearest real golden parcel.",
        },
    }
    if frontage is None:
        ctx["provenance"]["frontage"] = {
            **ctx["provenance"].get(
                "frontage", {"name": "Street frontage", "url": None, "as_of": None}
            ),
            "note": "Street acceptance unknown for this lot (illustrative)",
        }
    for key, value in (lot.overrides or {}).items():
        if "." not in key:
            ctx[key] = value
            continue
        section, field = key.split(".")
        target = ctx[section][0] if section == "parcels" else ctx[section]
        target[field] = value
    return ctx


# ---------------------------------------------------------------- map features


def map_features(lots_by_area: dict[str, list[Lot]]) -> tuple[list, list[Point]]:
    features, stops = [], []
    for area, lots in lots_by_area.items():
        outline = unary_union([lot.polygon for lot in lots]).convex_hull.buffer(40)
        features.append(
            {
                "type": "Feature",
                "geometry": rounded(to_4326(outline)),
                "properties": {"kind": "neighborhood", "name": area},
            }
        )
    # A bus line along the south edge of Hazelwood, like Second Ave in the mockup.
    hazelwood = unary_union([lot.polygon for lot in lots_by_area["Hazelwood"]])
    minx, miny, maxx, _ = hazelwood.bounds
    line = LineString([(minx - 300, miny - 120), (maxx + 300, miny + 260)])
    for i in range(7):
        stop = line.interpolate(i / 6, normalized=True)
        stops.append(stop)
        features.append(
            {
                "type": "Feature",
                "geometry": rounded(to_4326(stop)),
                "properties": {"kind": "transit_stop", "name": f"Second Ave stop {i + 1}"},
            }
        )
    for area in ["Hazelwood", "Greenfield"]:
        _, _, maxx, maxy = unary_union([lot.polygon for lot in lots_by_area[area]]).bounds
        park = Polygon(
            [
                (maxx + 80, maxy - 400),
                (maxx + 380, maxy - 400),
                (maxx + 380, maxy - 100),
                (maxx + 80, maxy - 100),
            ]
        )
        features.append(
            {
                "type": "Feature",
                "geometry": rounded(to_4326(park)),
                "properties": {"kind": "park", "name": f"{area} park"},
            }
        )
    school = unary_union([lot.polygon for lot in lots_by_area["Glen Hazel"]]).centroid
    features.append(
        {
            "type": "Feature",
            "geometry": rounded(to_4326(Point(school.x, school.y + 700))),
            "properties": {"kind": "school", "name": "Glen Hazel school"},
        }
    )
    return features, stops


# ---------------------------------------------------------------- main


def choose_candidates(lots: list[Lot], rng: np.random.Generator) -> None:
    for lot in lots:
        lot.candidate = rng.random() < CANDIDATE_SHARE
    hazelwood = [lot for lot in lots if lot.area.name == "Hazelwood"]
    outside = [lot for lot in lots if not lot.area.in_city]

    # Required special cases (docs/06-mock-data.md).
    sample_a = hazelwood[0]
    sample_a.candidate = True
    sample_a.overrides = {
        "zoning": [{"code": "R3-M", "kind": "district", "share": 1.0}],
        "physical.steep_slope_share": 0.0,
        "physical.landslide_prone_share": 0.0,
        "physical.undermined_share": 0.0,
        "physical.deep_mined_share": 0.0,
        "physical.flood_zones": [],
        "infrastructure.frontage_type": "street",
        "infrastructure.combined_sewershed": True,
        "parcels.current_use": "VACANT LAND",
        "parcels.has_structure": False,
        "parcels.owner_type": "private",
        "title.tax_lien_total_usd": 0.0,
    }
    hazelwood[9].candidate = True
    hazelwood[9].overrides = {
        "physical.steep_slope_share": 0.45,
        "physical.landslide_prone_share": 0.3,
    }
    for lot in (hazelwood[20], hazelwood[35]):
        lot.candidate = True
        lot.overrides = {"infrastructure.frontage_type": None}
    for lot in (hazelwood[44], hazelwood[45]):
        lot.candidate = True
        lot.assembly_id = "assembly-1"
    for lot in outside:
        lot.candidate = False
    outside[2].candidate = True


def main() -> None:
    rng = np.random.default_rng(SEED)
    golden = load_golden()

    lots: list[Lot] = []
    lots_by_area: dict[str, list[Lot]] = {}
    for area in AREAS:
        area_lots = layout(area, rng, first_index=len(lots))
        lots_by_area[area.name] = area_lots
        lots.extend(area_lots)
    choose_candidates(lots, rng)

    letters = iter(_names())
    for lot in lots:
        lot.display_name = (
            f"Sample lot {next(letters)}" if lot.candidate else f"Lot {lot.block_lot}"
        )

    features, stops = map_features(lots_by_area)

    (OUT / "site_analysis").mkdir(parents=True, exist_ok=True)
    for old in (OUT / "site_analysis").glob("*.json"):
        old.unlink()

    summaries, parcel_features = [], []
    for lot in lots:
        neighbors = [
            n
            for n in lots
            if n is not lot
            and n.block == lot.block
            and n.row == lot.row
            and n.polygon.distance(lot.polygon) < 1
        ]
        template = nearest_template(lot.polygon.centroid, golden, lot.area.in_city)
        raw = build_context(lot, template, neighbors, stops, rng)
        context = SiteContext.model_validate(raw)
        analysis = None
        if lot.candidate:
            analysis = SiteAnalysis.model_validate(analyze(raw, {}))
            path = OUT / "site_analysis" / f"{lot.parcel_id}.json"
            path.write_text(analysis.model_dump_json(by_alias=True, indent=1) + "\n")
        centroid_4326 = to_4326(lot.polygon.centroid)
        summaries.append(
            summarize(
                context,
                analysis,
                display_name=lot.display_name,
                centroid=(round(centroid_4326.x, 6), round(centroid_4326.y, 6)),
                candidate=lot.candidate,
                illustrative=True,
                assembly_id=lot.assembly_id,
            )
        )
        parcel_features.append(_feature(lot.parcel_id, to_4326(lot.polygon)))

    for _, raw, raw_analysis in golden:
        context = SiteContext.model_validate(raw)
        analysis = SiteAnalysis.model_validate(raw_analysis)
        geom = to_4326(shape(raw["parcels"][0]["geometry"]))
        parcel = raw["parcels"][0]
        summaries.append(
            summarize(
                context,
                analysis,
                display_name=(parcel["address"] or parcel["block_lot"]).title(),
                centroid=(round(geom.centroid.x, 6), round(geom.centroid.y, 6)),
                candidate=True,
                illustrative=False,
            )
        )
        parcel_features.append(_feature(parcel["parcel_id"], geom))

    _write(OUT / "summaries.json", [s.model_dump(mode="json") for s in summaries])
    _write(OUT / "parcels.geojson", {"type": "FeatureCollection", "features": parcel_features})
    _write(OUT / "map_features.geojson", {"type": "FeatureCollection", "features": features})

    candidates = [s for s in summaries if s.candidate]
    bands: dict[str, int] = {}
    for s in candidates:
        bands[str(s.band)] = bands.get(str(s.band), 0) + 1
    print(f"{len(summaries)} parcels, {len(candidates)} candidates; bands: {bands}")
    print(f"Wrote {OUT.relative_to(REPO)}")


def _names():
    yield from "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for first in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for second in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            yield first + second


def _feature(parcel_id: str, geom_4326) -> dict:
    return {
        "type": "Feature",
        "geometry": rounded(geom_4326),
        "properties": {"parcel_id": parcel_id},
    }


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
