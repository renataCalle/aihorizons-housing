"""Every judgment the v0 engine makes, in one place (spec: SiteAnalysis.assumptions).

Each assumption has a mode and a (low, high) range used by the Monte Carlo, a unit, and a
`source`. Anything marked PLACEHOLDER is not derived from data: it is a starting value to be
replaced by a local benchmark or by calibration, and the report says so. Users override any
editable key (spec: Adjust drawer), e.g. `--set hard_cost_psf=275`.
"""

from dataclasses import dataclass

PLACEHOLDER = "PLACEHOLDER - replace with local benchmark"
UNCALIBRATED = "PLACEHOLDER - set in validation"


@dataclass(frozen=True)
class Assumption:
    key: str
    label: str
    value: float
    low: float
    high: float
    unit: str
    source: str
    editable: bool = True


_ALL = [
    # ---- construction economics
    Assumption("hard_cost_psf", "Hard cost per gross sq ft", 250, 200, 320, "$/sf", PLACEHOLDER),
    Assumption(
        "soft_cost_share", "Soft costs as share of hard", 0.20, 0.15, 0.25, "share", PLACEHOLDER
    ),
    Assumption(
        "contingency_share", "Contingency on hard + soft", 0.07, 0.05, 0.10, "share", PLACEHOLDER
    ),
    Assumption("construction_months", "Construction duration", 12, 9, 16, "months", PLACEHOLDER),
    Assumption(
        "carry_rate", "Annual carrying cost of capital", 0.09, 0.07, 0.11, "rate/yr", PLACEHOLDER
    ),
    Assumption(
        "target_margin", "Target margin on cost", 0.15, 0.15, 0.15, "share", "developer input"
    ),
    # ---- revenue
    Assumption(
        "new_build_premium",
        "New construction price premium over resale comps",
        0.25,
        0.10,
        0.40,
        "share",
        PLACEHOLDER,
    ),
    Assumption("cap_rate", "Cap rate for rental exit", 0.065, 0.055, 0.075, "rate", PLACEHOLDER),
    Assumption(
        "opex_ratio",
        "Operating expenses + vacancy, share of gross rent",
        0.40,
        0.35,
        0.45,
        "share",
        PLACEHOLDER,
    ),
    # ---- schedule
    Assumption(
        "permit_review_months",
        "Building permit review (PLI)",
        3,
        2,
        5,
        "months",
        "PLACEHOLDER - PLI data has issue dates only",
    ),
    # ---- score (spec: decay constants are set in validation, not by hand)
    Assumption(
        "score_time_scale_months",
        "Time factor: e-folding months",
        18,
        18,
        18,
        "months",
        UNCALIBRATED,
        editable=False,
    ),
    Assumption(
        "score_land_full_ratio",
        "Land headroom: max land price / land price that earns full points",
        1.5,
        1.5,
        1.5,
        "ratio",
        UNCALIBRATED,
        editable=False,
    ),
    Assumption(
        "score_premium_scale",
        "Cost factor: premium share that zeroes the score",
        0.30,
        0.30,
        0.30,
        "share",
        UNCALIBRATED,
        editable=False,
    ),
]

ASSUMPTIONS: dict[str, Assumption] = {a.key: a for a in _ALL}


def resolve(overrides: dict[str, float] | None = None) -> dict[str, Assumption]:
    """Assumptions with user overrides applied (an override pins low = mode = high)."""
    out = dict(ASSUMPTIONS)
    for k, v in (overrides or {}).items():
        if k not in out:
            raise KeyError(f"unknown assumption {k!r}; valid: {sorted(out)}")
        a = out[k]
        if not a.editable:
            raise KeyError(f"{k!r} is not editable")
        out[k] = Assumption(a.key, a.label, v, v, v, a.unit, "user override", True)
    return out
