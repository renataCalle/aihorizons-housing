"""Fit the Zoning Board approval model (Bayesian logistic regression) and store it for the engine.

    uv run python -m navigator_research.approval_model     # fit, validate, write config + report

Data: data/clean/zba_cases.parquet (navigator_pipeline.zba), one row per case. A case counts
when the board ruled on a variance or special exception: granted, granted with conditions or
partly granted = 1, denied = 0. Withdrawn cases, "legally nonconforming" findings and cases
with no decision posted are left out (and reported).

Model: logit P(granted) = x'beta with Gaussian priors. The intercepts per approval type are
centred on the engine's former placeholder guesses (variance 70%, special exception 80%), so
the placeholder becomes a real prior that the data updates; other coefficients have
Normal(0, 1) priors. The posterior is found by Newton's method (MAP) with the Laplace
approximation for its covariance, checked against a random-walk Metropolis sampler.

Features come from navigator_engine.approval.features, the same function the engine uses at
prediction time. Output: engine/src/navigator_engine/config/models/approval_v1.json and
docs/approval-model.md.
"""

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from navigator_engine import approval
from navigator_pipeline import scores

REPO = Path(__file__).resolve().parents[3]
CASES = REPO / "data" / "clean" / "zba_cases.parquet"
CONFIG = REPO / "engine" / "src" / "navigator_engine" / "config" / "models" / "approval_v1.json"
REPORT = REPO / "docs" / "approval-model.md"

GRANTED = {"granted", "granted_with_conditions", "partial"}
DECIDED = GRANTED | {"denied"}
TEST_FROM = date(2026, 1, 1)  # hold out 2026 decisions


def logit(p: float) -> float:
    return math.log(p / (1 - p))


# Prior mean and sd per feature, from the old placeholder modes: a variance hearing 70%, a
# special-exception-only hearing 80%; sd 0.5 on the logit scale (about +/- 10 points).
PRIOR = {
    "intercept": (logit(0.70), 0.5),
    "special_exception_only": (logit(0.80) - logit(0.70), 0.5),
}
SLOPE_SD = 1.0


# ---------------------------------------------------------------- data


def approvals_of(case: pd.Series) -> list[dict]:
    reliefs = case["reliefs"] if isinstance(case["reliefs"], (list, np.ndarray)) else []
    if not len(reliefs):
        reliefs = case.get("agenda_reliefs")
        reliefs = reliefs if isinstance(reliefs, (list, np.ndarray)) else []
    return [
        {
            "type": r["type"],
            "section": (list(r["sections"]) or [None])[0],
            "description": r["description"] or "",
        }
        for r in reliefs
    ]


def board_rulings(cases: pd.DataFrame) -> pd.DataFrame:
    """Cases where the board ruled on at least one variance or special exception."""
    keep = [
        i
        for i, c in cases.iterrows()
        if c["outcome"] in DECIDED and any(a["type"] in approval.ZBA_TYPES for a in approvals_of(c))
    ]
    return cases.loc[keep]


def parcel_sites(cases: pd.DataFrame) -> dict[str, dict]:
    """Parcel-level inputs for each case's parcel, from the stored SiteContext (data/scores,
    looked up by parcel ID): the same facts the engine reads when it scores that parcel."""
    store = scores.load()
    out = {}
    for pid in cases["parcel_id"].dropna().unique():
        ctx = store.context(pid)
        if ctx is not None:
            out[pid] = approval.site_features(ctx)
    return out


