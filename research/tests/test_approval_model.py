"""The approval model's fitting routine recovers known coefficients from simulated data."""

import numpy as np

from navigator_research import approval_model as am


def test_map_and_laplace_recover_simulated_coefficients() -> None:
    rng = np.random.default_rng(0)
    n = 4_000
    X = np.column_stack([np.ones(n), rng.integers(0, 2, n), rng.normal(size=n)])
    beta = np.array([1.2, 0.6, -0.8])
    y = (rng.random(n) < 1 / (1 + np.exp(-(X @ beta)))).astype(float)
    mu, prec = np.zeros(3), np.eye(3) / 10.0**2  # weak prior
    est, cov = am.fit_map(X, y, mu, prec)
    assert np.all(np.abs(est - beta) < 3 * np.sqrt(np.diag(cov)))
    draws = am.metropolis(X, y, mu, prec, est, cov, n=4_000)
    assert np.all(np.abs(draws.mean(0) - est) < 0.5 * np.sqrt(np.diag(cov)) + 0.02)


def test_a_strong_prior_holds_with_little_data() -> None:
    X, y = np.ones((5, 1)), np.array([1.0, 1, 1, 1, 0])
    est, _ = am.fit_map(X, y, np.array([am.logit(0.7)]), np.eye(1) / 0.1**2)
    assert abs(est[0] - am.logit(0.7)) < 0.1


def test_metrics() -> None:
    y, p = np.array([1.0, 0, 1]), np.array([0.9, 0.2, 0.6])
    assert am.brier(y, p) < 0.1 and am.auc(y, p) == 1.0
    assert am.log_loss(y, p) > 0
