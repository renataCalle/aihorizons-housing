"""Zoning Board approval odds from a fitted Bayesian logistic regression.

One Zoning Board hearing decides every variance and special exception a project asks for, so
the model predicts one probability per hearing from two kinds of variables:

- **the request** (which approvals, which rule each relaxes): for a past case from its
  decision, for a new proposal from the engine's zoning check;
- **the parcel** (district, market, lot, site conditions): always from the parcel's
  SiteContext, via `site_features()`. For past cases that is the stored context of the case's
  parcel (data/scores, looked up by parcel ID), so training and prediction read the same facts.

The same `features()` builds the design row for past cases (training, in navigator_research)
and for any parcel x building type the engine evaluates, so the two can never drift apart.

The fitted posterior (mean and covariance of the coefficients, Laplace approximation) lives in
config/models/approval_v1.json. Without it the engine falls back to the placeholder priors in
entitlement.RUNGS.
"""

import json
import math
from importlib.resources import files

import numpy as np

ZBA_TYPES = ("variance", "special_exception", "use_variance")  # decided at a board hearing

# What each approval relaxes, from its code section (and words, for past cases).
RULES = ("use", "lot_size", "setback", "height", "parking", "other")
RESIDENTIAL_FAMILIES = ("R1D", "R1A", "R2", "R3", "RM", "H")
STRONG_MARKETS = set("ABCDE")  # URA Market Value Analysis types with local sales strength

# Design columns, in order: a baseline for any board hearing (variances decide it when
# present), an adjustment when every request is a special exception, then 0/1 or scaled terms.
FEATURES = (
    "intercept",
    "special_exception_only",
    "rule_use",
    "rule_lot_size",
    "rule_setback",
    "rule_height",
    "rule_parking",
    "extra_approvals",
    "housing",
    "residential_district",
    "strong_market",
    "log_lot_area",
    "vacant_lot",
    "steep_slope",
    "undermined",
    "flood_zone",
)
SITE_TERMS = ("residential_district", "strong_market", "log_lot_area")
CONDITION_TERMS = ("vacant_lot", "steep_slope", "undermined", "flood_zone")
STEEP_SHARE = 0.25  # a quarter of the lot or more on 25%+ grade
LOG_LOT_CENTER = math.log(3_000)  # typical infill lot, sf


# The engine's zoning checks -> the rule they relax (the model's vocabulary).
CHECK_RULES = {
    "use_allowed": "use",
    "min_lot_size": "lot_size",
    "fits_envelope": "setback",
    "row_fits_width": "setback",
}
HOUSING_WORDS = ("dwelling", "unit", "house", "residential", "duplex", "townhouse", "townhome",
                 "apartment", "home")  # fmt: skip


def rule_of(section: str | None, description: str = "") -> str:
    """The rule an approval relaxes: use, lot_size, setback, height, parking or other."""
    s, d = section or "", description.lower()
    if s.startswith("911.") or "use of" in d or "not permitted" in d or "prohibited" in d:
        return "use"
    if s.startswith("914.") or "parking" in d:
        return "parking"
    if s.startswith(("912.", "919.", "926.")):  # accessory structures, signs, street frontage
        return "other"
    if "lot size" in d or "lot area" in d or "per unit" in d or s.startswith("925.01"):
        return "lot_size"
    if "height" in d or "stor" in d or s.startswith(("925.07", "916.02")):
        return "height"
    if "setback" in d or s.startswith(("903.03", "904.", "905.", "925.06")):
        return "setback"
    return "other"


def district_family(district: str | None) -> str:
    base = (district or "").split("-")[0].upper()
    return base if base in RESIDENTIAL_FAMILIES else "other"


def is_housing(request: str | None) -> bool:
    text = request.lower() if isinstance(request, str) else ""
    return any(w in text for w in HOUSING_WORDS)


def _rule(a: dict) -> str:
    if a["type"] == "use_variance":
        return "use"
    return a.get("rule") or rule_of(a.get("section"), a.get("description", ""))


def site_features(ctx: dict) -> dict:
    """The parcel-level inputs, read from a SiteContext (the same facts the report shows)."""
    districts = sorted(
        (z for z in ctx.get("zoning") or [] if z["kind"] == "district"), key=lambda z: -z["share"]
    )
    parcels = ctx.get("parcels") or []
    phys = ctx.get("physical") or {}
    flood = {z["code"] for z in phys.get("flood_zones") or [] if z["share"] > 0}
    return {
        "district": districts[0]["code"] if districts else None,
        "mva": (ctx.get("area") or {}).get("mva_market_type"),
        "lot_sqft": sum(p.get("lot_area_sqft") or 0 for p in parcels) or None,
        "vacant": bool(parcels) and not any(p.get("has_structure") for p in parcels),
        "steep_slope_share": phys.get("steep_slope_share"),
        "undermined_share": phys.get("undermined_share"),
        "flood": bool(flood & {"A", "AE", "FLOODWAY"}),
    }


def features(approvals: list[dict], site: dict, housing: bool = True) -> dict[str, float]:
    """Design row for one hearing. `approvals` = [{"type", "section", "description"?, "rule"?}]
    (the engine passes `rule` from its check; past cases derive it from section and words).
    `site` = site_features(context). Unknown site facts count as 0 (not present)."""
    zba = [a for a in approvals if a["type"] in ZBA_TYPES]
    types = {"variance" if a["type"] == "use_variance" else a["type"] for a in zba}
    rules = {_rule(a) for a in zba}
    lot_sqft = site.get("lot_sqft")
    lot = max(lot_sqft or 0.0, 100.0)
    district, mva = site.get("district"), site.get("mva")
    return {
        "intercept": float(bool(zba)),
        "special_exception_only": float(types == {"special_exception"}),
        "rule_use": float("use" in rules),
        "rule_lot_size": float("lot_size" in rules),
        "rule_setback": float("setback" in rules),
        "rule_height": float("height" in rules),
        "rule_parking": float("parking" in rules),
        "extra_approvals": float(max(len(zba) - 1, 0)),
        "housing": float(housing),
        "residential_district": float(district_family(district) != "other"),
        "strong_market": float(isinstance(mva, str) and mva in STRONG_MARKETS),
        "log_lot_area": math.log(lot) - LOG_LOT_CENTER if lot_sqft else 0.0,
        "vacant_lot": float(bool(site.get("vacant"))),
        "steep_slope": float((site.get("steep_slope_share") or 0) >= STEEP_SHARE),
        "undermined": float((site.get("undermined_share") or 0) > 0),
        "flood_zone": float(bool(site.get("flood"))),
    }


def _load() -> dict | None:
    path = files("navigator_engine") / "config" / "models" / "approval_v1.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


MODEL = _load()


def available() -> bool:
    return MODEL is not None


def row(x: dict[str, float]) -> np.ndarray:
    return np.array([x[f] for f in MODEL["features"]], dtype=float)


def sample(x: dict[str, float], n: int, rng: np.random.Generator) -> np.ndarray:
    """n draws of P(approval at the hearing): coefficients drawn from the posterior."""
    mean = np.asarray(MODEL["coef_mean"], dtype=float)
    cov = np.asarray(MODEL["coef_cov"], dtype=float)
    beta = rng.multivariate_normal(mean, cov, size=n, method="cholesky")
    return 1.0 / (1.0 + np.exp(-(beta @ row(x))))


def basis() -> str:
    d = MODEL["data"]
    return (
        f"model {MODEL['name']}: Bayesian logistic regression on {d['cases']} Zoning Board "
        f"decisions ({d['denials']} denied), {d['from']} to {d['to']}"
    )
