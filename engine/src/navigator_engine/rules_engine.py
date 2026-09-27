"""Rules engine: buildable envelope and the zoning checks for every building type.

Input: a SiteContext-shaped dict and the rules tables in navigator_engine/config/rules/
(drafted by sandbox/rules/extract.py from the zoning code). Pure computation.

Pittsburgh's residential district tables (903.03) set a minimum lot size but no density or
coverage limit, so capacity comes from the envelope: (lot width - side setbacks) x (lot depth -
front and rear setbacks) x stories. Lot width and depth are read from the parcel's minimum
rotated rectangle. Contextual setbacks (925.06) can only reduce required setbacks, so ignoring
them is conservative.
"""

import csv
import io
from dataclasses import dataclass, field
from importlib.resources import files

import shapely
from shapely.geometry import shape

RULES = files("navigator_engine") / "config" / "rules"

# ---------------------------------------------------------------- assumptions (editable)
# Product templates are judgments, not code: surfaced to the user as editable assumptions.
TEMPLATES = {
    "single_family": {
        "use": "single_unit_detached",
        "units": [1],
        "unit_sqft": 1_500,
        "stories": 2,
    },
    "duplex": {"use": "two_unit", "units": [2], "unit_sqft": 1_100, "stories": 2},
    "triplex": {"use": "three_unit", "units": [3], "unit_sqft": 950, "stories": 3},
    "townhome": {
        "use": "single_unit_attached",
        "units": list(range(2, 9)),
        "unit_sqft": 1_400,
        "stories": 3,
        "unit_width_ft": 18,
    },
    "walkup": {
        "use": "multi_unit",
        "units": list(range(4, 13)),
        "unit_sqft": 850,
        "stories": 3,
        "efficiency": 0.80,
    },
}
# A dimensional variance is plausible only for a modest deviation (judgment; calibrate on ZBA
# outcomes once available). Programs needing more than this are not offered.
MAX_DIMENSIONAL_SHORTFALL = 0.25
CONTEXTUAL_MIN_SIDE_FT = 3.0  # 925.06.C floor when adjacent lots are built

RELIEF_FOR = {
    "P": None,
    "A": "administrator_exception",
    "S": "special_exception",
    "C": "conditional_use",
    "P/S": None,
    "": "use_variance",
}


def _load(name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO((RULES / name).read_text())))


def _num(v: str):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


DIM = {}  # district -> standard -> (value, section)
for r in _load("residential_draft.csv"):
    if r["district"] != "*":
        DIM.setdefault(r["district"], {})[r["standard"]] = (_num(r["value"]), r["code_section"])
USE = {}  # (use, use-subdistrict column) -> (permission, section)
for r in _load("use_permissions_draft.csv"):
    USE[(r["use"], r["district_column"])] = r["permission"]
STD = _load("standards_draft.csv")
PARKING = {r["scope"]: _num(r["value"]) for r in STD if r["standard"] == "parking_min_per_unit"}


# ---------------------------------------------------------------- envelope


@dataclass
class Envelope:
    district: str
    scenario: str  # strict (district table) | contextual (925.06.C side setbacks)
    lot_sqft: float
    width_ft: float
    depth_ft: float
    side_setback_ft: float
    footprint_sqft: float
    stories: float | None
    height_ft: float | None
    covered: bool = True
    notes: list[str] = field(default_factory=list)


def lot_dimensions(geojson: dict) -> tuple[float, float, float]:
    geom = shape(geojson)
    rect = shapely.minimum_rotated_rectangle(geom)
    xs, ys = rect.exterior.coords.xy
    sides = sorted(
        {round(((xs[i + 1] - xs[i]) ** 2 + (ys[i + 1] - ys[i]) ** 2) ** 0.5, 2) for i in range(4)}
    )
    width, depth = sides[0], sides[-1]
    return geom.area, width, depth


def use_column(district: str) -> str:
    """'RM-M' -> 'RM'; 'H' -> 'H'; mixed-use codes map to themselves."""
    base = district.split("-")[0]
    return base if base in {"R1D", "R1A", "R2", "R3", "RM"} else district


