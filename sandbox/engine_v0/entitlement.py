"""Entitlement model v0: relief items -> P(approval) and months to decision (samples).

Two rungs are measured from City Council zoning legislation (Legistar, 2000-2026): approvals
are Beta(1 + passed, 1 + failed) posteriors and durations are the observed intro-to-passage
days. They are optimistic: cases withdrawn before a vote are not visible. Zoning Board rungs
are PLACEHOLDER priors (spec v0 fallback) until ZBA decisions can be extracted.
"""

import numpy as np

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


def sample(relief: list[dict], n: int, rng: np.random.Generator) -> dict:
    """Joint samples of P(approval) and hearing months for a program's relief items.

    Items are treated as independent (P multiplies). Items before the same body (ZBA) are
    heard together, so months take the max within a body and add across bodies.
    """
    p = np.ones(n)
    by_body: dict[str, np.ndarray] = {}
    sources = []
    for item in relief:
        t = item["type"]
        if t in RUNGS:
            kind, params, months, src = RUNGS[t]
            if kind == "beta":
                p *= rng.beta(1 + params[0], 1 + params[1], n)
            else:
                p *= rng.triangular(params[0], params[1], params[2], n)
            body = "zba" if t in ("special_exception", "variance", "use_variance") else t
            m = rng.triangular(*months, n)
            by_body[body] = np.maximum(by_body.get(body, 0), m)
            sources.append(f"{t}: {src}")
        elif t in PROCEDURAL:
            by_body[t] = np.maximum(by_body.get(t, 0), rng.triangular(*PROCEDURAL[t], n))
    months = sum(by_body.values()) if by_body else np.zeros(n)
    return {"p": p, "months": months, "sources": sources}
