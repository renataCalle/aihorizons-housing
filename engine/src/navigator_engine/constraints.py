"""Constraint model v0: SiteContext facts (+ rules-engine overlays) -> flags.

Each flag carries severity, a cost range, a schedule range, evidence, confidence, and how to
resolve it (spec: Flag). Thresholds and costs below are expert-judgment PLACEHOLDERS (spec v0
fallback) and are listed in the output's assumptions. A missing fact yields an `unknown`
flag, never a clean check.
"""

PLACEHOLDER = "PLACEHOLDER cost/threshold"

# severity -> probability the check kills the deal (for cost-to-kill ordering); placeholder
P_KILL = {"high": 0.30, "medium": 0.10, "low": 0.03, "unknown": 0.15}


def _ev(ctx: dict, key: str, code_section: str | None = None) -> list[dict]:
    src = (ctx.get("provenance") or {}).get(key) or {}
    return [
        {
            "source": src.get("name") or key,
            "as_of": src.get("as_of"),
            "layer": key,
            "code_section": code_section,
            "url": src.get("url"),
        }
    ]


def _flag(
    fid, category, severity, title, cost, months, evidence, confidence, resolution, action=None
):
    return {
        "id": fid,
        "category": category,
        "severity": severity,
        "title": title,
        "cost_usd": cost,
        "months": months,
        "evidence": evidence,
        "confidence": confidence,
        "resolution": resolution,
        "_action": action,
    }


