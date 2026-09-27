# Zoning Board approval model (approval_v1)

Replaces the engine's placeholder approval odds for **variances and special exceptions** with
a Bayesian logistic regression fitted on the board's own decisions. Administrator
exceptions, subdivisions and Council approvals keep their previous basis.

- **Data**: 202 board rulings on variances or special exceptions, decided
  2025-02-05 to 2026-08-28; 28 denied (base rate 86% granted).
  Left out: no_decision_posted 74, nonconforming 8, unknown 4, denied 2, granted_with_conditions 1, partial 1, granted 1, no_relief_needed 1, ruling but no stored parcel facts 1.
- **Source**: decisions and agendas from the city's ZBA meeting pages
  (`navigator_pipeline.zba_download` -> `navigator_pipeline.zba`), linked to parcels by
  lot-and-block or address.
- **Target**: whether the board granted the hearing's requests (granted, granted with
  conditions or partly granted = yes; denied = no).
- **Method**: Bayesian logistic regression; MAP (Newton) + Laplace covariance. Priors: centred on the former placeholders (a variance hearing
  70%, a special-exception-only hearing 80%; sd 0.5 on the logit scale); other coefficients
  Normal(0, 1). Laplace vs. Metropolis: largest difference in posterior means
  0.1075, sd ratios [0.987, 0.966, 1.031, 1.03, 1.03, 1.093].
- **Model chosen**: + site conditions (vacant, slope, undermined, flood): the simplest model unless a richer one lowers the 5-fold
  cross-validated log loss by more than 0.005.

## Coefficients (logit scale)

| Feature | Prior mean | Posterior mean | Posterior sd | Odds ratio |
|---|---|---|---|---|
| `intercept` | +0.85 (sd 0.50) | +1.36 | 0.22 | 3.91 |
| `special_exception_only` | +0.54 (sd 0.50) | +0.85 | 0.39 | 2.35 |
| `vacant_lot` | +0.00 (sd 1.00) | +0.83 | 0.50 | 2.30 |
| `steep_slope` | +0.00 (sd 1.00) | +0.95 | 0.54 | 2.57 |
| `undermined` | +0.00 (sd 1.00) | -0.07 | 0.45 | 0.94 |
| `flood_zone` | +0.00 (sd 1.00) | -0.52 | 0.61 | 0.60 |

## Validation

| Model | CV log loss | CV Brier | CV AUC | 2026 test cases | 2026 test log loss |
|---|---|---|---|---|---|
| base (approval type only) | 0.398 | 0.118 | 0.545 | 91 | 0.480 |
| + number of approvals | 0.399 | 0.119 | 0.553 | 91 | 0.480 |
| + housing request | 0.396 | 0.118 | 0.594 | 91 | 0.475 |
| + rule relaxed | 0.401 | 0.119 | 0.557 | 91 | 0.477 |
| + place (district, market, lot) | 0.401 | 0.120 | 0.578 | 91 | 0.542 |
| + site conditions (vacant, slope, undermined, flood) | 0.389 | 0.117 | 0.608 | 91 | 0.462 |
| full | 0.398 | 0.119 | 0.628 | 91 | 0.509 |

Cross-validated calibration (cases sorted by predicted probability):

| Cases | Predicted | Observed |
|---|---|---|
| 51 | 77% | 84% |
| 51 | 80% | 72% |
| 50 | 89% | 96% |
| 50 | 93% | 92% |

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
- Fitted 2026-09-27; refit as new decisions are posted.
