"""
Layer 3 — Eisenberg-Noe clearing (Management Science, 2001).

Models the legal bankruptcy settlement process via the Fictitious Default
Algorithm. Given a nominal liability matrix L (L[i][j] = amount bank i owes
bank j) and external assets, it computes the clearing payment vector p* — the
amount each bank actually pays — under three principles:
  * limited liability (pay at most what you have),
  * absolute priority of debt over equity,
  * proportional sharing among creditors.
"""
from __future__ import annotations

import numpy as np


def exposure_to_liability_matrix(exposure_matrix: np.ndarray) -> np.ndarray:
    """
    Convert an exposure matrix (exposure[i][j] = i lent to j, so j owes i) into
    a liability matrix L where L[i][j] = amount bank i owes bank j.
    j owes i exactly what i lent to j, so L = exposure.T.
    """
    return np.asarray(exposure_matrix, dtype=float).T.copy()


def run_eisenberg_noe(
    L: np.ndarray,
    external_assets: np.ndarray,
    bank_ids: list[str],
    max_iter: int = 10000,
    tolerance: float = 1e-10,
) -> dict:
    """
    Solve the Eisenberg-Noe clearing problem.

    Args:
        L: (n x n) nominal liability matrix, L[i][j] = bank i owes bank j.
        external_assets: (n,) external (non-interbank) assets per bank.
        bank_ids: ordered list of bank id strings.
    """
    L = np.asarray(L, dtype=float)
    external_assets = np.asarray(external_assets, dtype=float)
    n = len(bank_ids)

    p_bar = L.sum(axis=1)  # total obligations of each bank
    # Relative liability matrix Pi[i][j] = share of i's debt owed to j.
    with np.errstate(divide="ignore", invalid="ignore"):
        Pi = np.where(p_bar[:, None] > 0, L / p_bar[:, None], 0.0)

    p = p_bar.copy()  # start: everyone pays in full
    steps: list[dict] = []

    for iteration in range(max_iter):
        # Available resources of bank i = external assets + payments received.
        inflow = Pi.T @ p
        p_new = np.minimum(p_bar, external_assets + inflow)
        p_new = np.maximum(p_new, 0.0)

        defaulted = [bank_ids[i] for i in range(n) if p_new[i] < p_bar[i] - 1e-9]
        steps.append(
            {
                "iteration": iteration,
                "total_payments": float(p_new.sum()),
                "num_defaulted": len(defaulted),
                "defaulted_banks": defaulted,
            }
        )

        if np.max(np.abs(p_new - p)) < tolerance:
            p = p_new
            break
        p = p_new

    inflow = Pi.T @ p
    equity_values = external_assets + inflow - p  # residual equity after clearing
    with np.errstate(divide="ignore", invalid="ignore"):
        recovery = np.where(p_bar > 0, p / p_bar, 1.0)
    defaulted_banks = [bank_ids[i] for i in range(n) if p[i] < p_bar[i] - 1e-9]
    total_shortfall = float(np.sum(p_bar - p))

    return {
        "clearing_payments": {bank_ids[i]: float(p[i]) for i in range(n)},
        "nominal_obligations": {bank_ids[i]: float(p_bar[i]) for i in range(n)},
        "equity_values": {bank_ids[i]: float(equity_values[i]) for i in range(n)},
        "defaulted_banks": defaulted_banks,
        "recovery_rates": {bank_ids[i]: float(recovery[i]) for i in range(n)},
        "total_shortfall": total_shortfall,
        "simulation_steps": steps,
    }


def run_eisenberg_noe_shocked(
    exposure_matrix: np.ndarray,
    external_assets: np.ndarray,
    bank_ids: list[str],
    shocked_bank_idx: int,
    shock_magnitude: float,
) -> dict:
    """
    Apply an external-asset shock to one bank, then run clearing. Returns the
    standard EN result plus a per-step history shaped like DebtRank steps so the
    frontend can animate it through the same channel.
    """
    external = np.asarray(external_assets, dtype=float).copy()
    n = len(bank_ids)
    if 0 <= shocked_bank_idx < n:
        external[shocked_bank_idx] *= max(0.0, 1.0 - float(shock_magnitude))

    L = exposure_to_liability_matrix(exposure_matrix)
    result = run_eisenberg_noe(L, external, bank_ids)

    # Build DebtRank-shaped steps from recovery rates so the WS animation can
    # render EN too: distress = 1 - recovery rate.
    p_bar = L.sum(axis=1)
    total_equity = float(np.sum(np.maximum(external_assets, 0.0)) + 1e-9)
    recovery = np.array([result["recovery_rates"][bid] for bid in bank_ids])
    distress = np.clip(1.0 - recovery, 0.0, 1.0)

    final_loss = float(
        np.sum([max(0.0, -result["equity_values"][bid]) for bid in bank_ids])
        / total_equity
    )

    animated_steps = []
    raw_steps = result["simulation_steps"] or [{"iteration": 0, "defaulted_banks": []}]
    for s in raw_steps:
        defaulted_set = set(s["defaulted_banks"])
        animated_steps.append(
            {
                "step": s["iteration"],
                "distress_levels": {
                    bid: (float(distress[k]) if bid in defaulted_set else 0.0)
                    for k, bid in enumerate(bank_ids)
                },
                "defaulted_banks": s["defaulted_banks"],
            }
        )
    result["animated_steps"] = animated_steps
    result["final_distress"] = {bid: float(distress[k]) for k, bid in enumerate(bank_ids)}
    result["total_system_loss"] = min(1.0, max(final_loss, len(result["defaulted_banks"]) / n))
    result["num_defaults"] = len(result["defaulted_banks"])
    return result
