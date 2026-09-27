"""Publish the results bundle (results/): what the API and the demo serve without the data store.

    uv run python -m navigator_pipeline.publish                  # Hazelwood + golden parcels
    uv run python -m navigator_pipeline.publish --area Greenfield --out /tmp/greenfield

Reads the local data store (after `navigator_pipeline.refresh`), builds a SiteContext for every
candidate lot (vacant land) in the area from the stored copy, scores it with the engine (the
engine's pick plus one row per building type), and writes small, validated files. Contexts are
built without live lookups so the bundle is reproducible; the manifest records the data dates.

No owner names or mailing addresses are published: owner *type* only (the store never keeps
names). Layout and columns: results/README.md, written by this command.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from navigator_contracts import SiteAnalysis, SiteContext
from navigator_engine import analyze
from navigator_engine.rules_engine import TEMPLATES
from navigator_pipeline import site_context
from navigator_pipeline.bundle import CSV_COLUMNS, FILES, MAX_BYTES, RESULTS, write_jsonl_gz
from navigator_pipeline.settings import CLEAN, RAW, REPO_ROOT

GOLDEN_CONTEXTS = REPO_ROOT / "fixtures" / "golden" / "site_context"
SIMPLIFY_FT = 0.5  # parcel outlines: well below what a map shows
DECIMALS = 6  # about 10 cm
TO_4326 = Transformer.from_crs("EPSG:2272", "EPSG:4326", always_xy=True)


def _round(geom):
    return shapely.transform(geom, lambda c: np.round(c, DECIMALS))


def _geojson(geom) -> dict:
    return json.loads(shapely.to_geojson(geom))


def _to_4326(gs: gpd.GeoSeries, tolerance: float) -> gpd.GeoSeries:
    simple = gs.simplify(tolerance, preserve_topology=True) if tolerance else gs
    return simple.to_crs(4326).apply(_round)


def _num(v, digits: int = 0):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), digits) if digits else round(float(v))


def _golden_ids() -> list[str]:
    return [
        json.loads(p.read_text())["parcels"][0]["parcel_id"]
        for p in sorted(GOLDEN_CONTEXTS.glob("*.json"))
    ]


def lead_option(a: dict) -> dict | None:
    """The option the engine's metrics describe (None when nothing was scored)."""
    m = a["metrics"]
    return next((o for o in a["options"] if m and o["label"] == m["option"]), None)


def approval_path(a: dict, opt: dict | None) -> str:
    """by_right | the approvals needed ('variance+subdivision') | not_allowed | not_covered."""
    if a["verdict"]["band"] == "not_scored":
        return "not_covered"
    if not opt:
        return "not_allowed"
    relief = [r.split(" (")[0] for r in opt["relief"]]
    return "+".join(dict.fromkeys(relief)) or "by_right"


def approval_basis(opt: dict | None) -> str | None:
    """Where the approval odds come from: by_right, model, measured, placeholder (joined by +)."""
    if not opt:
        return None
    if not opt["relief"]:
        return "by_right"
    kinds = []
    for src in opt["entitlement_basis"]:
        kind = (
            "model"
            if "model" in src
            else "measured"
            if "measured" in src
            else "placeholder"
            if "PLACEHOLDER" in src
            else "other"
        )
        kinds.append(kind)
    return "+".join(dict.fromkeys(kinds)) or None


