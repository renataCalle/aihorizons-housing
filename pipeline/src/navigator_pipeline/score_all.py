"""Score every city parcel once and store the results, so a lookup never re-runs the engine.

    uv run python -m navigator_pipeline.score_all                  # every city parcel
    uv run python -m navigator_pipeline.score_all --workers 8
    uv run python -m navigator_pipeline.score_all --resume         # continue an interrupted run
    uv run python -m navigator_pipeline.score_all --ids 0055A00225000000 --out /tmp/scores

For each parcel: SiteContext from the stored copy (no live lookups, so the run is reproducible
and sends no traffic to the sources), the engine's SiteAnalysis (the same `analyze` the API
calls), and one row per building type. Parcels that cannot be scored (no assessment record) are
kept with the reason. Output, read with `navigator_pipeline.scores` or any DuckDB client:

    parcels.parquet    one row per parcel: facts, score, band, key ranges, status
    programs.parquet   one row per parcel and building type (results/README.md columns)
    analyses.parquet   parcel_id, analysis (SiteAnalysis JSON)
    contexts.parquet   parcel_id, context (SiteContext JSON), to re-run the engine
    manifest.json      versions, data dates, counts, run time

Files are sorted by parcel_id in small row groups, so a lookup by ID reads a few MB.
"""

import argparse
import json
import multiprocessing as mp
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import shape

from navigator_contracts import SiteAnalysis, SiteContext
from navigator_engine import analyze
from navigator_engine.rules_engine import TEMPLATES
from navigator_pipeline import site_context
from navigator_pipeline.bundle import CSV_COLUMNS
from navigator_pipeline.publish import (
    DECIMALS,
    TO_4326,
    approval_path,
    csv_row,
    data_as_of,
    lead_option,
)
from navigator_pipeline.settings import SCORES

CHUNK = 1_000
ROW_GROUP = 1_024  # rows per Parquet row group: a lookup by ID decompresses one group
TABLES = ("parcels", "programs", "analyses", "contexts")

PARCEL_COLUMNS = [
    "parcel_id",
    "block_lot",
    "address",
    "municipality",
    "neighborhood",
    "zoning",
    "zoning_district",
    "lot_area_sqft",
    "current_use",
    "has_structure",
    "vacant",
    "owner_type",
    "assessed_land",
    "assessed_total",
    "land_price",
    "land_price_source",
    "status",
    "error",
    "score",
    "score_p10",
    "score_p50",
    "score_p90",
    "band",
    "headline",
    "lead_product",
    "lead_units",
    "approval_path",
    "approval_prob_p50",
    "months_p10",
    "months_p50",
    "months_p90",
    "cost_premium_p10",
    "cost_premium_p50",
    "cost_premium_p90",
    "max_land_p10",
    "max_land_p50",
    "max_land_p90",
    "top_flag",
    "top_flag_severity",
    "high_flags",
    "unknown_flags",
    "data_as_of",
    "lon",
    "lat",
]


def _r(rng: dict | None, key: str, digits: int = 0):
    if not rng or rng.get(key) is None:
        return None
    return round(float(rng[key]), digits) if digits else round(float(rng[key]))


def centroid(ctx: dict) -> tuple[float, float]:
    c = shape(ctx["parcels"][0]["geometry"]).centroid
    lon, lat = TO_4326.transform(c.x, c.y)
    return round(lon, DECIMALS), round(lat, DECIMALS)


