"""
Layer 3 — Threshold (hard default) cascade — the classic domino model.

A bank defaults the instant its remaining equity drops below zero. When a bank
defaults, each of its creditors immediately absorbs the full exposure they had
to it. Creditors that then cross the zero-equity threshold default in the next
round. This continues until a round produces no new defaults. It is the
worst-case / most visually dramatic contagion model.
"""
from __future__ import annotations

import numpy as np


def run_threshold_cascade(
    exposure_matrix: np.ndarray,   # exposure[i][j] = bank i lent to bank j
    equity: np.ndarray,
    bank_ids: list[str],
    shocked_bank_idx: int,
    shock_magnitude: float,
) -> list[dict]:
    """
    Returns a per-round history. Each round dict:
        {step, defaulted_this_round, all_defaulted, distress_levels,
         equity_remaining, total_system_loss, total_equity_destroyed,
         simulation_complete}

    distress_levels are reported as fraction of equity lost (capped at 1.0) so
    the same frontend animation/color logic applies.
    """
    exposure_matrix = np.asarray(exposure_matrix, dtype=float)
    equity = np.asarray(equity, dtype=float)
    n = len(bank_ids)
    total_equity = float(equity.sum()) if equity.sum() > 0 else 1.0

    equity_remaining = equity.copy()
    defaulted = np.zeros(n, dtype=bool)

    # Apply the initial shock.
    if 0 <= shocked_bank_idx < n:
        equity_remaining[shocked_bank_idx] -= float(shock_magnitude) * equity[shocked_bank_idx]

    history: list[dict] = []

    def distress_of() -> dict[str, float]:
        out = {}
        for i in range(n):
            if defaulted[i]:
                out[bank_ids[i]] = 1.0
            else:
                lost = (equity[i] - equity_remaining[i]) / max(equity[i], 1.0)
                out[bank_ids[i]] = float(np.clip(lost, 0.0, 1.0))
        return out

    def record(step_idx: int, defaulted_this_round: list[str], complete: bool) -> None:
        destroyed = float(np.sum(equity[defaulted]))
        history.append(
            {
                "step": step_idx,
                "defaulted_this_round": defaulted_this_round,
                "all_defaulted": [bank_ids[i] for i in range(n) if defaulted[i]],
                "distress_levels": distress_of(),
                "equity_remaining": {
                    bank_ids[i]: float(max(0.0, equity_remaining[i])) for i in range(n)
                },
                "total_system_loss": destroyed / total_equity,
                "total_equity_destroyed": destroyed,
                "simulation_complete": complete,
            }
        )

    # Round 0: detect the directly-shocked defaults.
    newly = [
        bank_ids[i]
        for i in range(n)
        if equity_remaining[i] <= 0 and not defaulted[i]
    ]
    for i in range(n):
        if equity_remaining[i] <= 0:
            defaulted[i] = True
    record(0, newly, complete=(len(newly) == 0))

    step_idx = 0
    while newly:
        step_idx += 1
        # Apply losses from this round's defaulters to their creditors.
        for j_id in newly:
            j = bank_ids.index(j_id)
            for i in range(n):
                if defaulted[i]:
                    continue
                loss = exposure_matrix[i, j]  # creditor i loses what it lent to j
                equity_remaining[i] -= loss

        newly = [
            bank_ids[i]
            for i in range(n)
            if equity_remaining[i] <= 0 and not defaulted[i]
        ]
        for i in range(n):
            if equity_remaining[i] <= 0 and not defaulted[i]:
                defaulted[i] = True

        record(step_idx, newly, complete=(len(newly) == 0))

    if history:
        history[-1]["simulation_complete"] = True
    return history