def csv_row(ctx: dict, a: dict, product: str, lead: bool, centroid) -> dict:
    """One building type on one lot. `a` is the engine's own analysis for the lead row and a
    per-type analysis (analyze(..., program=...)) for the others."""
    p = ctx["parcels"][0]
    districts = sorted(
        (z for z in ctx["zoning"] if z["kind"] == "district"), key=lambda z: -z["share"]
    )
    rc = a.get("rule_checks") or {}
    rep = next(
        (x for x in rc.get("programs", []) if x["product_type"] == product and x["representative"]),
        None,
    )
    opt = lead_option(a) or {}
    m = a["metrics"] or {}
    rng = lambda r, k, d=0: _num((r or {}).get(k), d)  # noqa: E731
    score, months = a["verdict"]["score_range"], m.get("months_to_permit")
    prem, land = opt.get("site_cost_premium"), m.get("max_land_price")
    top = a["flags"][0] if a["flags"] else None
    return {
        "parcel_id": p["parcel_id"],
        "block_lot": p["block_lot"],
        "neighborhood": ctx["area"]["neighborhood"],
        "zoning_district": districts[0]["code"] if districts else None,
        "lot_area_sqft": _num(p["lot_area_sqft"]),
        "owner_type": p["owner_type"],
        "assessed_value": _num(p["assessed_land"]),
        "product": product,
        "units": opt.get("units") or (rep["units"] if rep else None),
        "lead": lead,
        "score_p10": rng(score, "p10", 1),
        "score_p50": rng(score, "p50", 1),
        "score_p90": rng(score, "p90", 1),
        "band": a["verdict"]["band"],
        "approval_path": approval_path(a, opt),
        "approval_prob_p10": rng(m.get("approval_prob"), "p10", 3),
        "approval_prob_p50": rng(m.get("approval_prob"), "p50", 3),
        "approval_prob_p90": rng(m.get("approval_prob"), "p90", 3),
        "approval_basis": approval_basis(opt or None),
        "months_p10": rng(months, "p10", 1),
        "months_p50": rng(months, "p50", 1),
        "months_p90": rng(months, "p90", 1),
        "cost_premium_p10": rng(prem, "p10"),
        "cost_premium_p50": rng(prem, "p50"),
        "cost_premium_p90": rng(prem, "p90"),
        "max_land_p10": rng(land, "p10"),
        "max_land_p50": rng(land, "p50"),
        "max_land_p90": rng(land, "p90"),
        "top_flag": top["title"] if top else None,
        "top_flag_severity": top["severity"] if top else None,
        "unknown_flags": ";".join(f["id"] for f in a["flags"] if f["severity"] == "unknown"),
        "lon": centroid[0],
        "lat": centroid[1],
    }


def summary(pid: str, facts: pd.Series, zoning: list[str], centroid, a: dict | None) -> dict:
    """ParcelSummary-shaped (navigator_api.models); facts from the store, judgments copied."""
    address = facts["address"] if isinstance(facts["address"], str) else None
    out = {
        "parcel_id": pid,
        "block_lot": facts["block_lot"] or None,
        "display_name": (address or facts["block_lot"] or pid).title(),
        "address": address,
        "municipality": facts["municipality"]
        if isinstance(facts["municipality"], str)
        else ("PITTSBURGH" if facts["in_pittsburgh"] else "UNKNOWN"),
        "neighborhood": facts["neighborhood"] if isinstance(facts["neighborhood"], str) else None,
        "zoning": zoning,
        "lot_area_sqft": float(facts["lot_area_sqft_gis"]),
        "current_use": facts["current_use"]
        if isinstance(facts["current_use"], str)
        else "NO ASSESSMENT RECORD",
        "owner_type": facts["owner_type"],
        "assessed_land": _num(facts["assessed_land"], 2),
        "centroid": list(centroid),
        "candidate": a is not None,
        "illustrative": False,
        "assembly_id": None,
        "score": None,
        "band": None,
        "top_flag": None,
        "top_flag_severity": None,
        "max_land_price": None,
        "lead_option": None,
    }
    if a is None:
        return out
    m = a["metrics"]
    lead = lead_option(a)
    top = a["flags"][0] if a["flags"] else None
    out.update(
        score=a["verdict"]["score"],
        band=a["verdict"]["band"],
        top_flag=top["title"] if top else None,
        top_flag_severity=top["severity"] if top else None,
        max_land_price=m["max_land_price"] if m else None,
        lead_option={k: lead[k] for k in ("label", "product_type", "units", "relief")}
        if lead
        else None,
    )
    return out