def parcel_row(ctx: dict, a: dict, lonlat: tuple[float, float]) -> dict:
    p = ctx["parcels"][0]
    districts = sorted(
        (z for z in ctx["zoning"] if z["kind"] == "district"), key=lambda z: -z["share"]
    )
    opt, m, v = lead_option(a) or {}, a["metrics"] or {}, a["verdict"]
    top = a["flags"][0] if a["flags"] else None
    land = m.get("land_basis") or {}
    return {
        "parcel_id": p["parcel_id"],
        "block_lot": p["block_lot"],
        "address": p["address"],
        "municipality": p["municipality"],
        "neighborhood": ctx["area"]["neighborhood"],
        "zoning": ",".join(z["code"] for z in districts),
        "zoning_district": districts[0]["code"] if districts else None,
        "lot_area_sqft": round(p["lot_area_sqft"]),
        "current_use": p["current_use"],
        "has_structure": p["has_structure"],
        "vacant": p["current_use"] == "VACANT LAND" and not p["has_structure"],
        "owner_type": p["owner_type"],
        "assessed_land": p["assessed_land"],
        "assessed_total": p["assessed_total"],
        "land_price": land.get("value"),
        "land_price_source": land.get("source"),
        "status": "scored" if v["band"] != "not_scored" else "not_scored",
        "error": None,
        "score": v["score"],
        "score_p10": _r(v["score_range"], "p10", 1),
        "score_p50": _r(v["score_range"], "p50", 1),
        "score_p90": _r(v["score_range"], "p90", 1),
        "band": v["band"],
        "headline": v["headline"],
        "lead_product": opt.get("product_type"),
        "lead_units": opt.get("units"),
        "approval_path": approval_path(a, opt or None),
        "approval_prob_p50": _r(m.get("approval_prob"), "p50", 3),
        "months_p10": _r(m.get("months_to_permit"), "p10", 1),
        "months_p50": _r(m.get("months_to_permit"), "p50", 1),
        "months_p90": _r(m.get("months_to_permit"), "p90", 1),
        "cost_premium_p10": _r(opt.get("site_cost_premium"), "p10"),
        "cost_premium_p50": _r(opt.get("site_cost_premium"), "p50"),
        "cost_premium_p90": _r(opt.get("site_cost_premium"), "p90"),
        "max_land_p10": _r(m.get("max_land_price"), "p10"),
        "max_land_p50": _r(m.get("max_land_price"), "p50"),
        "max_land_p90": _r(m.get("max_land_price"), "p90"),
        "top_flag": top["title"] if top else None,
        "top_flag_severity": top["severity"] if top else None,
        "high_flags": sum(f["severity"] == "high" for f in a["flags"]),
        "unknown_flags": ";".join(f["id"] for f in a["flags"] if f["severity"] == "unknown"),
        "data_as_of": a["versions"]["data_as_of"],
        "lon": lonlat[0],
        "lat": lonlat[1],
    }


NO_COMPS = (
    "not priced: fewer than 5 usable comparable sales within 0.5 mi in 3 years, "
    "so the engine cannot estimate sale value"
)


class NotPriced(ValueError):
    """The engine returned NaN ranges (not valid JSON); the reason says why."""


def _strict_json(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), allow_nan=False)


def score_context(ctx: dict) -> dict:
    """Everything stored for one parcel, from its SiteContext alone (no data store needed)."""
    ctx = json.loads(SiteContext.model_validate(ctx).model_dump_json(by_alias=True))
    a = analyze(ctx)
    SiteAnalysis.model_validate(a)
    try:
        analysis_json = _strict_json(a)
    except ValueError:
        unpriced = any(o["revenue_basis"] == "no usable comps" for o in a["options"])
        raise NotPriced(NO_COMPS if unpriced else "engine returned NaN values") from None
    lonlat = centroid(ctx)
    lead = (lead_option(a) or {}).get("product_type")
    programs = [
        csv_row(
            ctx,
            a if product == lead else analyze(ctx, program={"product_type": product}),
            product,
            product == lead,
            lonlat,
        )
        for product in TEMPLATES
    ]
    pid = ctx["parcels"][0]["parcel_id"]
    return {
        "parcels": parcel_row(ctx, a, lonlat),
        "programs": programs,
        "analyses": {"parcel_id": pid, "analysis": analysis_json},
        "contexts": {"parcel_id": pid, "context": _strict_json(ctx)},
    }


