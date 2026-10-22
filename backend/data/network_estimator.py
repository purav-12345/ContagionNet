"""
Layer 1 — Maximum Entropy (RAS / Blien-Graef) bilateral exposure estimator.

In reality banks do not publish who they lend to. Given only each bank's total
interbank lending (row sums) and total interbank borrowing (column sums), the
maximum-entropy estimate is the most likely bilateral matrix consistent with
those margins. This is the standard central-bank methodology (ECB, Bank of
England). Implemented via iterative proportional fitting (RAS).
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("data.estimator")


def maximum_entropy_estimation(
    interbank_assets: np.ndarray,        # (n,) how much each bank lends in total
    interbank_liabilities: np.ndarray,   # (n,) how much each bank borrows in total
    max_iter: int = 10000,
    tolerance: float = 1e-8,
) -> np.ndarray:
    """
    RAS iterative proportional fitting.

    Returns:
        X: (n x n) bilateral exposure matrix where X[i][j] = amount bank i
        lent to bank j. Diagonal is zero (no self-lending). Row sums match
        interbank_assets; column sums match interbank_liabilities.
    """
    interbank_assets = np.asarray(interbank_assets, dtype=float)
    interbank_liabilities = np.asarray(interbank_liabilities, dtype=float)
    n = len(interbank_assets)
    if n < 2:
        return np.zeros((n, n))

    # Normalize so total lending == total borrowing (required for RAS feasibility).
    total = (interbank_assets.sum() + interbank_liabilities.sum()) / 2.0
    assets_norm = interbank_assets * total / max(interbank_assets.sum(), 1e-10)
    liab_norm = interbank_liabilities * total / max(interbank_liabilities.sum(), 1e-10)

    # Better-than-uniform starting point: outer product of margins (max-entropy
    # prior), scaled to the asset row totals, with diagonal removed.
    outer = np.outer(assets_norm, liab_norm)
    np.fill_diagonal(outer, 0.0)
    row_sum = outer.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1.0
    X = outer / row_sum * assets_norm[:, np.newaxis]
    np.fill_diagonal(X, 0.0)

    for iteration in range(max_iter):
        X_prev = X.copy()

        # Scale rows to match interbank_assets.
        row_sums = X.sum(axis=1)
        row_sums[row_sums == 0] = 1.0
        X = X * (assets_norm / row_sums)[:, np.newaxis]
        np.fill_diagonal(X, 0.0)

        # Scale columns to match interbank_liabilities.
        col_sums = X.sum(axis=0)
        col_sums[col_sums == 0] = 1.0
        X = X * (liab_norm / col_sums)[np.newaxis, :]
        np.fill_diagonal(X, 0.0)

        if np.max(np.abs(X - X_prev)) < tolerance:
            logger.info("RAS converged in %d iterations", iteration + 1)
            break
    else:
        logger.warning("RAS hit max_iter=%d without full convergence", max_iter)

    return X


def build_exposure_matrix(banks: list[dict]) -> np.ndarray:
    """
    Build the (n x n) bilateral exposure matrix from a list of bank dicts using
    each bank's interbank_assets (row totals) and interbank_liabilities
    (column totals).
    """
    interbank_assets = np.array([b["interbank_assets"] for b in banks], dtype=float)
    interbank_liabilities = np.array(
        [b["interbank_liabilities"] for b in banks], dtype=float
    )
    return maximum_entropy_estimation(interbank_assets, interbank_liabilities)
