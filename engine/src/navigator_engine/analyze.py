"""Engine v0 end to end: SiteContext -> SiteAnalysis-shaped dict.

    rules engine -> constraint flags -> entitlement samples -> pro forma Monte Carlo
    -> score (with counterfactual breakdown) -> next steps by cost-to-kill

Pure: reads only the context, the rules tables in config/, and the assumptions module. Every
number that is not derived from the context is listed in `assumptions` with its source.
"""

import math

import numpy as np

from navigator_engine import constraints, entitlement
from navigator_engine.assumptions import resolve
from navigator_engine.rules_engine import NOT_CHECKED, TEMPLATES, site_checks
from navigator_engine.rules_engine import analyze as rules_analyze

N = 2_000
ENGINE_VERSION = "0.1.0"
RESIDENTIAL = {"RESIDENTIAL"}


def _range(x: np.ndarray) -> dict:
    q = np.nanpercentile(x, [10, 50, 90])
    return {"p10": float(q[0]), "p50": float(q[1]), "p90": float(q[2])}


def _tri(a, rng, n=N):
    return np.full(n, a.value) if a.low == a.high else rng.triangular(a.low, a.value, a.high, n)


# ---------------------------------------------------------------- market inputs


NEW_BUILD_YEAR = 2010
MIN_COMPS = 5


def sale_psf(ctx: dict) -> tuple[np.ndarray | None, dict]:
    """$/sf from arm's-length residential comps with a known building size (facts).

    Recent construction (built 2010+) is used directly when there are enough sales; otherwise
    resale comps are used and the new-build premium assumption is applied.
    """
    rows = [
        s
        for s in ctx["market"]["sales"]
        if s.get("building_sqft")
        and s["building_sqft"] >= 500
        and s["price"] >= 30_000
        and (s.get("property_class") in RESIDENTIAL)
    ]
    new = [s for s in rows if (s.get("year_built") or 0) >= NEW_BUILD_YEAR]
    use, kind = (new, "new-build") if len(new) >= MIN_COMPS else (rows, "resale")
    if len(use) < MIN_COMPS:
        return None, {"n": len(use), "kind": kind}
    psf = np.array([s["price"] / s["building_sqft"] for s in use])
    q = np.percentile(psf, [25, 50, 75])
    return q, {"n": len(use), "kind": kind}


def rent_for(ctx: dict, unit_sqft: float) -> float | None:
    beds = 2 if unit_sqft >= 900 else 1
    for r in ctx["market"]["rent_benchmarks"]:
        if r["bedrooms"] == beds:
            return r["monthly_rent"]
    return None


# ---------------------------------------------------------------- pro forma


def proforma(ctx, program, flag_list, relief, A, land_price, rng) -> dict:
    t = TEMPLATES[program["product"]]
    units = program["units"]
    saleable = units * t["unit_sqft"]
    gfa = program["gfa_sqft"]

    # revenue
    q, meta = sale_psf(ctx)
    rent = rent_for(ctx, t["unit_sqft"])
    exits = []
    if q is not None:
        psf = rng.triangular(q[0], q[1], q[2], N)
        if meta["kind"] == "resale":
            psf = psf * (1 + _tri(A["new_build_premium"], rng))
        exits.append(
            (
                saleable * psf,
                f"for-sale: {meta['n']} {meta['kind']} comps "
                f"${q[0]:,.0f}-${q[2]:,.0f}/sf"
                + (" + new-build premium" if meta["kind"] == "resale" else ""),
            )
        )
    if program["product"] == "walkup" and rent:
        noi = units * rent * 12 * (1 - _tri(A["opex_ratio"], rng))
        exits.append(
            (noi / _tri(A["cap_rate"], rng), f"rental exit: HUD SAFMR ${rent:,.0f}/mo at cap rate")
        )
    if exits:  # a developer takes the better exit
        revenue, rev_basis = max(exits, key=lambda e: np.nanmedian(e[0]))
    else:
        revenue = np.full(N, np.nan)
        rev_basis = "no usable comps"

    # entitlement and schedule
    ent = entitlement.sample(relief, N, rng)
    flag_months = [f["months"] for f in flag_list if f["months"]]
    study = (
        np.max([rng.uniform(lo, hi, N) for lo, hi in flag_months], axis=0)
        if flag_months
        else np.zeros(N)
    )
    months_permit = _tri(A["permit_review_months"], rng) + np.maximum(ent["months"], study)

    # costs
    hard = gfa * _tri(A["hard_cost_psf"], rng)
    soft = hard * _tri(A["soft_cost_share"], rng)
    cont = (hard + soft) * _tri(A["contingency_share"], rng)
    priced = [f["cost_usd"] for f in flag_list if f["cost_usd"]]
    premium = (
        np.sum([rng.uniform(lo, hi, N) for lo, hi in priced], axis=0) if priced else np.zeros(N)
    )
    r = _tri(A["carry_rate"], rng)
    mc = _tri(A["construction_months"], rng)
    build_carry = 0.5 * (hard + soft + cont) * r * mc / 12
    land_carry_factor = r * (months_permit + mc) / 12
    nonland = hard + soft + cont + premium + build_carry
    total = land_price * (1 + land_carry_factor) + nonland
    margin = revenue / total - 1
    m = A["target_margin"].value
    max_land = (revenue / (1 + m) - nonland) / (1 + land_carry_factor)
    return {
        "revenue": revenue,
        "total": total,
        "margin": margin,
        "max_land": max_land,
        "premium": premium,
        "premium_share": premium / total,
        "p": ent["p"],
        "months": months_permit,
        "rev_basis": rev_basis,
        "ent_sources": ent["sources"],
        "gfa": gfa,
        "saleable": saleable,
    }