def neighbors_built(ctx: dict) -> bool | None:
    """True when at least two adjacent lots carry a structure (both sides, for a mid-block lot);
    None when adjacency is unknown."""
    adj = ctx.get("adjacent")
    if adj is None:
        return None
    built = [a for a in adj if a["has_structure"] and a["shared_edge_ft"] >= 20]
    return len(built) >= 2


def single_unit_side_setback(width_ft: float) -> float | None:
    """925.06.C: reduced interior side yards for a single-unit house on a lot under 60 ft wide,
    regardless of neighbors."""
    if width_ft >= 60:
        return None
    if width_ft < 38:
        return 3.0
    return 4.0 if width_ft < 45 else 5.0


def envelope(ctx: dict, district: str, scenario: str = "strict") -> Envelope:
    lot, width, depth = lot_dimensions(ctx["parcels"][0]["geometry"])
    d = DIM.get(district)
    if not d:
        return Envelope(
            district,
            scenario,
            lot,
            width,
            depth,
            0,
            0,
            None,
            None,
            covered=False,
            notes=[f"no dimensional rules for {district} in v0 tables"],
        )
    g = lambda k: (d.get(k) or (None, None))[0]  # noqa: E731
    front, rear = g("min_front_setback") or 0, g("min_rear_setback") or 0
    side = g("min_interior_side_setback") or 0
    notes = []
    if scenario == "contextual":
        side = min(side, CONTEXTUAL_MIN_SIDE_FT)
        notes.append(
            "925.06.C contextual sides (3 ft); needs adjacent built lots, confirm "
            "their actual setbacks on survey"
        )
    fw, fd = max(width - 2 * side, 0), max(depth - front - rear, 0)
    env = Envelope(
        district,
        scenario,
        lot,
        width,
        depth,
        side,
        fw * fd,
        g("max_stories"),
        g("max_height"),
        notes=notes,
    )
    if district == "H" and g("max_disturbance_share"):
        env.footprint_sqft = min(env.footprint_sqft, lot * g("max_disturbance_share"))
        env.notes.append("H: disturbance capped at 50% of lot (905.02.C)")
    return env


# ---------------------------------------------------------------- relief check


CHECK_LABELS = {
    "use_allowed": "Housing type allowed in the district",
    "min_lot_size": "Lot meets the minimum lot size",
    "fits_envelope": "Fits within setbacks and stories",
    "row_fits_width": "Townhome row fits the lot width",
    "subdivision": "Each townhome on its own lot",
}

# Rules that matter for small housing but are not evaluated in v0 (shown so users know).
NOT_CHECKED = [
    {
        "label": "Off-street parking minimum",
        "section": "914.02",
        "reason": "Parking layout is not modelled; reductions (914.04) and the infill "
        "exception (914.11.B.4) apply in some cases",
    },
    {
        "label": "Maximum height in feet",
        "section": "903.03",
        "reason": "Only the number of stories is checked",
    },
    {
        "label": "Corner-lot street-side setback",
        "section": "903.03",
        "reason": "Corner lots are treated like interior lots",
    },
    {
        "label": "Residential compatibility near other districts",
        "section": "916.02",
        "reason": "Extra height and setback limits near residential and H districts",
    },
    {
        "label": "Grading and retaining walls",
        "section": "915.02",
        "reason": "Priced as a site cost (slope flag), not checked as a rule",
    },
]


def _check(
    check_id, section, status, required=None, provided=None, unit=None, relief_type=None, note=None
) -> dict:
    return {
        "check_id": check_id,
        "label": CHECK_LABELS[check_id],
        "section": section,
        "status": status,
        "required": required,
        "provided": provided,
        "unit": unit,
        "relief_type": relief_type,
        "note": note,
    }


