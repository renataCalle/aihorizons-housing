"""Scheduled refresh: re-pull sources from their live APIs when they have new data.

    uv run python -m navigator_pipeline.refresh              # everything that is due
    uv run python -m navigator_pipeline.refresh --dry-run    # show what would happen
    uv run python -m navigator_pipeline.refresh --force sales pli_permits
    uv run python -m navigator_pipeline.refresh --no-features

Run it nightly from cron; the exact line is in pipeline/README.md.

For each source past its cadence (catalog.REFRESH_DAYS), the source is asked when it last
changed. Unchanged -> only `checked_at` is recorded. Changed -> re-download (the previous copy
is kept in `_previous/` and restored if the download fails), rebuild the clean tables that
depend on it, and recompute per-parcel facts if any of their inputs changed.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime

from navigator_pipeline import build, fetch
from navigator_pipeline.catalog import BY_KEY, SOURCES, Source, refresh_days
from navigator_pipeline.http import client, get_json
from navigator_pipeline.settings import DATA_DIR, FEATURES, RAW

LOG = DATA_DIR / "refresh_log.jsonl"

# Clean tables that the per-parcel facts are computed from (features.py reads these).
FEATURE_INPUTS = {
    "parcels",
    "neighborhoods",
    "zoning",
    "historic_districts",
    "greenways",
    "parks",
    "height_overlay",
    "parking_reduction_overlay",
    "riverfront_overlay",
    "uptown_ipod",
    "steep_slope",
    "landslide_prone",
    "undermined",
    "landslides_observed",
    "fema_flood_zones",
    "dep_aml",
    "dep_digitized_mined_area",
    "dep_land_recycling",
    "dep_storage_tanks",
    "combined_sewershed",
    "water_providers",
    "street_centerlines",
    "city_steps",
    "transit_stops",
    "market_value_analysis",
    "hud_safmr",
    "hud_qct",
    "hud_dda",
    "opportunity_zones",
    "city_owned",
    "tax_liens",
    "condemned",
    "pli_permits",
}


# ---------------------------------------------------------------- decisions (pure)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def is_due(manifest: dict | None, days: int, now: datetime) -> bool:
    """Due when never fetched, or when the last check is older than the cadence."""
    if manifest is None:
        return True
    last = _parse(manifest.get("checked_at") or manifest.get("fetched_at"))
    return last is None or (now - last).total_seconds() >= days * 86_400


def has_changed(manifest: dict | None, remote_as_of: str | None) -> bool:
    """Changed when there is no manifest, the source can't say, or its date moved."""
    if manifest is None or remote_as_of is None:
        return True
    return str(manifest.get("source_as_of")) != str(remote_as_of)


def tables_for(keys: set[str]) -> list[str]:
    """Clean tables to rebuild when these raw sources change, in build order."""
    out = []
    for name in build.BUILDERS:
        if set(build.DEPENDS.get(name, [name])) & keys:
            out.append(name)
    return out


# ---------------------------------------------------------------- source metadata


def remote_as_of(src: Source) -> str | None:
    """Ask the source when its data last changed (without downloading it)."""
    with client(timeout=30, read=60) as http:
        if src.kind in ("wprdc", "wprdc_latest"):
            pkg, res = fetch._wprdc_resource(http, src, latest=src.kind == "wprdc_latest")
            return res.get("last_modified") or pkg.get("metadata_modified")
        if src.kind == "arcgis":
            layers = (
                [f"{src.url}/{i}" for i in src.extra["sublayers"]]
                if src.extra.get("sublayers")
                else [src.url]
            )
            edits = [
                (get_json(http, u, {"f": "json"}).get("editingInfo") or {}).get("lastEditDate")
                for u in layers
            ]
            edits = [e for e in edits if e]
            return datetime.fromtimestamp(max(edits) / 1000, UTC).isoformat() if edits else None
        if src.kind == "legistar":
            top = get_json(
                http,
                f"{fetch.LEGISTAR}/matters",
                {
                    "$filter": "substringof('Zoning',MatterTitle)",
                    "$orderby": "MatterLastModifiedUtc desc",
                    "$top": 1,
                },
            )
            return top[0].get("MatterLastModifiedUtc") if top else None
    return None