# ---------------------------------------------------------------- score


# Score = approval path (35) + site cost (35) + land headroom (30). Additive, so every point
# belongs to one named component (report: "Where the score comes from"). The three shapes
# are UNCALIBRATED placeholders; validation sets them (spec: Score).
WEIGHTS = {"approval": 35, "site_cost": 35, "land": 30}


def score_samples(pf: dict, A: dict, land_price: float) -> dict[str, np.ndarray]:
    tau = A["score_time_scale_months"].value
    kappa = A["score_premium_scale"].value
    full = A["score_land_full_ratio"].value
    approval = WEIGHTS["approval"] * pf["p"] * np.exp(-pf["months"] / tau)
    site = WEIGHTS["site_cost"] * np.clip(1 - pf["premium_share"] / kappa, 0, 1)
    if land_price > 0:
        land = WEIGHTS["land"] * np.clip(pf["max_land"] / (full * land_price), 0, 1)
    else:
        land = WEIGHTS["land"] * (pf["max_land"] > 0)
    land = np.where(np.isnan(pf["max_land"]), 0, land)
    return {"approval": approval, "site_cost": site, "land": land, "total": approval + site + land}


def band(score: float) -> str:
    return (
        "fast_track" if score >= 75 else "feasible_with_conditions" if score >= 50 else "high_risk"
    )


# ---------------------------------------------------------------- explanation

PRODUCT_NAMES = {
    "single_family": ("single-family home", "single-family homes"),
    "duplex": ("duplex", "duplexes"),
    "triplex": ("triplex", "triplexes"),
    "townhome": ("attached townhome", "attached townhomes"),
    "walkup": ("unit walk-up", "unit walk-up"),
}
RELIEF_NAMES = {
    "administrator_exception": "an administrator exception",
    "special_exception": "a special exception",
    "variance": "a variance",
    "use_variance": "a use variance",
    "conditional_use": "a conditional use",
    "rezoning": "a rezoning",
    "subdivision": "a subdivision",
}


def _k(x: float) -> str:
    return f"-${-x / 1000:,.0f}k" if x < 0 else f"${x / 1000:,.0f}k"


def program_name(opt: dict) -> str:
    one, many = PRODUCT_NAMES[opt["product"]]
    if opt["product"] == "walkup":
        return f"{opt['units']}-{one}"
    if opt["units"] == 1:
        return one
    return f"{opt['units']} {many}" if opt["product"] == "townhome" else one