def check_program(ctx: dict, env: Envelope, product: str, units: int) -> tuple[list[dict], float]:
    """Every zoning check for one building, pass or fail, and the floor area it needs.

    status: pass | needs_approval (fixable by the approval in relief_type) |
    rejected (implausible deviation or use not allowed) | not_applicable.
    """
    t = TEMPLATES[product]
    checks = []

    # 1. use permission (911.02; 911.04.A.69A for attached units in R1D)
    perm = USE.get((t["use"], use_column(env.district)), "")
    section = "911.02"
    if perm == "P/S":  # 911.04.A.69A: attached units in R1D by right only on lots <= 35 ft wide
        perm, section = ("P" if env.width_ft <= 35 else "S"), "911.04.A.69A"
    what = f"{t['use']} is '{perm or 'not listed'}' in {env.district}"
    if not RELIEF_FOR.get(perm):
        checks.append(_check("use_allowed", section, "pass", note=what))
    elif RELIEF_FOR[perm] == "use_variance":
        checks.append(
            _check("use_allowed", section, "rejected", relief_type="use_variance", note=what)
        )
    else:
        checks.append(
            _check(
                "use_allowed", section, "needs_approval", relief_type=RELIEF_FOR[perm], note=what
            )
        )

    # 2. minimum lot size (per new lot for townhomes; 925.01.C for a single house)
    min_lot = DIM.get(env.district, {}).get("min_lot_size") or (None, None)
    lot_per_building = env.lot_sqft / units if product == "townhome" else env.lot_sqft
    if not min_lot[0]:
        checks.append(
            _check(
                "min_lot_size",
                min_lot[1],
                "not_applicable",
                provided=round(lot_per_building),
                unit="sf",
                note="no minimum lot size in this district",
            )
        )
    elif lot_per_building >= min_lot[0]:
        checks.append(
            _check(
                "min_lot_size",
                min_lot[1],
                "pass",
                required=min_lot[0],
                provided=round(lot_per_building),
                unit="sf",
            )
        )
    elif product == "single_family":  # pre-code lots exempt, else admin exception
        checks.append(
            _check(
                "min_lot_size",
                "925.01.C.2",
                "needs_approval",
                required=min_lot[0],
                provided=round(env.lot_sqft),
                unit="sf",
                relief_type="administrator_exception",
                note=f"lot {env.lot_sqft:,.0f} sf < {min_lot[0]:,.0f} sf minimum "
                "(exempt if recorded before the code)",
            )
        )
    else:
        what = (
            f"{units} lots of {lot_per_building:,.0f} sf"
            if product == "townhome"
            else f"lot {env.lot_sqft:,.0f} sf"
        )
        short = 1 - lot_per_building / min_lot[0]
        ok = short <= MAX_DIMENSIONAL_SHORTFALL
        checks.append(
            _check(
                "min_lot_size",
                min_lot[1],
                "needs_approval" if ok else "rejected",
                required=min_lot[0],
                provided=round(lot_per_building),
                unit="sf",
                relief_type="variance" if ok else "implausible",
                note=f"{what} < {min_lot[0]:,.0f} sf minimum ({short:.0%} short)",
            )
        )

    # 3. building envelope: setbacks x stories (narrow-lot side yards for a single house)
    need_gfa = units * t["unit_sqft"] / t.get("efficiency", 1.0)
    stories = min(t["stories"], env.stories or t["stories"])
    footprint = env.footprint_sqft
    narrow_side = single_unit_side_setback(env.width_ft)
    if product == "single_family" and narrow_side is not None and narrow_side < env.side_setback_ft:
        depth = (
            env.footprint_sqft / max(env.width_ft - 2 * env.side_setback_ft, 1e-9)
            if env.width_ft > 2 * env.side_setback_ft
            else None
        )
        if depth is None:  # recover buildable depth from the lot when width was exhausted
            d = DIM[env.district]
            front, rear = d["min_front_setback"][0] or 0, d["min_rear_setback"][0] or 0
            depth = env.depth_ft - front - rear
        footprint = max(env.width_ft - 2 * narrow_side, 0) * max(depth, 0)
    capacity = footprint * stories
    if need_gfa <= capacity:
        checks.append(
            _check(
                "fits_envelope",
                "903.03",
                "pass",
                required=round(need_gfa),
                provided=round(capacity),
                unit="sf",
            )
        )
    else:
        shortfall = 1 - capacity / need_gfa
        ok = shortfall <= MAX_DIMENSIONAL_SHORTFALL
        checks.append(
            _check(
                "fits_envelope",
                "903.03",
                "needs_approval" if ok else "rejected",
                required=round(need_gfa),
                provided=round(capacity),
                unit="sf",
                relief_type="variance" if ok else "implausible",
                note=f"needs {need_gfa:,.0f} sf; envelope gives {capacity:,.0f} sf "
                f"({shortfall:.0%} short)",
            )
        )

    # 4-5. townhome-only checks
    if product == "townhome":
        row = units * t["unit_width_ft"]  # the row fronts the street: compare to lot width
        if row > env.width_ft:
            checks.append(
                _check(
                    "row_fits_width",
                    "903.03",
                    "rejected",
                    required=row,
                    provided=round(env.width_ft, 1),
                    unit="ft",
                    relief_type="implausible",
                    note=f"{units} x {t['unit_width_ft']} ft row exceeds {env.width_ft:.0f} ft "
                    "lot width",
                )
            )
        else:
            checks.append(
                _check(
                    "row_fits_width",
                    "903.03",
                    "pass",
                    required=row,
                    provided=round(env.width_ft, 1),
                    unit="ft",
                )
            )
        checks.append(
            _check(
                "subdivision",
                "911.02 (own lot per unit)",
                "needs_approval",
                relief_type="subdivision",
                note="townhomes need a subdivision into one lot per unit",
            )
        )
    else:
        checks.append(_check("row_fits_width", None, "not_applicable"))
        checks.append(_check("subdivision", None, "not_applicable"))
    return checks, need_gfa