def failed_row(pid: str, facts: pd.Series, error: str) -> dict:
    row = dict.fromkeys(PARCEL_COLUMNS)
    clean = lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else v  # noqa: E731
    row.update(
        parcel_id=pid,
        block_lot=clean(facts.get("block_lot")),
        address=clean(facts.get("address")),
        municipality=clean(facts.get("municipality")),
        neighborhood=clean(facts.get("neighborhood")),
        lot_area_sqft=round(float(facts.get("lot_area_sqft_gis") or 0)),
        current_use=clean(facts.get("current_use")),
        owner_type=clean(facts.get("owner_type")),
        status="error",
        error=error,
    )
    return row


# ---------------------------------------------------------------- batch

BOOL = {"has_structure", "vacant", "lead"}
FLOAT = {"assessed_land", "assessed_total", "land_price", "lon", "lat"}
FLOAT |= {f"approval_prob_{q}" for q in ("p10", "p50", "p90")}
FLOAT |= {f"{k}_{q}" for k in ("score", "months") for q in ("p10", "p50", "p90")}
INT = {"lot_area_sqft", "assessed_value", "score", "units", "lead_units", "high_flags"}
INT |= {f"{k}_{q}" for k in ("cost_premium", "max_land") for q in ("p10", "p50", "p90")}


def _type(column: str) -> pa.DataType:
    if column in BOOL:
        return pa.bool_()
    if column in FLOAT:
        return pa.float64()
    return pa.int64() if column in INT else pa.string()


def _schema(columns: list[str]) -> pa.Schema:
    return pa.schema([(c, _type(c)) for c in columns])


SCHEMAS = {
    "parcels": _schema(PARCEL_COLUMNS),
    "programs": _schema(CSV_COLUMNS),
    "analyses": pa.schema([("parcel_id", pa.string()), ("analysis", pa.string())]),
    "contexts": pa.schema([("parcel_id", pa.string()), ("context", pa.string())]),
}


def write_part(rows: dict[str, list[dict]], parts: Path, n: int) -> None:
    for table in TABLES:
        t = pa.Table.from_pylist(rows[table], schema=SCHEMAS[table])
        pq.write_table(t, parts / f"{table}-{n:05d}.parquet", compression="zstd")
    (parts / f"done-{n:05d}").touch()


def score_chunk(job: tuple[int, list[str], str]) -> tuple[int, int, int]:
    n, ids, parts = job
    facts = site_context.store()["facts"]
    rows: dict[str, list] = {t: [] for t in TABLES}
    errors = 0
    for pid in ids:
        try:
            r = score_context(site_context.build([pid], live=False))
            rows["parcels"].append(r["parcels"])
            rows["programs"].extend(r["programs"])
            rows["analyses"].append(r["analyses"])
            rows["contexts"].append(r["contexts"])
        except Exception as exc:  # keep the parcel, with the reason, and carry on
            errors += 1
            reason = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
            if isinstance(exc, NotPriced):
                reason = str(exc)
            elif not bool(facts.loc[pid, "has_assessment"]):
                reason = "no county assessment record (use, address and values unknown)"
            rows["parcels"].append(failed_row(pid, facts.loc[pid], reason))
    write_part(rows, Path(parts), n)
    return n, len(ids), errors


MERGE_MEMORY = "3GB"  # DuckDB spills to disk beyond this


def merge(parts: Path, out: Path) -> None:
    """Stitch each table's parts into one zstd Parquet file with small row groups.

    Chunks are consecutive runs of sorted parcel IDs, so reading the parts in chunk order
    already yields parcel_id order: no sort, and memory stays flat however big the table is.
    """
    tmp = parts / "_duckdb_tmp"
    con = duckdb.connect(
        config={
            "memory_limit": MERGE_MEMORY,
            "temp_directory": tmp.as_posix(),
            "preserve_insertion_order": True,
        }
    )
    for table in TABLES:
        files = sorted(parts.glob(f"{table}-*.parquet"))  # zero-padded chunk numbers
        src = "[" + ", ".join(f"'{f.as_posix()}'" for f in files) + "]"
        dst = out / f"{table}.parquet"
        con.execute(
            f"COPY (SELECT * FROM read_parquet({src})) TO '{dst.as_posix()}' "
            f"(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE {ROW_GROUP})"
        )
        _check_sorted(con, dst)
    con.close()
    shutil.rmtree(tmp, ignore_errors=True)