def explain(head, flag_list, land: float, land_src: str, margin: float):
    """Plain-language reasons per score component, the land-price risk, and a summary."""
    if head is None:
        return [], None, None
    opt, pf, sc = head
    med = lambda x: float(np.nanmedian(x))  # noqa: E731
    months = med(pf["months"])
    relief = [RELIEF_NAMES.get(i["type"], i["type"]) for i in opt["relief"]]
    path = "By right, no hearing" if not relief else "Needs " + " and ".join(relief)
    priced = sorted(
        (f for f in flag_list if f["cost_usd"]),
        key=lambda f: -(f["cost_usd"][0] + f["cost_usd"][1]),
    )
    site_why = f"{priced[0]['title']} causes most of it" if priced else "No priced site constraints"
    ml10, ml50, ml90 = np.nanpercentile(pf["max_land"], [10, 50, 90])
    basis = "asking" if land_src == "user input" else "assessed land value"
    if ml50 <= 0:
        land_why = "Build cost exceeds value: no room to pay for land"
    elif ml50 < land:
        land_why = f"The {basis} is above the max land price"
    else:
        land_why = f"Max land price is above the {basis}"
    components = [
        {
            "key": "approval_path",
            "label": "Approval path",
            "points": round(med(sc["approval"])),
            "max_points": WEIGHTS["approval"],
            "note": f"{path}; about {months:.0f} months to permit-ready",
        },
        {
            "key": "site_cost",
            "label": "Site cost",
            "points": round(med(sc["site_cost"])),
            "max_points": WEIGHTS["site_cost"],
            "note": site_why,
        },
        {
            "key": "land_headroom",
            "label": "Land headroom",
            "points": round(med(sc["land"])),
            "max_points": WEIGHTS["land"],
            "note": land_why,
        },
    ]
    land_risk = None
    if land > 0 and ml50 < land:
        land_risk = f"High risk at the {'asking price' if basis == 'asking' else 'assessed value'}"

    lead = (
        ("A by-right " if not relief else "With " + " and ".join(relief) + ", a ")
        + program_name(opt)
        + " fits this lot"
    )
    top_cost = priced[0]["title"].split(" (")[0].lower() if priced else None
    if ml50 <= 0:
        tail = (
            f", but at today's cost assumptions it cannot carry land: building costs plus a "
            f"{margin:.0%} margin exceed the sale value by about {_k(-ml50)}."
        )
    else:
        why = f", but {top_cost} leaves" if top_cost else ", leaving"
        tail = (
            f"{why} room to pay only {_k(max(ml10, 0))}–{_k(ml90)} for the land. "
            f"The {'asking price' if basis == 'asking' else 'assessed land value'} "
            f"is {_k(land)}."
        )
    return components, land_risk, lead + tail


def site_premium(flag_list: list[dict]) -> dict:
    """Total constraint cost range and the flags behind it, largest first."""
    priced = sorted(
        (f for f in flag_list if f["cost_usd"]),
        key=lambda f: -(f["cost_usd"][0] + f["cost_usd"][1]),
    )
    return {
        "low": sum(f["cost_usd"][0] for f in priced),
        "high": sum(f["cost_usd"][1] for f in priced),
        "drivers": [f["title"].split(" (")[0] for f in priced],
    }


def land_over(max_land: np.ndarray, land: float) -> dict | None:
    """How far the land price sits above the max land price (None when it doesn't)."""
    p10, p50, p90 = np.nanpercentile(max_land, [10, 50, 90])
    if land <= 0 or p50 >= land:
        return None
    return {"low": float(max(land - p90, 0)), "high": float(land - p10)}


def lot_dims(rules: dict) -> dict | None:
    covered = [r for r in rules.get("readings", []) if r["covered"]]
    if not covered:
        return None
    env = covered[0]["scenarios"]["strict"]["envelope"]
    return {"width": env["width_ft"], "depth": env["depth_ft"]}


ODDS_NOTE = (
    "Each rule either passes or fails. A failure that an approval can fix adds that approval; "
    "the building's approval odds are the product of the odds of every approval it needs "
    "(measured from City Council votes for conditional uses and rezonings, expert "
    "placeholders for the others). A building that passes every rule is allowed outright."
)