def map_features(area: str) -> dict:
    """The neighbourhood outline, its parks and its transit stops (EPSG:4326)."""
    hoods = gpd.read_parquet(CLEAN / "neighborhoods.parquet")
    hood = hoods[hoods["neighborhood"].eq(area)]
    if hood.empty:
        return {"type": "FeatureCollection", "features": []}
    outline = hood.geometry.union_all()
    feats = [
        {
            "type": "Feature",
            "geometry": _geojson(_to_4326(gpd.GeoSeries([outline], crs=hood.crs), 5.0).iloc[0]),
            "properties": {"kind": "neighborhood", "name": area},
        }
    ]
    parks = gpd.read_parquet(CLEAN / "parks.parquet")
    parks = parks[parks.intersects(outline)]
    for name, geom in zip(parks["name"], _to_4326(parks.geometry, 5.0), strict=True):
        feats.append(
            {
                "type": "Feature",
                "geometry": _geojson(geom),
                "properties": {"kind": "park", "name": name if isinstance(name, str) else None},
            }
        )
    stops = gpd.read_parquet(CLEAN / "transit_stops.parquet")
    stops = stops[stops.within(outline.buffer(300))].sort_values("stop_id")
    for name, geom in zip(stops["stop_name"], _to_4326(stops.geometry, 0), strict=True):
        feats.append(
            {
                "type": "Feature",
                "geometry": _geojson(geom),
                "properties": {"kind": "transit_stop", "name": name},
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def data_as_of() -> dict:
    keys = sorted({k for v in site_context.PROVENANCE.values() for k in v})
    keys += sorted(set(site_context.LIVE_RECORDS.values()) - set(keys))
    out = {}
    for k in keys:
        m = json.loads((RAW / k / "_manifest.json").read_text())
        out[k] = {"source_as_of": m.get("source_as_of"), "fetched_at": m.get("fetched_at")}
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(area: str, out: Path, golden: bool = True) -> dict:
    st = site_context.store()
    facts = st["facts"]
    scope = facts.index[facts["neighborhood"].eq(area)].tolist()
    extra = [g for g in (_golden_ids() if golden else []) if g in facts.index and g not in scope]
    scope = sorted(scope) + extra
    f = facts.loc[scope]
    vacant = f["current_use"].eq("VACANT LAND") & f["has_structure"].eq(False)
    candidates = [pid for pid in scope if vacant[pid] or pid in extra]

    geoms = st["parcels"].set_index("parcel_id").loc[scope, "geometry"]
    geoms = gpd.GeoSeries(geoms, crs=st["parcels"].crs)
    cx, cy = TO_4326.transform(geoms.centroid.x.to_numpy(), geoms.centroid.y.to_numpy())
    centroid = {
        pid: (round(float(x), DECIMALS), round(float(y), DECIMALS))
        for pid, x, y in zip(scope, cx, cy, strict=True)
    }
    zt = st["zoning"]
    zoning = (
        zt[zt["parcel_id"].isin(scope) & zt["kind"].eq("district")]
        .groupby("parcel_id")["code"]
        .apply(lambda s: sorted(set(s)))
        .to_dict()
    )

    contexts, analyses, rows = [], {}, []
    for i, pid in enumerate(candidates, 1):
        ctx = site_context.build([pid], live=False)
        ctx = json.loads(SiteContext.model_validate(ctx).model_dump_json(by_alias=True))
        a = analyze(ctx)
        SiteAnalysis.model_validate(a)
        contexts.append({"parcel_id": pid, "context": ctx})
        analyses[pid] = a
        lead = (lead_option(a) or {}).get("product_type")
        for product in TEMPLATES:
            ap = a if product == lead else analyze(ctx, program={"product_type": product})
            rows.append(csv_row(ctx, ap, product, product == lead, centroid[pid]))
        if i % 100 == 0:
            print(f"  {i}/{len(candidates)} candidates scored", flush=True)

    out.mkdir(parents=True, exist_ok=True)
    write_jsonl_gz(out / FILES["contexts"], contexts)
    write_jsonl_gz(
        out / FILES["analyses"],
        [{"parcel_id": pid, "analysis": analyses[pid]} for pid in candidates],
    )
    summaries = [
        summary(pid, f.loc[pid], zoning.get(pid, []), centroid[pid], analyses.get(pid))
        for pid in scope
    ]
    (out / FILES["summaries"]).write_text(json.dumps(summaries, indent=1, default=str) + "\n")
    whole = ["lot_area_sqft", "assessed_value", "units"]
    whole += [c for c in CSV_COLUMNS if c.startswith(("cost_premium_", "max_land_"))]
    table = pd.DataFrame(rows, columns=CSV_COLUMNS).astype(dict.fromkeys(whole, "Int64"))
    table.to_csv(out / FILES["summaries_csv"], index=False)

    shapes = _to_4326(geoms, SIMPLIFY_FT)
    parcels = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": _geojson(shapes[pid]),
                "properties": {"parcel_id": pid, "block_lot": f.loc[pid, "block_lot"]},
            }
            for pid in scope
        ],
    }
    (out / FILES["parcels"]).write_text(json.dumps(parcels, separators=(",", ":")) + "\n")
    (out / FILES["map_features"]).write_text(
        json.dumps(map_features(area), separators=(",", ":")) + "\n"
    )

    first = next(iter(analyses.values()))["versions"]
    bands = pd.Series([a["verdict"]["band"] for a in analyses.values()]).value_counts()
    manifest = {
        "area": area,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "uv run python -m navigator_pipeline.publish"
        + ("" if area == "Hazelwood" else f" --area '{area}'"),
        "versions": {k: first[k] for k in ("engine", "ruleset", "schema")},
        "counts": {
            "parcels": len(scope),
            "candidates": len(candidates),
            "golden_parcels": len(extra),
            "csv_rows": len(rows),
            "bands": {k: int(v) for k, v in bands.items()},
        },
        "data_as_of": data_as_of(),
        "files": {},
    }
    _write_readme(out, manifest)
    for name in [v for k, v in FILES.items() if k != "manifest"]:
        path = out / name
        manifest["files"][name] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
    (out / FILES["manifest"]).write_text(json.dumps(manifest, indent=2) + "\n")

    total = sum(p.stat().st_size for p in out.iterdir() if p.is_file())
    if total > MAX_BYTES:
        raise SystemExit(f"bundle is {total / 1e6:.1f} MB, over the {MAX_BYTES / 1e6:.0f} MB cap")
    return manifest | {"total_bytes": total}


