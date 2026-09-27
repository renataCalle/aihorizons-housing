"""Entitlement model v0: relief items -> P(approval) and months to decision (samples).

Two rungs are measured from City Council zoning legislation (Legistar, 2000-2026): approvals
are Beta(1 + passed, 1 + failed) posteriors and durations are the observed intro-to-passage
days. They are optimistic: cases withdrawn before a vote are not visible. Zoning Board
approvals (variances, special exceptions) use the fitted approval model when its config is
present (navigator_engine.approval); their RUNGS entries remain the prior and the fallback.
Administrator exceptions and subdivisions stay PLACEHOLDER priors: no decision data.
"""

import numpy as np

from navigator_engine import approval

DAYS_PER_MONTH = 30.44

# rung -> (kind, params, months (low, mode, high), source)
RUNGS = {
    "administrator_exception": ("tri", (0.80, 0.90, 0.97), (0.5, 1.5, 3), "PLACEHOLDER prior"),
    "special_exception": ("tri", (0.65, 0.80, 0.92), (2, 3.5, 6), "PLACEHOLDER prior (ZBA)"),
    "variance": ("tri", (0.50, 0.70, 0.85), (2, 4, 7), "PLACEHOLDER prior (ZBA)"),
    "use_variance": ("tri", (0.20, 0.40, 0.60), (3, 5, 9), "PLACEHOLDER prior (ZBA)"),
    "subdivision": ("tri", (0.85, 0.95, 0.99), (1, 2, 4), "PLACEHOLDER prior"),
    "conditional_use": (
        "beta",
        (27, 2),
        (44 / DAYS_PER_MONTH, 60 / DAYS_PER_MONTH, 162 / DAYS_PER_MONTH),
        "measured: council, 27 of 29 passed; days p10/p50/p90 44/60/162",
    ),
    "rezoning": (
        "beta",
        (91, 10),
        (41 / DAYS_PER_MONTH, 79 / DAYS_PER_MONTH, 225 / DAYS_PER_MONTH),
        "measured: council, 91 of 101 passed; days p10/p50/p90 41/79/225",
    ),
}
# Procedures that add time but are not discretionary approvals
PROCEDURAL = {"site_investigation": (1, 2, 3), "prohibited_without_study": (6, 12, 18)}


def sample(relief: list[dict], n: int, rng: np.random.Generator, site: dict | None = None) -> dict:
    """Joint samples of P(approval) and hearing months for a program's relief items.
    `site` = approval.site_features(context): the parcel-level inputs of the approval model.

    Variances and special exceptions go to one Zoning Board hearing: with the fitted approval
    model they get one probability for the hearing (navigator_engine.approval); without it,
    one placeholder per item. Other approvals are treated as independent (P multiplies).
    Items before the same body are heard together, so months take the max within a body and
    add across bodies.
    """
    p = np.ones(n)
    by_body: dict[str, np.ndarray] = {}
    sources = []
    hearing = [i for i in relief if i["type"] in approval.ZBA_TYPES]
    modelled = bool(hearing) and approval.available()
    if modelled:
        site = site or {}
        x = approval.features(
            [
                {
                    "type": i["type"],
                    "section": i.get("section"),
                    "rule": approval.CHECK_RULES.get(i.get("check")),
                }
                for i in hearing
            ],
            site,
        )
        p *= approval.sample(x, n, rng)
        sources.append(f"zoning board hearing: {approval.basis()}")
    for item in relief:
        t = item["type"]
        if t in RUNGS:
            kind, params, months, src = RUNGS[t]
            if not (modelled and t in approval.ZBA_TYPES):
                if kind == "beta":
                    p *= rng.beta(1 + params[0], 1 + params[1], n)
                else:
                    p *= rng.triangular(params[0], params[1], params[2], n)
                sources.append(f"{t}: {src}")
            body = "zba" if t in approval.ZBA_TYPES else t
            m = rng.triangular(*months, n)
            by_body[body] = np.maximum(by_body.get(body, 0), m)
        elif t in PROCEDURAL:
            by_body[t] = np.maximum(by_body.get(t, 0), rng.triangular(*PROCEDURAL[t], n))
    months = sum(by_body.values()) if by_body else np.zeros(n)
    return {"p": p, "months": months, "sources": sources}