def rule_checks(ctx: dict, rules: dict, scenario: str | None, options: list[dict]) -> dict | None:
    """Every building type tested on this lot, rule by rule, with its approval odds."""
    covered = [r for r in rules.get("readings", []) if r["covered"]]
    if not covered or scenario is None:
        return None
    reading = covered[0]
    programs = reading["scenarios"][scenario]["programs"]
    chosen = {(o["product"], o["units"]): o["label"] for o in options}
    out = []
    for prog in programs:
        statuses = {c["status"] for c in prog["checks"]}
        outcome = (
            "rejected"
            if "rejected" in statuses
            else "needs_approval"
            if "needs_approval" in statuses
            else "by_right"
        )
        odds = months = None
        if outcome != "rejected":
            ent = entitlement.sample(prog["relief"], N, np.random.default_rng(11))
            odds, months = _range(ent["p"]), _range(ent["months"])
        out.append(
            {
                "product_type": prog["product"],
                "units": prog["units"],
                "gfa_sqft": prog["gfa_sqft"],
                "outcome": outcome,
                "checks": prog["checks"],
                "approval_prob": odds,
                "approval_months": months,
                "representative": False,
                "chosen_as": chosen.get((prog["product"], prog["units"])),
            }
        )
    # one readable column per building type: largest allowed outright, else largest needing
    # approval, else the smallest tested (to show why that type fails)
    for product in TEMPLATES:
        mine = [p for p in out if p["product_type"] == product]
        pick = (
            max(
                (p for p in mine if p["outcome"] == "by_right"),
                key=lambda p: p["units"],
                default=None,
            )
            or max(
                (p for p in mine if p["outcome"] == "needs_approval"),
                key=lambda p: p["units"],
                default=None,
            )
            or min(mine, key=lambda p: p["units"])
        )
        pick["representative"] = True
    return {
        "district": reading["district"],
        "scenario": scenario,
        "uncovered_districts": [r["district"] for r in rules["readings"] if not r["covered"]],
        "site_checks": site_checks(ctx),
        "not_checked": NOT_CHECKED,
        "programs": out,
        "odds_note": ODDS_NOTE,
    }


# ---------------------------------------------------------------- orchestration


BLOCKING = ("use_variance", "implausible")


def _requested(programs: list[dict], product: str, units: int | None) -> dict:
    """The tested program for a requested building type. Without a unit count: the largest
    allowed outright, else the largest that approvals could allow, else the smallest tested."""
    if product not in TEMPLATES:
        raise ValueError(f"unknown product_type {product!r}; one of {sorted(TEMPLATES)}")
    mine = [p for p in programs if p["product"] == product]
    if units is not None:
        pick = next((p for p in mine if p["units"] == units), None)
        if pick is None:
            raise ValueError(
                f"{product} is tested at {TEMPLATES[product]['units']} units, not {units}"
            )
        return pick
    by_right = [p for p in mine if not p["relief"]]
    plausible = [p for p in mine if not any(i["type"] in BLOCKING for i in p["relief"])]
    return (
        max(by_right, key=lambda p: p["units"], default=None)
        or max(plausible, key=lambda p: p["units"], default=None)
        or min(mine, key=lambda p: p["units"])
    )


def _options(
    rules: dict, program: dict | None = None
) -> tuple[list[dict], str | None, dict | None]:
    """Candidate programs from the primary district reading, and the requested program (if
    any). With a request, it is the only option; a request the rules reject has none."""
    covered = [r for r in rules.get("readings", []) if r["covered"]]
    if not covered:
        return [], None, None
    reading = covered[0]
    scen = "contextual" if "contextual" in reading["scenarios"] else "strict"
    s = reading["scenarios"][scen]
    if program is not None:
        pick = _requested(s["programs"], program["product_type"], program.get("units"))
        if any(i["type"] in BLOCKING for i in pick["relief"]):
            return [], scen, pick
        return [{"label": "with_relief" if pick["relief"] else "by_right", **pick}], scen, pick
    out = []
    if s["best_by_right"]:
        out.append({"label": "by_right", **s["best_by_right"]})
    if s["best_with_relief"]:
        out.append({"label": "with_relief", **s["best_with_relief"]})
    return out, scen, None