def _write_readme(out: Path, m: dict) -> None:
    c = m["counts"]
    bands = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in c["bands"].items())
    text = f"""# Results bundle: {m["area"]}

Pre-computed screening results for **{c["parcels"]:,} parcels** in {m["area"]} (plus
{c["golden_parcels"]} golden test parcels). The API and the demo read these files; they do not
need the 1 GB data store. Generated {m["generated_at"][:10]} by engine {m["versions"]["engine"]},
rules `{m["versions"]["ruleset"]}`, contracts {m["versions"]["schema"]}.

**Regenerate** (needs the local data store; see pipeline/README.md):

```bash
{m["command"]}
```

Candidates are the {c["candidates"]:,} vacant lots (county land use "VACANT LAND", no
structure) plus the golden parcels. Engine picks: {bands}.

## Files

| File | What it holds |
|---|---|
| `summaries.json` | One summary per parcel (all {c["parcels"]:,}): the API's `ParcelSummary` shape. Non-candidates have no score. |
| `summaries.csv` | One row per candidate and building type ({c["csv_rows"]:,} rows). Columns below. |
| `site_analysis.jsonl.gz` | One line per candidate: `{{"parcel_id", "analysis": SiteAnalysis}}`, the engine's pick. |
| `site_context.jsonl.gz` | One line per candidate: `{{"parcel_id", "context": SiteContext}}`, the facts the engine used. Re-run the engine from these for other buildings or assumptions (about 10 ms each). |
| `parcels.geojson` | Parcel outlines, EPSG:4326, simplified by {SIMPLIFY_FT} ft, {DECIMALS} decimals. Properties: `parcel_id`, `block_lot`. |
| `map_features.geojson` | The neighbourhood outline, its parks and transit stops (`kind`, `name`). |
| `manifest.json` | Versions, counts, the as-of date of every data source, and a checksum per file. |

Load and validate everything in Python with `navigator_pipeline.bundle.load()`.

## summaries.csv columns

| Column | Meaning |
|---|---|
| `parcel_id`, `block_lot` | County ID (16 characters) and the city's dashed block-lot |
| `neighborhood`, `zoning_district` | City neighbourhood; the zoning district covering most of the lot |
| `lot_area_sqft`, `owner_type` | Lot area from the parcel map; owner type (private, city, land_bank, ura, other_public). No owner names |
| `assessed_value` | County assessed land value, USD (the default land price; not a market price) |
| `product`, `units` | Building type tested and its unit count (the largest the zoning rules allow, else the smallest tested) |
| `lead` | True for the building type the engine picks for this lot; that row repeats the numbers in site_analysis |
| `score_p10/p50/p90` | Score 0-100 (10th, 50th, 90th percentile of the simulation) |
| `band` | fast_track (75+), feasible_with_conditions (50-74), high_risk (<50), not_scored (zoning not covered) |
| `approval_prob_p10/p50/p90` | Chance the approvals are granted (1 when by right); variances and special exceptions from the Zoning Board model |
| `approval_basis` | Where those odds come from: by_right, model (Zoning Board decisions), measured (City Council votes), placeholder (no decision data yet), joined by `+` |
| `approval_path` | by_right; the approvals needed joined by `+` (e.g. `variance+subdivision`); not_allowed (the zoning rules rule it out); not_covered |
| `months_p10/p50/p90` | Months to permit-ready |
| `cost_premium_p10/p50/p90` | Extra site cost from constraints (slope, undermining, flood...), USD |
| `max_land_p10/p50/p90` | Most a developer could pay for the land at the target margin, USD; negative = costs exceed value |
| `top_flag`, `top_flag_severity` | The most severe constraint and its severity |
| `unknown_flags` | IDs of checks the data could not answer, `;`-separated. Unknown is never clean |
| `lon`, `lat` | Parcel centroid, EPSG:4326 |

Empty cells mean not applicable (no score for a building the rules rule out).

## Limits

- **Screening, not advice.** Costs, prices and approval odds for special exceptions and
  variances are placeholders until local benchmarks and zoning board decisions are available
  (the city's site blocks this client). Every assumption is listed in each analysis.
- **Snapshot.** Built from the stored copy of each source (dates in `manifest.json`); the live
  app refreshes fast-changing records (assessments, liens, permits, sales) per parcel.
- **No evidence file.** Zoning board decisions are not available, so there is no case evidence.
- **Personal data.** Owner type only. Addresses are property addresses from public records.
"""
    (out / FILES["readme"]).write_text(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="Hazelwood", help="city neighbourhood name")
    ap.add_argument("--out", type=Path, default=RESULTS)
    ap.add_argument("--no-golden", action="store_true", help="leave out the golden parcels")
    args = ap.parse_args()
    m = publish(args.area, args.out, golden=not args.no_golden)
    print(
        f"wrote {args.out}: {m['counts']['parcels']:,} parcels, "
        f"{m['counts']['candidates']:,} candidates, {m['total_bytes'] / 1e6:.1f} MB"
    )


if __name__ == "__main__":
    main()