def design(
    cases: pd.DataFrame, features: tuple[str, ...], sites: dict[str, dict]
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """X, y and the kept cases: board rulings on a variance or special exception whose parcel
    has stored facts. Request variables come from the decision; parcel variables from `sites`."""
    rows, ys, keep = [], [], []
    for i, c in board_rulings(cases).iterrows():
        site = sites.get(c["parcel_id"]) if isinstance(c["parcel_id"], str) else None
        if site is None:
            continue
        x = approval.features(approvals_of(c), site, housing=approval.is_housing(c.get("request")))
        rows.append([x[f] for f in features])
        ys.append(float(c["outcome"] in GRANTED))
        keep.append(i)
    return np.array(rows, float), np.array(ys, float), cases.loc[keep]


def prior(features: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    mu = np.array([PRIOR.get(f, (0.0, SLOPE_SD))[0] for f in features])
    sd = np.array([PRIOR.get(f, (0.0, SLOPE_SD))[1] for f in features])
    return mu, np.diag(1 / sd**2)


def decided_on(cases: pd.DataFrame) -> pd.Series:
    """Decision date, or the hearing date when the decision's date is unreadable (a typo)."""
    return pd.to_datetime(cases["decision_date"].fillna(cases["hearing_date"])).dt.date


# ---------------------------------------------------------------- fit


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-z))


def log_posterior(beta, X, y, mu, prec) -> float:
    z = X @ beta
    ll = np.sum(y * z - np.logaddexp(0, z))
    d = beta - mu
    return float(ll - 0.5 * d @ prec @ d)


