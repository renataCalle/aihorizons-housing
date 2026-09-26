"""Download raw data into <DATA_DIR>/raw/<key>/ with a provenance manifest.

    uv run python -m navigator_pipeline.fetch                 # everything not yet downloaded
    uv run python -m navigator_pipeline.fetch zoning parcels  # specific sources
    uv run python -m navigator_pipeline.fetch --wave 2        # one wave
    uv run python -m navigator_pipeline.fetch --force zoning  # re-download

Raw files are replaced only by a newer download; build clean tables with
navigator_pipeline.build. Routine updates go through navigator_pipeline.refresh.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from navigator_pipeline.catalog import ALLEGHENY_BBOX, SOURCES, WPRDC, Source
from navigator_pipeline.http import USER_AGENT, client
from navigator_pipeline.http import get_json as _get_json
from navigator_pipeline.http import post_json as _post_json
from navigator_pipeline.http import stream as _stream
from navigator_pipeline.settings import RAW

LEGISTAR = "https://webapi.legistar.com/v1/pittsburgh"
__all__ = ["USER_AGENT", "client", "fetch", "RAW", "SOURCES"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _wprdc_resource(http: httpx.Client, src: Source, latest: bool = False) -> tuple[dict, dict]:
    pkg = _get_json(http, f"{WPRDC}/api/3/action/package_show", {"id": src.dataset})["result"]
    resources = pkg["resources"]
    if src.resource_id:
        res = next(r for r in resources if r["id"] == src.resource_id)
    else:
        matches = [r for r in resources if (r.get("format") or "").upper() == src.fmt.upper()]
        if not matches:
            raise LookupError(f"{src.key}: no {src.fmt} resource in {src.dataset}")
        res = max(matches, key=lambda r: r.get("created") or "") if latest else matches[0]
    return pkg, res


def fetch_wprdc(http: httpx.Client, src: Source, out: Path, latest: bool = False) -> dict:
    pkg, res = _wprdc_resource(http, src, latest)
    url = res["url"]
    fmt = (res.get("format") or "bin").lower()
    ext = {"geojson": "geojson", "csv": "csv", "zip": "zip", "shp": "zip", "xlsx": "xlsx"}
    dest = out / f"{src.key}.{ext.get(fmt, fmt)}"
    _stream(http, url, dest)
    return {
        "url": url,
        "files": [dest.name],
        "source_as_of": res.get("last_modified") or pkg.get("metadata_modified"),
        "dataset_title": pkg["title"],
        "resource_name": res["name"],
    }


def _arcgis_layer(
    http: httpx.Client,
    url: str,
    where: str,
    bbox: bool = True,
    chunk: int = 500,
    params: dict | None = None,
) -> tuple[dict, list[dict]]:
    """All features of one layer inside the Allegheny bbox, as GeoJSON features (EPSG:4326).

    Uses the object-id pattern (ids first, then chunks), which works on servers without
    pagination support.
    """
    meta = _get_json(http, url, {"f": "json"})
    xmin, ymin, xmax, ymax = ALLEGHENY_BBOX
    spatial: dict = {"where": where}
    if bbox:
        spatial |= {
            "geometry": f"{xmin},{ymin},{xmax},{ymax}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }
    ids = _post_json(http, f"{url}/query", {**spatial, "returnIdsOnly": "true", "f": "json"})
    if "error" in ids:
        raise RuntimeError(f"{url}: {ids['error']}")
    object_ids = sorted(ids.get("objectIds") or [])
    chunk = min(int(meta.get("maxRecordCount") or 1000), chunk)
    features: list[dict] = []
    for i in range(0, len(object_ids), chunk):
        batch = _post_json(
            http,
            f"{url}/query",
            {
                "objectIds": ",".join(map(str, object_ids[i : i + chunk])),
                "outFields": "*",
                "outSR": 4326,
                "f": "geojson",
                **(params or {}),
            },
        )
        if "error" in batch:
            raise RuntimeError(f"{url}: {batch['error']}")
        features.extend(batch.get("features", []))
    return meta, features


def fetch_arcgis(http: httpx.Client, src: Source, out: Path) -> dict:
    """One layer, or a group's sublayers merged with a `_sublayer` property."""
    sublayers = src.extra.get("sublayers")
    urls = [f"{src.url}/{i}" for i in sublayers] if sublayers else [src.url]
    features: list[dict] = []
    edits: list[int] = []
    title = None
    for url in urls:
        meta, feats = _arcgis_layer(
            http,
            url,
            src.where,
            bbox=src.extra.get("bbox", True),
            chunk=src.extra.get("chunk", 500),
            params=src.extra.get("params"),
        )
        title = title or meta.get("name")
        if sublayers:
            for f in feats:
                f["properties"]["_sublayer"] = meta.get("name")
        features.extend(feats)
        if edit := (meta.get("editingInfo") or {}).get("lastEditDate"):
            edits.append(edit)
    dest = out / f"{src.key}.geojson"
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    as_of = datetime.fromtimestamp(max(edits) / 1000, UTC).isoformat() if edits else None
    return {
        "url": src.url,
        "files": [dest.name],
        "source_as_of": as_of,
        "dataset_title": title,
        "feature_count": len(features),
    }


