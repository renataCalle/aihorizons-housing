"""Run the Navigator v0 on any Allegheny County parcel.

    uv run python -m sandbox.navigator 4-A-303
    uv run python -m sandbox.navigator 0052H00093000000
    uv run python -m sandbox.navigator "5607 ELMER ST"
    uv run python -m sandbox.navigator 4-A-303 --set hard_cost_psf=275 --land-price 40000

Prints the report in decision order (spec: Report blocks) and writes the full
SiteAnalysis-shaped JSON to sandbox/data/output/<parcel_id>.json.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from sandbox import site_context
from sandbox.engine_v0.analyze import analyze
from sandbox.report import render

DATA = Path(__file__).parent / "data"
FEAT = DATA / "features"
OUT = DATA / "output"


def resolve(query: str) -> str:
    """County id, dashed block-lot, or street address -> county parcel id."""
    q = query.strip().upper()
    p = pd.read_parquet(
        DATA / "clean" / "parcels.parquet",
        columns=["parcel_id", "block_lot", "address", "municipality"],
    )
    hit = p[(p["parcel_id"] == q) | (p["block_lot"].str.upper() == q)]
    if len(hit) == 0:
        hit = p[p["address"].fillna("").str.upper() == q]
    if len(hit) == 0:
        hit = p[p["address"].fillna("").str.upper().str.contains(q, regex=False)]
    if len(hit) == 1:
        return hit["parcel_id"].iloc[0]
    if len(hit) == 0:
        sys.exit(
            f"No parcel matches {query!r}. Try the county id (16 characters) or a "
            "block-lot like 4-A-303."
        )
    print(f"{len(hit)} parcels match {query!r}; showing up to 10:")
    print(hit.head(10).to_string(index=False))
    sys.exit("Re-run with one parcel id or block-lot from the list.")


def ensure_facts(pid: str) -> None:
    for f in FEAT.glob("parcel_facts*.parquet"):
        if pid in set(pd.read_parquet(f, columns=["parcel_id"])["parcel_id"]):
            return
    print(f"computing facts for {pid} (not in the city table)...", file=sys.stderr)
    subprocess.run(
        [
            sys.executable,
            "-W",
            "ignore",
            "-m",
            "sandbox.features",
            "--ids",
            pid,
            "--tag",
            f"adhoc_{pid}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def _money(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def _rng(r: dict, fmt) -> str:
    return f"{fmt(r['p10'])} / {fmt(r['p50'])} / {fmt(r['p90'])}"


def report(ctx: dict, a: dict) -> None:
    p = ctx["parcels"][0]
    z = (
        ", ".join(f"{d['code']} {d['share']:.0%}" for d in ctx["zoning"] if d["kind"] == "district")
        or "not covered"
    )
    v = a["verdict"]
    print("=" * 78)
    print(f"{p['address']} · {p['block_lot']} · {p['municipality']}")
    print(
        f"Lot {p['lot_area_sqft']:,.0f} sf · zoning {z} · {p['current_use']} · "
        f"owner: {p['owner_type']}"
    )
    print("-" * 78)
    score = "—" if v["score"] is None else v["score"]
    print(f"SCORE {score}  [{v['band'].replace('_', ' ').upper()}]  {v['headline']}")
    m = a["metrics"]
    if m:
        print(f"\nKey numbers (p10 / p50 / p90), option: {m['option'].replace('_', ' ')}")
        print(f"  months to permit-ready  {_rng(m['months_to_permit'], lambda x: f'{x:.1f}')}")
        print(f"  approval odds           {_rng(m['approval_prob'], lambda x: f'{x:.0%}')}")
        print(
            f"  max land price          {_rng(m['max_land_price'], _money)}  vs "
            f"{_money(m['land_basis']['value'])} ({m['land_basis']['source']})"
        )
    print("\nRed flags")
    for f in a["flags"]:
        cost = (
            ""
            if not f["cost_usd"]
            else f"  cost {_money(f['cost_usd'][0])}-{_money(f['cost_usd'][1])}"
        )
        mo = "" if not f["months"] else f"  +{f['months'][0]:g}-{f['months'][1]:g} mo"
        sec = next((e["code_section"] for e in f["evidence"] if e.get("code_section")), None)
        src = f"  [{sec}]" if sec else ""
        print(f"  {f['severity'].upper():8s} {f['title']}{cost}{mo}{src}")
    if not a["flags"]:
        print("  none")
    print(f"\nCleared: {', '.join(a['cleared']) or 'none'}")
    print(f"\nWhat you can build ({a['rules']['scenario']} setbacks)")
    for o in a["options"]:
        rel = "; ".join(o["relief"]) or "no relief"
        print(
            f"  {o['label'].replace('_', ' '):12s} {o['units']} x {o['product_type']:14s} "
            f"margin {_rng(o['margin'], lambda x: f'{x:.0%}')} · score p50 "
            f"{o['score']['p50']:.0f} · {rel}"
        )
        print(f"  {'':12s} revenue: {o['revenue_basis']}")
    print("\nNext steps")
    for s in a["next_steps"]:
        c = (
            "free"
            if s["cost_usd"][1] == 0
            else f"{_money(s['cost_usd'][0])}-{_money(s['cost_usd'][1])}"
        )
        print(f"  {s['order']}. {s['action']} ({s['who']}, {c})")
    if a["score_breakdown"]:
        print("\nWhere the points went")
        for b in a["score_breakdown"]:
            print(f"  -{b['points_lost']:>5} {b['component']:8s} {b['driver_flag_id']}")
    ph = [x["key"] for x in a["assumptions"] if "PLACEHOLDER" in x["source"]]
    print(f"\nPlaceholder assumptions ({len(ph)}): {', '.join(ph)}")
    print("Screening estimate only; not a zoning determination, legal or engineering advice.")
    print("=" * 78)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="county parcel id, block-lot (4-A-303), or address")
    ap.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override an assumption, e.g. hard_cost_psf=275",
    )
    ap.add_argument("--land-price", type=float, help="asking price (default: assessed land)")
    args = ap.parse_args()
    overrides = {k: float(v) for k, v in (s.split("=", 1) for s in args.set)}
    pid = resolve(args.query)
    ensure_facts(pid)
    ctx = site_context.build([pid])
    if args.land_price is not None:
        overrides["land_price"] = args.land_price
    result = analyze(ctx, overrides)
    report(ctx, result)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{pid}.json"
    path.write_text(
        json.dumps(
            {"input": args.query, "site_context": ctx, "site_analysis": result},
            indent=2,
            default=str,
        )
        + "\n"
    )
    payload = json.loads(path.read_text())
    html_path = path.with_suffix(".html")
    html_path.write_text(render(payload))
    print(f"full JSON: {path}")
    print(f"report:    {html_path}")


if __name__ == "__main__":
    main()
