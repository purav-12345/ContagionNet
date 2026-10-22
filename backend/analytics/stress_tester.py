"""
Layer 4 — Stress testing engine.

Runs every single-node shock scenario, builds the Systemic Importance Ranking
(SIR), and computes the full N×N contagion heatmap.
"""
from __future__ import annotations

import logging

import numpy as np

from engine.debtrank import debtrank_summary, run_debtrank

logger = logging.getLogger("analytics.stress")


def run_all_single_shock_scenarios(
    V: np.ndarray,
    exposure_matrix: np.ndarray,
    equity: np.ndarray,
    bank_ids: list[str],
    bank_names: dict[str, str],
    shock_magnitude: float = 1.0,
) -> list[dict]:
    """
    Trigger each bank's failure one at a time, run DebtRank, record results.
    Returns scenarios sorted by total_system_loss (descending).
    """
    scenarios: list[dict] = []
    n = len(bank_ids)
    for idx in range(n):
        history = run_debtrank(V, equity, bank_ids, idx, shock_magnitude)
        summary = debtrank_summary(history, equity)
        scenarios.append(
            {
                "shocked_bank_id": bank_ids[idx],
                "shocked_bank_name": bank_names.get(bank_ids[idx], bank_ids[idx]),
                "total_system_loss": summary["total_system_loss"],
                "num_defaults": summary["num_defaults"],
                "contagion_rounds": summary["contagion_rounds"],
                "systemic_importance_score": summary["total_system_loss"],
                "affected_banks": summary["affected_banks"],
            }
        )

    scenarios.sort(key=lambda s: s["total_system_loss"], reverse=True)
    logger.info("Ran %d single-node shock scenarios", n)
    return scenarios


def compute_systemic_importance_ranking(scenarios: list[dict]) -> list[dict]:
    """Rank scenarios by SIR score; rank 1 = most dangerous."""
    ranked = sorted(
        scenarios, key=lambda s: s["systemic_importance_score"], reverse=True
    )
    out = []
    for rank, s in enumerate(ranked, start=1):
        out.append(
            {
                "rank": rank,
                "bank_id": s["shocked_bank_id"],
                "bank_name": s["shocked_bank_name"],
                "systemic_importance_score": s["systemic_importance_score"],
                "num_defaults_caused": s["num_defaults"],
                "total_system_loss": s["total_system_loss"],
                "contagion_rounds": s["contagion_rounds"],
            }
        )
    return out


def compute_contagion_heatmap(
    V: np.ndarray,
    equity: np.ndarray,
    bank_ids: list[str],
    bank_names: dict[str, str],
) -> dict:
    """
    matrix[i][j] = fraction of bank i's equity lost when bank j is the initial
    failure (full default of j). Computed by running DebtRank shocked at j and
    reading final distress of i.
    """
    n = len(bank_ids)
    matrix = [[0.0] * n for _ in range(n)]
    for j in range(n):
        history = run_debtrank(V, equity, bank_ids, j, 1.0)
        final = history[-1].distress_levels
        for i in range(n):
            matrix[i][j] = float(final[bank_ids[i]])
    logger.info("Computed %dx%d contagion heatmap", n, n)
    return {
        "matrix": matrix,
        "bank_ids": list(bank_ids),
        "bank_names": [bank_names.get(b, b) for b in bank_ids],
    }
