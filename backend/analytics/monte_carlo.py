"""
Layer 4 — Monte Carlo systemic Value-at-Risk.

Draws thousands of correlated external-asset shock vectors from a multivariate
normal distribution, runs DebtRank for each, and builds the probability
distribution of total system loss. Reports expected loss, VaR(95/99), CVaR(95),
and the probability of a systemic crisis.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np

from engine.debtrank import debtrank_total_loss

logger = logging.getLogger("analytics.montecarlo")

CRISIS_THRESHOLD = 0.20  # loss fraction that constitutes a systemic crisis


def _default_correlation_matrix(n: int, base_corr: float = 0.3, seed: int = 17) -> np.ndarray:
    """
    Realistic correlation matrix: every pair shares a systemic factor (base_corr)
    plus a small idiosyncratic perturbation. Projected to the nearest valid
    (positive semi-definite) correlation matrix.
    """
    rng = np.random.default_rng(seed)
    C = np.full((n, n), base_corr)
    np.fill_diagonal(C, 1.0)
    perturb = rng.normal(0.0, 0.05, size=(n, n))
    perturb = (perturb + perturb.T) / 2
    np.fill_diagonal(perturb, 0.0)
    C = np.clip(C + perturb, -0.99, 0.99)
    np.fill_diagonal(C, 1.0)
    # Make PSD via eigenvalue clipping.
    vals, vecs = np.linalg.eigh(C)
    vals = np.clip(vals, 1e-6, None)
    C = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.diag(C))
    C = C / np.outer(d, d)
    return C


def run_monte_carlo(
    V: np.ndarray,
    equity: np.ndarray,
    bank_ids: list[str],
    n_simulations: int = 2000,
    correlation_matrix: np.ndarray | None = None,
    shock_mean: float = 0.05,
    shock_std: float = 0.15,
    seed: int | None = None,
) -> dict:
    """
    Run the Monte Carlo experiment and return the loss distribution + stats.

    seed defaults to None -> a fresh entropy-seeded RNG every call, so each run
    is a genuinely new random draw (a real stochastic Monte Carlo). Pass an int
    only if you want a reproducible run.
    """
    n = len(bank_ids)
    rng = np.random.default_rng(seed)

    if correlation_matrix is None:
        correlation_matrix = _default_correlation_matrix(n)

    cov = correlation_matrix * (shock_std ** 2)
    mean_vec = np.full(n, shock_mean)

    try:
        chol = np.linalg.cholesky(cov + 1e-10 * np.eye(n))
    except np.linalg.LinAlgError:
        chol = np.diag(np.full(n, shock_std))

    losses = np.empty(n_simulations, dtype=float)
    for s in range(n_simulations):
        z = rng.standard_normal(n)
        shock = mean_vec + chol @ z
        shock = np.clip(shock, 0.0, 1.0)  # only adverse shocks; cap at full loss
        losses[s] = debtrank_total_loss(V, equity, shock)

    losses_sorted = np.sort(losses)
    expected_loss = float(losses.mean())
    var_95 = float(np.percentile(losses, 95))
    var_99 = float(np.percentile(losses, 99))
    tail = losses_sorted[losses_sorted >= var_95]
    cvar_95 = float(tail.mean()) if tail.size else var_95
    prob_crisis = float(np.mean(losses > CRISIS_THRESHOLD))

    counts, bin_edges = np.histogram(losses, bins=50, range=(0.0, max(1.0, losses.max())))

    logger.info(
        "Monte Carlo: %d sims, E[loss]=%.3f, VaR95=%.3f, VaR99=%.3f, P(crisis)=%.3f",
        n_simulations, expected_loss, var_95, var_99, prob_crisis,
    )

    return {
        "loss_distribution": losses.tolist(),
        "expected_loss": expected_loss,
        "var_95": var_95,
        "var_99": var_99,
        "cvar_95": cvar_95,
        "probability_crisis": prob_crisis,
        "crisis_threshold": CRISIS_THRESHOLD,
        "n_simulations": n_simulations,
        "min_loss": float(losses.min()),
        "max_loss": float(losses.max()),
        "median_loss": float(np.median(losses)),
        "shock_mean": float(shock_mean),
        "shock_std": float(shock_std),
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "histogram": {
            "bins": bin_edges.tolist(),
            "counts": counts.tolist(),
        },
    }
