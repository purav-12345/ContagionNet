"""
Layer 3 — DebtRank (Battiston et al., Nature Scientific Reports, 2012).

THE MOST CRITICAL FILE. DebtRank models distress as a continuous variable
h_i(t) in [0, 1]. The defining feature — and the part everyone gets wrong — is
the "propagate once" state machine: a bank that is DISTRESSED propagates its
distress to its creditors exactly once, then becomes INACTIVE and never
propagates again. This prevents the double-counting that the naive repeated-
matrix-multiplication implementation produces.

State machine, executed each iteration:
  A. Propagation: every currently-DISTRESSED bank i adds V[j][i]*h[i] to every
     non-INACTIVE creditor j (capped at 1.0). Note index order: V[j][i] = how
     much of creditor j's equity is at risk from distressed debtor i.
  B. Transitions (computed from the PREVIOUS step's states, applied together):
       - UNDISTRESSED bank with new distress > 0  -> DISTRESSED
       - bank that was DISTRESSED this round       -> INACTIVE
  C. Record the full step.
  D. Stop when no bank is DISTRESSED.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np


class BankStatus(IntEnum):
    UNDISTRESSED = 0
    DISTRESSED = 1
    INACTIVE = 2


_STATUS_NAME = {
    BankStatus.UNDISTRESSED: "UNDISTRESSED",
    BankStatus.DISTRESSED: "DISTRESSED",
    BankStatus.INACTIVE: "INACTIVE",
}


@dataclass
class SimulationStep:
    step: int
    distress_levels: dict[str, float]    # bank_id -> h value (0.0 to 1.0)
    states: dict[str, str]               # bank_id -> status name
    equity_remaining: dict[str, float]   # bank_id -> fraction of equity remaining
    total_system_loss: float             # fraction of total system equity destroyed
    new_defaults: list[str]              # bank ids that crossed h>=1.0 this step
    newly_distressed: list[str]          # bank ids that became distressed this step
    simulation_complete: bool


def run_debtrank(
    V: np.ndarray,
    equity: np.ndarray,
    bank_ids: list[str],
    shocked_bank_idx: int,
    shock_magnitude: float,
    max_steps: int | None = None,
) -> list[SimulationStep]:
    """Single-bank initial shock. See module docstring for the state machine."""
    n = len(bank_ids)
    shock_vector = np.zeros(n, dtype=float)
    if 0 <= shocked_bank_idx < n:
        shock_vector[shocked_bank_idx] = float(shock_magnitude)
    return run_debtrank_vector(V, equity, bank_ids, shock_vector, max_steps=max_steps)


def run_debtrank_vector(
    V: np.ndarray,
    equity: np.ndarray,
    bank_ids: list[str],
    shock_vector: np.ndarray,
    max_steps: int | None = None,
) -> list[SimulationStep]:
    """
    Multi-bank initial shock (used by Monte Carlo). Every bank with a positive
    entry in shock_vector starts DISTRESSED at that distress level.
    """
    V = np.asarray(V, dtype=float)
    equity = np.asarray(equity, dtype=float)
    n = len(bank_ids)
    total_equity = float(equity.sum()) if equity.sum() > 0 else 1.0
    if max_steps is None:
        max_steps = n + 5

    h = np.zeros(n, dtype=float)
    states = np.full(n, BankStatus.UNDISTRESSED, dtype=int)

    shock_vector = np.clip(np.asarray(shock_vector, dtype=float), 0.0, 1.0)
    h = shock_vector.copy()
    states[shock_vector > 0] = BankStatus.DISTRESSED

    distressed_ever: set[str] = set()
    defaulted_ever: set[str] = set()
    history: list[SimulationStep] = []

    def record(step_idx: int, complete: bool) -> None:
        newly_distressed = [
            bank_ids[i]
            for i in range(n)
            if states[i] == BankStatus.DISTRESSED and bank_ids[i] not in distressed_ever
        ]
        new_defaults = [
            bank_ids[i]
            for i in range(n)
            if h[i] >= 1.0 - 1e-12 and bank_ids[i] not in defaulted_ever
        ]
        distressed_ever.update(newly_distressed)
        defaulted_ever.update(new_defaults)

        total_loss = float(np.sum(h * equity) / total_equity)
        history.append(
            SimulationStep(
                step=step_idx,
                distress_levels={bank_ids[i]: float(h[i]) for i in range(n)},
                states={bank_ids[i]: _STATUS_NAME[BankStatus(states[i])] for i in range(n)},
                equity_remaining={
                    bank_ids[i]: float(max(0.0, 1.0 - h[i])) for i in range(n)
                },
                total_system_loss=total_loss,
                new_defaults=new_defaults,
                newly_distressed=newly_distressed,
                simulation_complete=complete,
            )
        )

    # Step 0 — initial state.
    record(0, complete=False)

    step_idx = 0
    while step_idx < max_steps:
        distressed = [i for i in range(n) if states[i] == BankStatus.DISTRESSED]
        if not distressed:
            history[-1].simulation_complete = True
            break

        # --- Step A: propagation (h_new is a copy; h is read-only this round) ---
        h_new = h.copy()
        for i in distressed:
            hi = h[i]
            if hi <= 0:
                continue
            for j in range(n):
                if states[j] == BankStatus.INACTIVE:
                    continue
                h_new[j] = min(1.0, h_new[j] + V[j, i] * hi)

        # --- Step B: state transitions (computed from previous states) ---
        new_states = states.copy()
        for j in range(n):
            if h_new[j] > 0 and states[j] == BankStatus.UNDISTRESSED:
                new_states[j] = BankStatus.DISTRESSED
        for i in distressed:
            new_states[i] = BankStatus.INACTIVE

        h = h_new
        states = new_states
        step_idx += 1

        # --- Step C: record; Step D: convergence handled at loop top ---
        still_distressed = any(states[i] == BankStatus.DISTRESSED for i in range(n))
        record(step_idx, complete=not still_distressed)
        if not still_distressed:
            break

    return history


def debtrank_total_loss(
    V: np.ndarray,
    equity: np.ndarray,
    shock_vector: np.ndarray,
    max_steps: int | None = None,
) -> float:
    """
    Fast path: run the exact same DebtRank state machine but return ONLY the
    final total system loss (fraction of total equity destroyed). No per-step
    SimulationStep objects are built, so this is ~10-50x faster than
    run_debtrank_vector — used by Monte Carlo, which only needs the final number.

    Vectorized: propagation for one step is V[:, distressed] @ h[distressed].
    """
    V = np.asarray(V, dtype=float)
    equity = np.asarray(equity, dtype=float)
    n = len(equity)
    total_equity = float(equity.sum()) if equity.sum() > 0 else 1.0
    if max_steps is None:
        max_steps = n + 5

    UND, DIS, INA = 0, 1, 2
    h = np.clip(np.asarray(shock_vector, dtype=float), 0.0, 1.0).copy()
    states = np.where(h > 0, DIS, UND)

    for _ in range(max_steps):
        distressed = np.flatnonzero(states == DIS)
        if distressed.size == 0:
            break
        # contrib[j] = sum over distressed i of V[j, i] * h[i]
        contrib = V[:, distressed] @ h[distressed]
        active = states != INA
        h_new = np.where(active, np.minimum(1.0, h + contrib), h)

        new_states = states.copy()
        newly = (h_new > 0) & (states == UND)
        new_states[newly] = DIS
        new_states[distressed] = INA

        h = h_new
        states = new_states

    return float(np.sum(h * equity) / total_equity)


def debtrank_summary(history: list[SimulationStep], equity: np.ndarray) -> dict:
    """Convenience: extract final-state summary metrics from a run."""
    if not history:
        return {
            "total_system_loss": 0.0,
            "num_defaults": 0,
            "contagion_rounds": 0,
            "affected_banks": [],
            "final_distress": {},
        }
    final = history[-1]
    num_defaults = sum(1 for v in final.distress_levels.values() if v >= 1.0 - 1e-12)
    affected = [bid for bid, v in final.distress_levels.items() if v > 1e-9]
    return {
        "total_system_loss": final.total_system_loss,
        "num_defaults": num_defaults,
        "contagion_rounds": final.step,
        "affected_banks": affected,
        "final_distress": dict(final.distress_levels),
    }