def fit_map(X, y, mu, prec, iters: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """Posterior mode (Newton) and Laplace covariance (inverse negative Hessian)."""
    beta = mu.copy()
    for _ in range(iters):
        p = _sigmoid(X @ beta)
        grad = X.T @ (y - p) - prec @ (beta - mu)
        hess = X.T @ (X * (p * (1 - p))[:, None]) + prec
        step = np.linalg.solve(hess, grad)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    p = _sigmoid(X @ beta)
    hess = X.T @ (X * (p * (1 - p))[:, None]) + prec
    return beta, np.linalg.inv(hess)


def metropolis(X, y, mu, prec, start, cov, n=20_000, seed=1) -> np.ndarray:
    """Random-walk Metropolis draws, to check the Laplace approximation."""
    rng = np.random.default_rng(seed)
    d = len(start)
    chol = np.linalg.cholesky(cov * (2.38**2 / d))
    cur, cur_lp, out = start.copy(), log_posterior(start, X, y, mu, prec), []
    for _ in range(n):
        prop = cur + chol @ rng.standard_normal(d)
        lp = log_posterior(prop, X, y, mu, prec)
        if math.log(rng.random()) < lp - cur_lp:
            cur, cur_lp = prop, lp
        out.append(cur.copy())
    return np.array(out[n // 4 :])


# ---------------------------------------------------------------- validation


def log_loss(y, p) -> float:
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y, p) -> float:
    return float(np.mean((p - y) ** 2))


def auc(y, p) -> float | None:
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float(np.mean([(a > b) + 0.5 * (a == b) for a in pos for b in neg]))


def cross_validate(X, y, mu, prec, k: int = 5, seed: int = 3) -> np.ndarray:
    """Out-of-fold predictions (folds stratified by outcome)."""
    rng = np.random.default_rng(seed)
    fold = np.empty(len(y), int)
    for cls in (0, 1):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        fold[idx] = np.arange(len(idx)) % k
    out = np.empty(len(y))
    for f in range(k):
        tr, te = fold != f, fold == f
        beta, _ = fit_map(X[tr], y[tr], mu, prec)
        out[te] = _sigmoid(X[te] @ beta)
    return out


BASE = ("intercept", "special_exception_only")
RULE_TERMS = ("rule_use", "rule_lot_size", "rule_setback", "rule_height", "rule_parking")
PLACE_TERMS = approval.SITE_TERMS
CONDITION_TERMS = approval.CONDITION_TERMS
CANDIDATES = {
    "base (approval type only)": BASE,
    "+ number of approvals": BASE + ("extra_approvals",),
    "+ housing request": BASE + ("housing",),
    "+ rule relaxed": BASE + RULE_TERMS,
    "+ place (district, market, lot)": BASE + PLACE_TERMS,
    "+ site conditions (vacant, slope, undermined, flood)": BASE + CONDITION_TERMS,
    "full": tuple(approval.FEATURES),
}


def evaluate(cases: pd.DataFrame, features: tuple[str, ...], sites: dict) -> dict:
    X, y, kept = design(cases, features, sites)
    mu, prec = prior(features)
    cv = cross_validate(X, y, mu, prec)
    decided = decided_on(kept)
    train = (decided < TEST_FROM).to_numpy()
    out = {"cv_log_loss": log_loss(y, cv), "cv_brier": brier(y, cv), "cv_auc": auc(y, cv)}
    if train.sum() and (~train).sum():
        beta, _ = fit_map(X[train], y[train], mu, prec)
        p = _sigmoid(X[~train] @ beta)
        out |= {
            "test_n": int((~train).sum()),
            "test_log_loss": log_loss(y[~train], p),
            "test_brier": brier(y[~train], p),
        }
    return out


# ---------------------------------------------------------------- main


def calibration(y, p, bins: int = 4) -> list[dict]:
    order = np.argsort(p)
    out = []
    for chunk in np.array_split(order, bins):
        if len(chunk):
            out.append(
                {
                    "n": int(len(chunk)),
                    "predicted": round(float(p[chunk].mean()), 3),
                    "observed": round(float(y[chunk].mean()), 3),
                }
            )
    return out


def main() -> None:
    cases = pd.read_parquet(CASES)
    rulings = board_rulings(cases)
    sites = parcel_sites(rulings)
    no_site = int(sum(not isinstance(p, str) or p not in sites for p in rulings["parcel_id"]))
    fits = {name: evaluate(cases, feats, sites) for name, feats in CANDIDATES.items()}
    # the simplest model unless a richer one lowers cross-validated log loss by > 0.005
    chosen = "base (approval type only)"
    best = min(fits, key=lambda n: fits[n]["cv_log_loss"])
    if fits[best]["cv_log_loss"] < fits[chosen]["cv_log_loss"] - 0.005:
        chosen = best
    features = CANDIDATES[chosen]

    X, y, kept = design(cases, features, sites)
    mu, prec = prior(features)
    beta, cov = fit_map(X, y, mu, prec)
    draws = metropolis(X, y, mu, prec, beta, cov)
    fitted = _sigmoid(X @ beta)
    cv = cross_validate(X, y, mu, prec)
    dates = decided_on(kept)
    left_out = cases[~cases.index.isin(rulings.index)]["outcome"].value_counts().to_dict()
    left_out["ruling but no stored parcel facts"] = no_site

    model = {
        "name": "approval_v1",
        "fitted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "method": "Bayesian logistic regression; MAP (Newton) + Laplace covariance",
        "target": "P(the Zoning Board grants the hearing's variances / special exceptions)",
        "features": list(features),
        "coef_mean": [round(float(b), 6) for b in beta],
        "coef_cov": [[round(float(v), 8) for v in r] for r in cov],
        "prior": {
            f: {"mean": round(float(m), 4), "sd": round(float(1 / math.sqrt(p)), 4)}
            for f, m, p in zip(features, mu, np.diag(prec), strict=True)
        },  # fmt: skip
        "data": {
            "cases": int(len(y)),
            "denials": int((y == 0).sum()),
            "from": str(min(dates)),
            "to": str(max(dates)),
            "left_out": {k: int(v) for k, v in left_out.items()},
        },
        "validation": {
            "chosen": chosen,
            "candidates": fits,
            "cv_calibration": calibration(y, cv),
            "laplace_vs_mcmc_max_abs_diff_mean": round(
                float(np.max(np.abs(draws.mean(0) - beta))), 4
            ),
            "laplace_vs_mcmc_sd_ratio": [
                round(float(a), 3) for a in draws.std(0) / np.sqrt(np.diag(cov))
            ],
        },
        "base_rate": round(float(y.mean()), 4),
    }
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(model, indent=2) + "\n")
    REPORT.write_text(report(model, fitted, y))
    print(f"wrote {CONFIG} ({chosen}; {len(y)} cases, {(y == 0).sum()} denied)")
    print(json.dumps(fits, indent=2))


def report(m: dict, fitted: np.ndarray, y: np.ndarray) -> str:
    d, v = m["data"], m["validation"]
    rows = "\n".join(
        f"| `{f}` | {m['prior'][f]['mean']:+.2f} (sd {m['prior'][f]['sd']:.2f}) | "
        f"{b:+.2f} | {math.sqrt(m['coef_cov'][i][i]):.2f} | {math.exp(b):.2f} |"
        for i, (f, b) in enumerate(zip(m["features"], m["coef_mean"], strict=True))
    )
    cands = "\n".join(
        f"| {n} | {s['cv_log_loss']:.3f} | {s['cv_brier']:.3f} | "
        f"{s['cv_auc'] if s['cv_auc'] is None else round(s['cv_auc'], 3)} | "
        f"{s.get('test_n', '-')} | {s.get('test_log_loss', float('nan')):.3f} |"
        for n, s in v["candidates"].items()
    )
    calib = "\n".join(
        f"| {c['n']} | {c['predicted']:.0%} | {c['observed']:.0%} |" for c in v["cv_calibration"]
    )
    left = ", ".join(f"{k} {n}" for k, n in d["left_out"].items())
    return f"""# Zoning Board approval model ({m["name"]})

Replaces the engine's placeholder approval odds for **variances and special exceptions** with
a Bayesian logistic regression fitted on the board's own decisions. Administrator
exceptions, subdivisions and Council approvals keep their previous basis.

- **Data**: {d["cases"]} board rulings on variances or special exceptions, decided
  {d["from"]} to {d["to"]}; {d["denials"]} denied (base rate {m["base_rate"]:.0%} granted).
  Left out: {left}.
- **Source**: decisions and agendas from the city's ZBA meeting pages
  (`navigator_pipeline.zba_download` -> `navigator_pipeline.zba`), linked to parcels by
  lot-and-block or address.
- **Target**: whether the board granted the hearing's requests (granted, granted with
  conditions or partly granted = yes; denied = no).
- **Method**: {m["method"]}. Priors: centred on the former placeholders (a variance hearing
  70%, a special-exception-only hearing 80%; sd 0.5 on the logit scale); other coefficients
  Normal(0, 1). Laplace vs. Metropolis: largest difference in posterior means
  {v["laplace_vs_mcmc_max_abs_diff_mean"]}, sd ratios {v["laplace_vs_mcmc_sd_ratio"]}.
- **Model chosen**: {v["chosen"]}: the simplest model unless a richer one lowers the 5-fold
  cross-validated log loss by more than 0.005.

## Coefficients (logit scale)

| Feature | Prior mean | Posterior mean | Posterior sd | Odds ratio |
|---|---|---|---|---|
{rows}

## Validation

| Model | CV log loss | CV Brier | CV AUC | 2026 test cases | 2026 test log loss |
|---|---|---|---|---|---|
{cands}

Cross-validated calibration (cases sorted by predicted probability):

| Cases | Predicted | Observed |
|---|---|---|
{calib}

## How the engine uses it

`navigator_engine.approval.features()` builds the same design row for a proposed building:
the approvals its zoning checks need (variance / special exception, and which rule each
relaxes), the district, the lot's URA market type and lot area, and `housing = 1`. Each of the
2,000 Monte Carlo draws samples coefficients from the posterior, so the approval odds carry
the model's uncertainty into the score. Approvals heard at one hearing get one probability,
not a product of independent guesses.

## Caveats

- The data are requests that were filed and decided. Applicants self-select, so odds are
  for "a request like this, once filed"; unusual requests are extrapolation.
- Neighbour opposition is recorded in decisions but not used: it is unknown when screening.
- Few denials: coefficients other than the intercepts are weakly identified and stay close
  to their priors unless the data are clear.
- Fitted {m["fitted_at"][:10]}; refit as new decisions are posted.
"""


if __name__ == "__main__":
    main()