def relief_for(ctx: dict, env: Envelope, product: str, units: int) -> tuple[list[dict], float]:
    """Relief items for a program (the failed checks), and the gross floor area it needs."""
    checks, need_gfa = check_program(ctx, env, product, units)
    items = [
        {
            "type": c["relief_type"],
            "section": c["section"],
            "what": c["note"],
            "check": c["check_id"],
        }
        for c in checks
        if c["status"] in ("needs_approval", "rejected")
    ]
    return items, need_gfa


def site_checks(ctx: dict) -> list[dict]:
    """Overlay rules that apply to the site whatever is built (906.02, 906.05)."""
    phys = ctx["physical"]
    u = phys.get("undermined_share")
    zones = {z["code"]: z["share"] for z in phys.get("flood_zones") or []}
    sfha = zones.get("AE", 0) + zones.get("A", 0)
    return [
        {
            "check_id": "undermined_overlay",
            "label": "Undermined area overlay (UM-O)",
            "section": "906.05",
            "status": "unknown" if u is None else "applies" if u > 0 else "clear",
            "note": None
            if not u
            else f"{u:.0%} of the lot. A single house must show >100 ft of "
            "rock over the mine; anything larger needs a site investigation",
        },
        {
            "check_id": "floodplain_overlay",
            "label": "Floodplain overlay (FP-O)",
            "section": "906.02.F.2",
            "status": "applies" if sfha > 0 else "clear",
            "note": None
            if not sfha
            else f"{sfha:.0%} of the lot. Lowest floor, basement included, 1.5 ft above base "
            "flood elevation",
        },
        {
            "check_id": "floodway",
            "label": "Regulatory floodway",
            "section": "906.02.E.2.a",
            "status": "applies" if zones.get("FLOODWAY") else "clear",
            "note": None
            if not zones.get("FLOODWAY")
            else "New building needs a no-rise engineering study and a DEP permit",
        },
    ]