def _manifest(key: str) -> dict | None:
    path = RAW / key / "_manifest.json"
    return json.loads(path.read_text()) if path.exists() else None


def _touch_checked(key: str, now: datetime) -> None:
    path = RAW / key / "_manifest.json"
    m = json.loads(path.read_text())
    m["checked_at"] = now.isoformat(timespec="seconds")
    path.write_text(json.dumps(m, indent=2))


def _refetch(src: Source) -> dict:
    """Re-download, keeping the previous copy until the new one is complete."""
    folder = RAW / src.key
    prev = folder / "_previous"
    if folder.exists():
        shutil.rmtree(prev, ignore_errors=True)
        prev.mkdir(parents=True)
        for f in folder.iterdir():
            if f.name != "_previous":
                shutil.move(str(f), prev / f.name)
    try:
        info = fetch.fetch(src, force=True)
    except Exception:
        for f in prev.iterdir():  # restore the previous copy
            shutil.move(str(f), folder / f.name)
        raise
    return info


def _ensure_raw(key: str) -> None:
    """Download a source's raw files if only its manifest is present (fresh clone)."""
    folder = RAW / key
    have = [f for f in folder.glob("*") if f.is_file() and not f.name.startswith("_")]
    if not have:
        print(f"  fetching missing raw input: {key}", flush=True)
        fetch.fetch(BY_KEY[key], force=True)


# ---------------------------------------------------------------- run


def run(keys: list[str] | None, force: set[str], dry_run: bool, features: bool) -> int:
    now = datetime.now(UTC)
    changed: set[str] = set()
    failures = 0
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for src in SOURCES:
        if keys and src.key not in keys:
            continue
        t0 = time.time()
        m = _manifest(src.key)
        entry = {
            "at": now.isoformat(timespec="seconds"),
            "source": src.key,
            "old_as_of": (m or {}).get("source_as_of"),
        }
        try:
            if src.key not in force and not is_due(m, refresh_days(src.key), now):
                entry["status"] = "fresh"
            else:
                remote = None if src.key in force else remote_as_of(src)
                entry["new_as_of"] = remote
                if src.key not in force and not has_changed(m, remote):
                    entry["status"] = "unchanged"
                    if not dry_run:
                        _touch_checked(src.key, now)
                elif dry_run:
                    entry["status"] = "would_update"
                else:
                    info = _refetch(src)
                    entry["status"] = "updated"
                    entry["new_as_of"] = info.get("source_as_of")
                    changed.add(src.key)
        except Exception as exc:  # keep going; the stored copy stays in place
            failures += 1
            entry["status"] = "failed"
            entry["error"] = f"{type(exc).__name__}: {exc}"[:300]
        entry["seconds"] = round(time.time() - t0, 1)
        print(f"{entry['status']:>13}  {src.key}", flush=True)
        if not dry_run:
            with LOG.open("a") as f:
                f.write(json.dumps(entry) + "\n")

    tables = tables_for(changed)
    if tables and not dry_run:
        print(f"rebuilding clean tables: {', '.join(tables)}", flush=True)
        for name in tables:
            for dep in build.DEPENDS.get(name, [name]):
                _ensure_raw(dep)  # a fresh clone has manifests but no raw files
            build.write(build.BUILDERS[name](), name)
    if features and not dry_run and set(tables) & FEATURE_INPUTS:
        print("recomputing per-parcel facts (city)", flush=True)
        core = {"parcel_facts", "parcel_zoning", "parcel_flood", "parcel_env_nearby"}
        for f in FEATURES.glob("parcel_*.parquet"):  # --ids subsets recompute on demand
            if f.stem not in core:
                f.unlink()
        subprocess.run(
            [sys.executable, "-W", "ignore", "-m", "navigator_pipeline.features"], check=True
        )
    return failures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*", help="limit to these sources")
    ap.add_argument("--force", nargs="+", default=[], help="re-download even if unchanged")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-features", action="store_true")
    args = ap.parse_args()
    keys = (args.keys or []) + args.force or None
    failures = run(keys, set(args.force), args.dry_run, not args.no_features)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