def fetch_legistar(http: httpx.Client, src: Source, out: Path) -> dict:
    """All council matters whose title mentions zoning, plus each matter's history."""
    matters: list[dict] = []
    skip = 0
    while True:
        batch = _get_json(
            http,
            f"{LEGISTAR}/matters",
            {"$filter": "substringof('Zoning',MatterTitle)", "$top": 1000, "$skip": skip},
        )
        matters.extend(batch)
        if len(batch) < 1000:
            break
        skip += 1000
    for m in matters:
        m["histories"] = _get_json(http, f"{LEGISTAR}/matters/{m['MatterId']}/histories")
    dest = out / f"{src.key}.json"
    dest.write_text(json.dumps(matters))
    return {
        "url": f"{LEGISTAR}/matters",
        "files": [dest.name],
        "source_as_of": max(
            (m["MatterLastModifiedUtc"] for m in matters if m.get("MatterLastModifiedUtc")),
            default=None,
        ),
        "dataset_title": "Pittsburgh City Council legislation (Legistar)",
        "feature_count": len(matters),
    }


def fetch(src: Source, force: bool = False) -> dict | None:
    out = RAW / src.key
    manifest = out / "_manifest.json"
    if manifest.exists() and not force:
        return None
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with client() as http:
        match src.kind:
            case "wprdc":
                info = fetch_wprdc(http, src, out)
            case "wprdc_latest":
                info = fetch_wprdc(http, src, out, latest=True)
            case "arcgis":
                info = fetch_arcgis(http, src, out)
            case "legistar":
                info = fetch_legistar(http, src, out)
            case _:
                raise ValueError(src.kind)
    info |= {
        "key": src.key,
        "wave": src.wave,
        "feeds": src.feeds,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.time() - started, 1),
        "bytes": {f: (out / f).stat().st_size for f in info["files"]},
        "sha256": {f: _sha256(out / f) for f in info["files"]},
        "notes": src.notes,
    }
    manifest.write_text(json.dumps(info, indent=2))
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--wave", type=int)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    chosen = [
        s
        for s in SOURCES
        if (not args.keys or s.key in args.keys) and (args.wave is None or s.wave == args.wave)
    ]
    failed = []
    for src in chosen:
        try:
            info = fetch(src, args.force)
        except Exception as e:  # keep going; report at the end
            failed.append(src.key)
            print(f"FAIL {src.key}: {type(e).__name__}: {e}", flush=True)
            continue
        if info is None:
            print(f"skip {src.key} (already fetched)", flush=True)
        else:
            mb = sum(info["bytes"].values()) / 1e6
            print(f"ok   {src.key}: {mb:.1f} MB in {info['seconds']}s", flush=True)
    if failed:
        print(f"\n{len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