def analyze(ctx: dict, overrides: dict | None = None, program: dict | None = None) -> dict:
    """SiteContext (dict) -> SiteAnalysis (dict).

    `overrides` keys are the editable `assumptions[].key` values, including `land_price`
    (default: assessed land value). `program` = {"product_type": ..., "units": ... | None}
    scores that building instead of the engine's pick (units None = the largest the rules
    allow); a building the rules reject comes back high risk, with the reason.
    """
    overrides = dict(overrides or {})
    land_price = overrides.pop("land_price", None)
    A = resolve(overrides)
    parcel = ctx["parcels"][0]
    land = land_price if land_price is not None else (parcel.get("assessed_land") or 0)
    land_src = (
        "user input"
        if land_price is not None
        else "county assessed land value (not a market price)"
    )

    rules = rules_analyze(ctx)
    options, scenario, requested = _options(rules, program)
    units_hint = max((o["units"] for o in options), default=1)
    flag_list, cleared = constraints.flags(ctx, rules, units_hint)
    if scenario == "contextual":
        flag_list.append(
            constraints._flag(
                "contextual_setbacks",
                "zoning",
                "low",
                "Program relies on contextual side setbacks (925.06.C)",
                None,
                None,
                [
                    {
                        "source": "Pittsburgh Zoning Code",
                        "as_of": None,
                        "layer": "rules",
                        "code_section": "925.06.C",
                        "url": None,
                    }
                ],
                "medium",
                "Survey the neighbours' actual side setbacks (must be 3 ft or less)",
                ("Boundary survey showing adjacent setbacks", "surveyor", (1_500, 3_500)),
            )
        )

    results = []
    for opt in options:
        rng = np.random.default_rng(7)
        pf = proforma(ctx, opt, flag_list, opt["relief"], A, land, rng)
        sc = score_samples(pf, A, land)
        results.append((opt, pf, sc))

    # headline option: highest risk-adjusted margin (P x margin, median)
    def radj(res):
        _, pf, _ = res
        v = np.nanmedian(pf["p"] * pf["margin"])
        return -math.inf if math.isnan(v) else v

    # Headline option (open contract decision; this is the default):
    # 1. a profitable by-right program leads: what you can do without asking permission;
    # 2. else the profitable option with the best P(approval) x margin;
    # 3. else the lowest-risk option, since P x margin would reward the riskier loss.
    by_right = next((r for r in results if r[0]["label"] == "by_right"), None)
    profitable = [r for r in results if np.nanmedian(r[1]["margin"]) > 0]
    if by_right is not None and any(r is by_right for r in profitable):
        head = by_right
    elif profitable:
        head = max(profitable, key=radj)
    else:
        head = by_right or (results[0] if results else None)

    # counterfactual breakdown: remove one flag, recompute the headline score
    breakdown = []
    if head:
        opt, pf, sc = head
        base = float(np.nanmedian(sc["total"]))
        for f in flag_list:
            rest = [g for g in flag_list if g["id"] != f["id"]]
            pf2 = proforma(ctx, opt, rest, opt["relief"], A, land, np.random.default_rng(7))
            lost = float(np.nanmedian(score_samples(pf2, A, land)["total"])) - base
            if lost > 0.5:
                comp = "approval_path" if f["months"] and not f["cost_usd"] else "site_cost"
                breakdown.append(
                    {"component": comp, "points_lost": round(lost, 1), "driver_flag_id": f["id"]}
                )
        if opt["relief"]:
            pf3 = proforma(ctx, opt, flag_list, [], A, land, np.random.default_rng(7))
            lost = float(np.nanmedian(score_samples(pf3, A, land)["total"])) - base
            breakdown.append(
                {
                    "component": "approval_path",
                    "points_lost": round(lost, 1),
                    "driver_flag_id": "relief:" + "+".join(i["type"] for i in opt["relief"]),
                }
            )
        breakdown.sort(key=lambda b: -b["points_lost"])

    # verdict
    if head is None:
        score = None
        if not rules.get("covered"):
            vband, headline = (
                "not_scored",
                "Partial report: zoning is not covered here; physical and market checks ran",
            )
        else:
            vband, headline = "high_risk", "No plausible program fits this lot"
            if requested is not None:
                why = "; ".join(
                    c["note"] or c["label"]
                    for c in requested["checks"]
                    if c["status"] == "rejected"
                )
                name = program_name(requested)
                name = (
                    name
                    if name[0].isdigit() and requested["product"] == "townhome"
                    else f"a {name}"
                )
                headline = f"High risk: the zoning rules rule out {name} here ({why})."
    else:
        opt, pf, sc = head
        score = float(np.nanmedian(sc["total"]))
        vband = band(score)
        low_conf = any(f["confidence"] == "low" and f["severity"] != "low" for f in flag_list)
        if vband == "fast_track" and low_conf:
            vband = "feasible_with_conditions"  # spec: low confidence never drives fast track
        driver = breakdown[0]["driver_flag_id"] if breakdown else None
        why = next((f["title"] for f in flag_list if f["id"] == driver), None) or (
            driver.replace("relief:", "needs ").replace("_", " ")
            if driver
            else "no major constraints found"
        )
        if vband == "fast_track":
            why = (
                f"{opt['units']} {opt['product'].replace('_', ' ')} by right, "
                "no high-severity constraints"
            )
        headline = f"{vband.replace('_', ' ').capitalize()}: {why}."

    # next steps: free checks first, then P(kill) / cost
    steps = []
    needs_relief = any(o["relief"] for o in options)
    if needs_relief or not rules.get("covered"):
        steps.append(
            (
                "Zoning pre-application meeting",
                "City Planning",
                (0, 0),
                "Confirms the approval path before design money is spent",
                [f["id"] for f in flag_list if f["category"] == "zoning"],
                1.0,
            )
        )
    for f in flag_list:
        if f["_action"]:
            action, who, cost = f["_action"]
            mid = (cost[0] + cost[1]) / 2
            steps.append(
                (
                    action,
                    who,
                    cost,
                    f["resolution"],
                    [f["id"]],
                    constraints.P_KILL[f["severity"]] / max(mid, 1),
                )
            )
    steps.sort(key=lambda s: (s[2][1] > 0, -s[5]))
    next_steps = [
        {"order": i + 1, "action": a, "who": w, "cost_usd": c, "why": y, "flag_ids": ids}
        for i, (a, w, c, y, ids, _) in enumerate(steps)
    ]

    def opt_out(res):
        o, pf, sc = res
        return {
            "label": o["label"],
            "product_type": o["product"],
            "units": o["units"],
            "relief": [f"{i['type']} ({i['section']})" for i in o["relief"]],
            "margin": _range(pf["margin"]),
            "months": _range(pf["months"]),
            "approval_prob": _range(pf["p"]),
            "max_land_price": _range(pf["max_land"]),
            "score": _range(sc["total"]),
            "revenue_basis": pf["rev_basis"],
            "entitlement_basis": pf["ent_sources"],
            "gfa_sqft": pf["gfa"],
            "unit_sqft": TEMPLATES[o["product"]]["unit_sqft"],
            "site_cost_premium": _range(pf["premium"]),
        }

    assumptions = [
        {
            "key": a.key,
            "label": a.label,
            "value": a.value,
            "unit": a.unit,
            "source": a.source,
            "editable": a.editable,
            "min": a.low,
            "max": a.high,
        }
        for a in A.values()
    ]
    assumptions.append(
        {
            "key": "land_price",
            "label": "Land price",
            "value": land,
            "unit": "$",
            "source": land_src,
            "editable": True,
            "min": None,
            "max": None,
        }
    )

    components, land_risk, summary = explain(
        head, flag_list, land, land_src, A["target_margin"].value
    )
    return {
        "verdict": {
            "score": None if score is None else round(score),
            "score_range": None if head is None else _range(head[2]["total"]),
            "band": vband,
            "headline": headline,
            "land_risk": land_risk,
            "components": components,
        },
        "narrative": {"summary": summary},
        "metrics": None
        if head is None
        else {
            "option": head[0]["label"],
            "months_to_permit": _range(head[1]["months"]),
            "approval_prob": _range(head[1]["p"]),
            "max_land_price": _range(head[1]["max_land"]),
            "land_basis": {"value": land, "source": land_src},
            "site_cost_premium": site_premium(flag_list),
            "land_over_max": land_over(head[1]["max_land"], land),
            "comps": {
                "count": len(ctx["market"]["sales"]),
                "radius_mi": round(ctx["market"].get("comps_radius_ft", 0) / 5280, 2),
                "window_months": ctx["market"].get("comps_years", 0) * 12,
            },
        },
        "flags": [
            {k: v for k, v in f.items() if k != "_action"}
            | {
                "resolved_by_step": next(
                    (st["order"] for st in next_steps if f["id"] in st["flag_ids"]), None
                )
            }
            for f in sorted(
                flag_list, key=lambda f: ["high", "medium", "unknown", "low"].index(f["severity"])
            )
        ],
        "cleared": cleared,
        "options": [opt_out(r) for r in results],
        "next_steps": next_steps,
        "score_breakdown": breakdown,
        "rule_checks": rule_checks(ctx, rules, scenario, options),
        "assumptions": assumptions,
        "rules": {
            "scenario": scenario,
            "confidence": rules.get("confidence"),
            "neighbors_built": rules.get("neighbors_built"),
            "lot_dimensions_ft": lot_dims(rules),
        },
        "versions": {
            "engine": ENGINE_VERSION,
            "ruleset": "rules drafts 2026-09-26",
            "schema": ctx.get("schema_version"),
            "data_as_of": min(
                (v["as_of"] for v in (ctx.get("provenance") or {}).values() if v.get("as_of")),
                default=None,
            ),
        },
    }
