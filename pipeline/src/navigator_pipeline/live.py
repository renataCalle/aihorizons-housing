"""Live per-parcel lookups at report time (the "hybrid" half of data freshness).

Map layers change rarely and come from the scheduled refresh. Records that change daily are
fetched live from the WPRDC datastore API for the parcels being analysed:

    assessment      use, structure, assessed values          (Allegheny County assessments)
    tax_liens       total of open liens                      (County tax lien summary)
    condemned       condemned / dead-end status              (City PLI)
    city_inventory  city-owned inventory status              (City of Pittsburgh)
    permits         building permits on the parcel           (City PLI)
    recent_sales    latest county sales, for new comps       (County sale transactions)

Every lookup is capped (TIMEOUT_S) and cached (CACHE_TTL_S). A failed lookup never breaks a
report: the stored copy is used and provenance records the fallback. WPRDC's SQL endpoint
blocks this client, so recent sales come from the plain search API sorted by date.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from navigator_pipeline.catalog import BY_KEY, WPRDC
from navigator_pipeline.http import client, get_json

TIMEOUT_S = 8.0
CACHE_TTL_S = 3_600
RECENT_SALES_LIMIT = 1_000  # about a month of county sales

# record -> (catalog source key, id field in the datastore)
PARCEL_RECORDS = {
    "assessment": ("assessments", "PARID"),
    "tax_liens": ("tax_liens", "pin"),
    "condemned": ("condemned", "parcel_id"),
    "city_inventory": ("city_owned", "pin"),
    "permits": ("pli_permits", "parcel_num"),
}
LABELS = {
    "assessment": "Allegheny County Property Assessments",
    "tax_liens": "Allegheny County Tax Liens",
    "condemned": "Condemned and Dead-End Properties",
    "city_inventory": "City-Owned Properties",
    "permits": "PLI Permits",
    "recent_sales": "Allegheny County Property Sale Transactions",
}

_cache: dict[tuple, tuple[float, object]] = {}
_lock = threading.Lock()


def _search_url() -> str:
    return f"{WPRDC}/api/3/action/datastore_search"


def _cached(key: tuple, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_S:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (now, value)
    return value


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _datastore(params: dict) -> list[dict]:
    with client(timeout=TIMEOUT_S, read=TIMEOUT_S) as http:
        body = get_json(http, _search_url(), params, tries=1)
    if not body.get("success"):
        raise RuntimeError(f"datastore error: {body.get('error')}")
    return body["result"]["records"]


def parcel_records(record: str, parcel_id: str) -> list[dict]:
    key, field = PARCEL_RECORDS[record]
    rid = BY_KEY[key].resource_id
    return _cached(
        (record, parcel_id),
        lambda: _datastore(
            {"resource_id": rid, "filters": f'{{"{field}":"{parcel_id}"}}', "limit": 100}
        ),
    )


def recent_sales() -> list[dict]:
    rid = BY_KEY["sales"].resource_id
    return _cached(
        ("recent_sales",),
        lambda: _datastore(
            {
                "resource_id": rid,
                "sort": "SALEDATE desc",
                "limit": RECENT_SALES_LIMIT,
                "fields": "PARID,SALEDATE,RECORDDATE,PRICE,SALECODE",
            }
        ),
    )


def fetch_all(parcel_ids: list[str]) -> dict[str, dict]:
    """All live records for these parcels, in parallel.

    Returns {record: {"ok": bool, "at": iso time, "data": {parcel_id: [rows]} | [rows],
    "error": str | None}}.
    """
    jobs = {(r, pid): (parcel_records, r, pid) for r in PARCEL_RECORDS for pid in parcel_ids}
    jobs[("recent_sales", None)] = (recent_sales,)
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        futures = {k: pool.submit(fn, *args) for k, (fn, *args) in jobs.items()}
        for (record, pid), fut in futures.items():
            at = datetime.now(UTC).isoformat(timespec="seconds")
            slot = results.setdefault(record, {"ok": True, "at": at, "data": {}, "error": None})
            try:
                rows = fut.result(timeout=TIMEOUT_S * 2)
                if pid is None:
                    slot["data"] = rows
                else:
                    slot["data"][pid] = rows
            except Exception as exc:
                slot["ok"] = False
                slot["error"] = f"{type(exc).__name__}"
    return results


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def assessment_fields(row: dict) -> dict:
    """Map one assessment record to SiteContext parcel fields (owner type set by caller)."""
    return {
        "current_use": row.get("USEDESC"),
        "has_structure": _num(row.get("FAIRMARKETBUILDING")) > 0
        or _num(row.get("FINISHEDLIVINGAREA")) > 0,
        "assessed_land": _num(row.get("FAIRMARKETLAND")) or None,
        "assessed_total": _num(row.get("FAIRMARKETTOTAL")) or None,
        "municode": int(_num(row.get("MUNICODE"))) or None,
    }


def permit_rows(rows: list[dict], limit: int = 20) -> list[dict]:
    out = [
        {
            "permit_id": str(r.get("permit_id")),
            "permit_type": r.get("permit_type"),
            "work_type": r.get("work_type"),
            "issue_date": (str(r["issue_date"])[:10] if r.get("issue_date") else None),
            "status": r.get("status"),
        }
        for r in rows
    ]
    return sorted(out, key=lambda p: p["issue_date"] or "", reverse=True)[:limit]