def flags(ctx: dict, rules: dict, units: int) -> tuple[list[dict], list[str]]:
    """Returns (flags, cleared checks)."""
    out, cleared = [], []
    phys = ctx["physical"]
    parcel = ctx["parcels"][0]
    title = ctx.get("title") or {}

    # ---- zoning coverage and confidence
    if not rules.get("covered"):
        out.append(
            _flag(
                "zoning_not_covered",
                "zoning",
                "unknown",
                f"Zoning not covered for {parcel['municipality']}",
                None,
                None,
                _ev(ctx, "zoning"),
                "low",
                "Confirm allowed uses and dimensions with the municipality",
                ("Municipal zoning review with the borough", "applicant", (0, 2_000)),
            )
        )
    elif rules.get("confidence") == "low":
        out.append(
            _flag(
                "split_zoned",
                "zoning",
                "medium",
                "Parcel spans more than one district or has uncovered rules",
                None,
                (0.5, 2),
                _ev(ctx, "zoning"),
                "low",
                "Ask City Planning which district governs the proposed footprint",
                ("Zoning pre-application meeting", "City Planning", (0, 0)),
            )
        )

    # ---- steep slope (city layer; >= 25% grade), 915.02 grading rules
    s = phys.get("steep_slope_share")
    if s is None:
        out.append(
            _flag(
                "slope_unknown",
                "physical",
                "unknown",
                "Slope not mapped here",
                None,
                None,
                _ev(ctx, "steep_slope"),
                "low",
                "Order a topographic survey",
                ("Topographic survey", "surveyor", (1_500, 4_000)),
            )
        )
    elif s >= 0.5:
        out.append(
            _flag(
                "steep_slope",
                "physical",
                "high",
                f"{s:.0%} of lot on 25%+ slope",
                (40_000, 150_000),
                (1, 4),
                _ev(ctx, "steep_slope", "915.02"),
                "medium",
                "Geotechnical report; walls under 10 ft, cut/fill under 25% (915.02)",
                (
                    "Geotechnical and grading feasibility study",
                    "geotechnical engineer",
                    (3_000, 8_000),
                ),
            )
        )
    elif s >= 0.15:
        out.append(
            _flag(
                "steep_slope",
                "physical",
                "medium",
                f"{s:.0%} of lot on 25%+ slope",
                (15_000, 60_000),
                (0.5, 2),
                _ev(ctx, "steep_slope", "915.02"),
                "medium",
                "Grading plan within 915.02 limits",
                ("Grading feasibility review", "civil engineer", (1_500, 4_000)),
            )
        )
    elif s > 0:
        out.append(
            _flag(
                "steep_slope",
                "physical",
                "low",
                f"{s:.0%} of lot on 25%+ slope",
                (5_000, 20_000),
                (0, 1),
                _ev(ctx, "steep_slope", "915.02"),
                "medium",
                "Keep the footprint off the steep portion",
                None,
            )
        )
    else:
        cleared.append("steep slope")

    # ---- landslide-prone
    ls = phys.get("landslide_prone_share")
    if ls is None:
        pass  # covered by slope_unknown outside the city
    elif ls > 0:
        sev = "high" if ls >= 0.5 else "medium"
        out.append(
            _flag(
                "landslide_prone",
                "physical",
                sev,
                f"{ls:.0%} of lot landslide-prone",
                (10_000, 80_000),
                (1, 3),
                _ev(ctx, "landslide_prone"),
                "medium",
                "Geotechnical investigation of slope stability",
                ("Slope stability assessment", "geotechnical engineer", (4_000, 10_000)),
            )
        )
    else:
        cleared.append("landslide-prone areas")

    # ---- undermining: UM-O overlay procedure comes from the rules engine (906.05)
    u = phys.get("undermined_share")
    deep = phys.get("deep_mined_share") or 0
    if u is None and deep == 0:
        out.append(
            _flag(
                "undermining_unknown",
                "physical",
                "unknown",
                "Undermining not mapped by the city here",
                None,
                None,
                _ev(ctx, "undermined"),
                "low",
                "Request DEP mine subsidence records",
                ("DEP mine map and subsidence records request", "applicant", (0, 500)),
            )
        )
    elif (u or 0) > 0 or deep > 0:
        multi = units > 1
        out.append(
            _flag(
                "undermined",
                "physical",
                "high" if multi else "medium",
                f"{max(u or 0, deep):.0%} of lot over mapped mine workings"
                + (" (UM-O overlay)" if (u or 0) > 0 else ""),
                (8_000, 25_000) if not multi else (15_000, 60_000),
                (1, 3),
                _ev(ctx, "undermined", "906.05"),
                "medium",
                "DEP records + site investigation; possible grouting or special "
                "foundations; mine subsidence insurance",
                (
                    "Geotechnical site investigation incl. DEP mine records",
                    "geotechnical consultant",
                    (8_000, 25_000),
                ),
            )
        )
    else:
        cleared.append("undermining")

    # ---- flood (FP-O = FEMA SFHA), 906.02
    zones = {z["code"]: z["share"] for z in phys.get("flood_zones") or []}
    if zones.get("FLOODWAY"):
        out.append(
            _flag(
                "floodway",
                "physical",
                "high",
                f"{zones['FLOODWAY']:.0%} of lot in the regulatory floodway",
                None,
                (6, 18),
                _ev(ctx, "flood", "906.02.E.2.a"),
                "high",
                "No-rise hydraulic analysis and DEP permit; usually not feasible",
                (
                    "Floodway feasibility check with the Floodplain Administrator",
                    "City Planning",
                    (0, 0),
                ),
            )
        )
    sfha = zones.get("AE", 0) + zones.get("A", 0)
    if sfha > 0:
        out.append(
            _flag(
                "flood_zone",
                "physical",
                "high" if sfha >= 0.5 else "medium",
                f"{sfha:.0%} of lot in the 1% annual-chance floodplain",
                (20_000, 90_000),
                (0.5, 2),
                _ev(ctx, "flood", "906.02.F.2"),
                "high",
                "Lowest floor at base flood elevation + 1.5 ft, no basement; flood insurance",
                (
                    "Elevation certificate / survey of base flood elevation",
                    "surveyor",
                    (500, 1_500),
                ),
            )
        )
    elif not zones.get("FLOODWAY"):
        cleared.append("FEMA floodplain")

    # ---- environmental records (facts: DEP sites within 1,000 ft)
    env = ctx.get("environmental") or []
    near = [e for e in env if e["distance_ft"] <= 250]
    if near:
        e = min(near, key=lambda x: x["distance_ft"])
        out.append(
            _flag(
                "env_nearby",
                "environmental",
                "medium",
                f"{len(near)} DEP record(s) within 250 ft (nearest "
                f"{e['distance_ft']:.0f} ft: {e['site_type'].replace('_', ' ')})",
                (3_000, 40_000),
                (0.5, 3),
                _ev(ctx, "environmental"),
                "medium",
                "Phase I ESA; Phase II if recognized conditions are found",
                (
                    "Phase I Environmental Site Assessment",
                    "environmental consultant",
                    (2_500, 5_000),
                ),
            )
        )
    elif env:
        out.append(
            _flag(
                "env_nearby",
                "environmental",
                "low",
                f"{len(env)} DEP record(s) within 1,000 ft",
                (0, 5_000),
                (0, 1),
                _ev(ctx, "environmental"),
                "medium",
                "Phase I ESA recommended",
                (
                    "Phase I Environmental Site Assessment",
                    "environmental consultant",
                    (2_500, 5_000),
                ),
            )
        )
    else:
        cleared.append("DEP environmental records")

    # ---- access and infrastructure
    fr = ctx["infrastructure"].get("frontage_type")
    if fr in ("none", "steps"):
        out.append(
            _flag(
                "frontage",
                "infrastructure",
                "high" if fr == "none" else "medium",
                "No street frontage within 60 ft"
                if fr == "none"
                else "Frontage on public steps only",
                (25_000, 100_000),
                (1, 4),
                _ev(ctx, "frontage"),
                "medium",
                "Confirm legal access and utility connections",
                ("Boundary survey + access and utility review", "surveyor / DOMI", (2_000, 5_000)),
            )
        )
    else:
        cleared.append("street frontage")
    if ctx["infrastructure"].get("combined_sewershed"):
        out.append(
            _flag(
                "combined_sewer",
                "infrastructure",
                "low",
                "Combined sewershed (proxy for stormwater requirements)",
                (5_000, 20_000),
                (0, 1),
                _ev(ctx, "sewer"),
                "low",
                "Stormwater management plan; capacity inquiry to PWSA",
                ("Sewer capacity inquiry", "PWSA", (0, 500)),
            )
        )

    # ---- site condition, title
    if parcel.get("has_structure"):
        out.append(
            _flag(
                "demolition",
                "physical",
                "low",
                "Existing structure to demolish",
                (15_000, 45_000),
                (1, 2),
                _ev(ctx, "parcels"),
                "high",
                "Demolition permit; asbestos survey",
                None,
            )
        )
    if title.get("condemned"):
        out.append(
            _flag(
                "condemned",
                "physical",
                "medium",
                "Condemned or dead-end property",
                (15_000, 60_000),
                (1, 3),
                _ev(ctx, "parcels"),
                "high",
                "Structural assessment or demolition",
                None,
            )
        )
    liens = title.get("tax_lien_total_usd") or 0
    if liens > 0:
        out.append(
            _flag(
                "tax_liens",
                "market",
                "medium",
                f"${liens:,.0f} in tax liens",
                (liens, liens),
                (1, 4),
                _ev(ctx, "parcels"),
                "high",
                "Clear liens at closing; title insurance",
                ("Title search", "title company", (300, 1_000)),
            )
        )

    # ---- zoning procedure flags come from the rules engine's overlay list
    for o in rules.get("overlays") or []:
        if o["type"] == "design_requirement":
            continue  # already priced in flood_zone
        if o["section"].startswith("906.05"):
            continue  # priced in the undermined flag
        out.append(
            _flag(
                f"overlay_{o['section']}",
                "zoning",
                "medium",
                o["what"],
                None,
                (1, 3),
                [
                    {
                        "source": "Pittsburgh Zoning Code",
                        "as_of": None,
                        "layer": "rules",
                        "code_section": o["section"],
                        "url": None,
                    }
                ],
                "high",
                o["what"],
                None,
            )
        )
    return out, cleared
