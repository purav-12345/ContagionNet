"""
Layer 5 — Unified simulation runner.

Runs any of the three algorithms and normalizes their output into a common list
of step dicts shaped like SimulationStepMessage, so REST and WebSocket share one
code path and the frontend animates all algorithms identically.
"""
from __future__ import annotations

from engine.debtrank import run_debtrank
from engine.eisenberg_noe import run_eisenberg_noe_shocked
from engine.threshold_cascade import run_threshold_cascade
from api.state import AppState


def _bank_payload(state: AppState, distress: dict[str, float],
                  status: dict[str, str], equity_remaining: dict[str, float]) -> list[dict]:
    return [
        {
            "id": bid,
            "name": state.bank_names.get(bid, bid),
            "distress": float(distress.get(bid, 0.0)),
            "state": status.get(bid, "UNDISTRESSED"),
            "equity_remaining": float(equity_remaining.get(bid, 1.0)),
        }
        for bid in state.bank_ids
    ]


def run_simulation_steps(
    state: AppState, bank_id: str, shock_magnitude: float, algorithm: str
) -> list[dict]:
    """Return a list of normalized step dicts for the requested algorithm."""
    idx = state.get_index(bank_id)

    if algorithm == "debtrank":
        history = run_debtrank(state.V, state.equity, state.bank_ids, idx, shock_magnitude)
        steps = []
        for s in history:
            steps.append(
                {
                    "step": s.step,
                    "banks": _bank_payload(
                        state, s.distress_levels, s.states, s.equity_remaining
                    ),
                    "total_system_loss": s.total_system_loss,
                    "new_defaults": s.new_defaults,
                    "newly_distressed": s.newly_distressed,
                    "simulation_complete": s.simulation_complete,
                }
            )
        return steps

    if algorithm == "threshold_cascade":
        history = run_threshold_cascade(
            state.exposure_matrix, state.equity, state.bank_ids, idx, shock_magnitude
        )
        steps = []
        prev_defaulted: set[str] = set()
        for s in history:
            distress = s["distress_levels"]
            all_def = set(s["all_defaulted"])
            status = {}
            for bid in state.bank_ids:
                if bid in all_def:
                    status[bid] = "INACTIVE"
                elif distress.get(bid, 0.0) > 0:
                    status[bid] = "DISTRESSED"
                else:
                    status[bid] = "UNDISTRESSED"
            new_defaults = [b for b in s["defaulted_this_round"]]
            steps.append(
                {
                    "step": s["step"],
                    "banks": _bank_payload(
                        state, distress, status, s["equity_remaining"]
                    ),
                    "total_system_loss": s["total_system_loss"],
                    "new_defaults": new_defaults,
                    "newly_distressed": new_defaults,
                    "simulation_complete": s["simulation_complete"],
                }
            )
            prev_defaulted = all_def
        return steps

    if algorithm == "eisenberg_noe":
        result = run_eisenberg_noe_shocked(
            state.exposure_matrix, state.external_assets, state.bank_ids,
            idx, shock_magnitude,
        )
        steps = []
        animated = result["animated_steps"]
        n = len(state.bank_ids)
        for k, s in enumerate(animated):
            distress = s["distress_levels"]
            defaulted_set = set(s["defaulted_banks"])
            status = {}
            equity_remaining = {}
            for bid in state.bank_ids:
                if bid in defaulted_set:
                    status[bid] = "INACTIVE"
                elif distress.get(bid, 0.0) > 0:
                    status[bid] = "DISTRESSED"
                else:
                    status[bid] = "UNDISTRESSED"
                equity_remaining[bid] = max(0.0, 1.0 - distress.get(bid, 0.0))
            complete = k == len(animated) - 1
            steps.append(
                {
                    "step": s["step"],
                    "banks": _bank_payload(state, distress, status, equity_remaining),
                    "total_system_loss": (
                        result["total_system_loss"] if complete
                        else len(defaulted_set) / n
                    ),
                    "new_defaults": s["defaulted_banks"],
                    "newly_distressed": s["defaulted_banks"],
                    "simulation_complete": complete,
                }
            )
        if not steps:
            steps = [
                {
                    "step": 0,
                    "banks": _bank_payload(
                        state, {}, {b: "UNDISTRESSED" for b in state.bank_ids}, {}
                    ),
                    "total_system_loss": 0.0,
                    "new_defaults": [],
                    "newly_distressed": [],
                    "simulation_complete": True,
                }
            ]
        return steps

    raise ValueError(f"Unknown algorithm: {algorithm}")