def _check_sorted(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    """Row groups must cover increasing parcel_id ranges, or lookups can't skip them."""
    stats = con.execute(
        "SELECT stats_min_value, stats_max_value FROM parquet_metadata(?) "
        "WHERE path_in_schema = 'parcel_id' ORDER BY row_group_id",
        [path.as_posix()],
    ).fetchall()
    for (_, prev_max), (next_min, _) in zip(stats, stats[1:], strict=False):
        if next_min < prev_max:
            raise RuntimeError(f"{path.name} is not in parcel_id order ({next_min} < {prev_max})")


def run(
    ids: list[str], out: Path, workers: int, resume: bool = False, keep_parts: bool = False
) -> dict:
    t0 = time.time()
    out.mkdir(parents=True, exist_ok=True)
    parts = out / "_parts"
    if parts.exists() and not resume:
        shutil.rmtree(parts)
    parts.mkdir(exist_ok=True)
    chunks = [(i, ids[j : j + CHUNK], str(parts)) for i, j in enumerate(range(0, len(ids), CHUNK))]
    todo = [c for c in chunks if not (parts / f"done-{c[0]:05d}").exists()]
    print(f"{len(ids):,} parcels in {len(chunks)} chunks; {len(todo)} to do, {workers} workers")

    done, errors = len(ids) - sum(len(c[1]) for c in todo), 0
    if todo:
        site_context.store()  # load once; forked workers share it
        parallel = workers > 1 and len(todo) > 1
        pool = mp.get_context("fork").Pool(workers) if parallel else None
        results = pool.imap_unordered(score_chunk, todo) if pool else map(score_chunk, todo)
        for _, n, e in results:
            done, errors = done + n, errors + e
            rate = done / max(time.time() - t0, 1e-9)
            print(f"  {done:,}/{len(ids):,} ({errors} errors) · {rate:,.0f}/s", flush=True)
        if pool:
            pool.close()
            pool.join()

    print("merging parts ...", flush=True)
    merge(parts, out)
    con = duckdb.connect()
    parcels = (out / "parcels.parquet").as_posix()
    counts = dict(con.execute(f"SELECT status, count(*) FROM '{parcels}' GROUP BY 1").fetchall())
    bands = dict(con.execute(f"SELECT band, count(*) FROM '{parcels}' GROUP BY 1").fetchall())
    versions = con.execute(
        f"SELECT analysis FROM '{(out / 'analyses.parquet').as_posix()}' LIMIT 1"
    ).fetchone()
    con.close()
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "uv run python -m navigator_pipeline.score_all",
        "scope": "City of Pittsburgh parcels" if len(ids) > CHUNK else f"{len(ids)} parcels",
        "live_lookups": False,
        "versions": json.loads(versions[0])["versions"] if versions else None,
        "counts": {"parcels": len(ids), "by_status": counts, "by_band": bands},
        "data_as_of": data_as_of(),
        "run_seconds": round(time.time() - t0),
        "files": {f"{t}.parquet": (out / f"{t}.parquet").stat().st_size for t in TABLES},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    if not keep_parts:
        shutil.rmtree(parts)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", help="only these parcels (default: every city parcel)")
    ap.add_argument("--out", type=Path, default=SCORES)
    ap.add_argument("--workers", type=int, default=max(1, min(10, mp.cpu_count() - 2)))
    ap.add_argument("--resume", action="store_true", help="keep finished chunks of a prior run")
    ap.add_argument("--keep-parts", action="store_true")
    args = ap.parse_args()
    facts = site_context.store()["facts"]
    if args.ids:
        ids = site_context.resolve_ids(args.ids, facts)
    else:
        ids = sorted(facts.index[facts["in_pittsburgh"].astype(bool)])
    m = run(sorted(set(ids)), args.out, args.workers, args.resume, args.keep_parts)
    size = sum(m["files"].values()) / 1e6
    print(f"wrote {args.out}: {m['counts']['by_status']} · {size:,.0f} MB · {m['run_seconds']:,} s")


if __name__ == "__main__":
    main()