def overlay_items(ctx: dict, units: int) -> list[dict]:
    """Overlay procedures that apply regardless of program choice."""
    out = []
    phys = ctx["physical"]
    if (phys.get("undermined_share") or 0) > 0:
        if units > 1:
            out.append(
                {
                    "type": "site_investigation",
                    "section": "906.05.B.3",
                    "what": "UM-O: geotechnical site investigation before approval",
                }
            )
        else:
            out.append(
                {
                    "type": "administrator_exception",
                    "section": "906.05.B.2 / 913.02.B",
                    "what": "UM-O: prove >100 ft overburden and no nearby subsidence",
                }
            )
    zones = {z["code"]: z["share"] for z in phys.get("flood_zones") or []}
    if zones.get("FLOODWAY"):
        out.append(
            {
                "type": "prohibited_without_study",
                "section": "906.02.E.2.a",
                "what": "floodway: no-rise H&H analysis + DEP permit",
            }
        )
    if zones.get("AE") or zones.get("A"):
        out.append(
            {
                "type": "design_requirement",
                "section": "906.02.F.2.a",
                "what": "FP-O: lowest floor, basement included, >= BFE + 1.5 ft",
            }
        )
    return out


def evaluate_programs(ctx: dict, env: Envelope) -> list[dict]:
    """Every product template x unit count, with all checks and the derived relief list."""
    programs = []
    for product, t in TEMPLATES.items():
        for n in t["units"]:
            checks, gfa = check_program(ctx, env, product, n)
            relief = [
                {
                    "type": c["relief_type"],
                    "section": c["section"],
                    "what": c["note"],
                    "check": c["check_id"],
                }
                for c in checks
                if c["status"] in ("needs_approval", "rejected")
            ]
            programs.append(
                {
                    "product": product,
                    "units": n,
                    "gfa_sqft": round(gfa),
                    "relief": relief,
                    "checks": checks,
                }
            )
    return programs


def best_programs(
    ctx: dict, env: Envelope, programs: list[dict] | None = None
) -> tuple[dict | None, dict | None]:
    programs = programs if programs is not None else evaluate_programs(ctx, env)
    by_right = [p for p in programs if not p["relief"]]
    plausible = [
        p
        for p in programs
        if p["relief"]
        and not any(i["type"] in ("use_variance", "implausible") for i in p["relief"])
    ]
    best_by_right = max(by_right, key=lambda p: p["units"], default=None)
    best_with_relief = max(plausible, key=lambda p: (p["units"], -len(p["relief"])), default=None)
    if best_with_relief and best_by_right and best_with_relief["units"] <= best_by_right["units"]:
        best_with_relief = None  # relief buys nothing
    return best_by_right, best_with_relief


def analyze(ctx: dict) -> dict:
    districts = [z for z in ctx["zoning"] if z["kind"] == "district"]
    if not districts:
        return {"covered": False, "note": "zoning not covered for this municipality in v1"}
    districts.sort(key=lambda z: -z["share"])
    built = neighbors_built(ctx)
    readings = []
    for z in districts:  # split-zoned parcels get one reading per district (spec edge state)
        reading = {"district": z["code"], "share": z["share"], "scenarios": {}}
        for scenario in ("strict", "contextual"):
            if scenario == "contextual" and not built:
                continue
            env = envelope(ctx, z["code"], scenario)
            if not env.covered:
                reading["covered"] = False
                reading["note"] = env.notes[0]
                break
            programs = evaluate_programs(ctx, env)
            br, wr = best_programs(ctx, env, programs)
            reading["scenarios"][scenario] = {
                "envelope": {
                    k: (round(v, 1) if isinstance(v, float) else v) for k, v in env.__dict__.items()
                },
                "best_by_right": br,
                "best_with_relief": wr,
                "programs": programs,
            }
        reading.setdefault("covered", True)
        readings.append(reading)
    best = [
        prog["units"]
        for r in readings
        if r["covered"]
        for v in r["scenarios"].values()
        for prog in (v["best_by_right"], v["best_with_relief"])
        if prog
    ]
    units = max(best, default=1)  # overlays key off the largest program the site could carry
    confidence = "low" if len(readings) > 1 or not all(r["covered"] for r in readings) else "high"
    return {
        "covered": True,
        "confidence": confidence,
        "neighbors_built": built,
        "readings": readings,
        "overlays": overlay_items(ctx, units),
    }
