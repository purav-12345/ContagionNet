"""Layer 5 — REST endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from analytics.monte_carlo import run_monte_carlo
from api import cache
from api.schemas import (
    HealthResponse,
    HeatmapResponse,
    MonteCarloRequest,
    NetworkResponse,
    SimulateRequest,
    SimulateResponse,
    SystemicImportanceResponse,
)
from api.simulation_runner import run_simulation_steps
from api.state import APP_STATE

logger = logging.getLogger("api.routes")
router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if APP_STATE.ready else "starting",
        banks_loaded=len(APP_STATE.bank_ids),
        network_ready=APP_STATE.ready,
        data_source=APP_STATE.data_source,
    )


@router.get("/network", response_model=NetworkResponse)
async def get_network() -> NetworkResponse:
    if not APP_STATE.ready:
        raise HTTPException(status_code=503, detail="Network not ready")
    nj = APP_STATE.network_json
    return NetworkResponse(
        nodes=nj.get("nodes", []),
        links=nj.get("links", []),
        total_banks=len(APP_STATE.bank_ids),
        total_system_equity=APP_STATE.system_metrics.get("total_system_equity", 0.0),
        total_system_assets=APP_STATE.system_metrics.get("total_system_assets", 0.0),
    )


@router.get("/banks")
async def get_banks() -> dict:
    if not APP_STATE.ready:
        raise HTTPException(status_code=503, detail="Network not ready")
    return {
        "banks": APP_STATE.network_json.get("nodes", []),
        "system_metrics": APP_STATE.system_metrics,
    }


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(req: SimulateRequest) -> SimulateResponse:
    if not APP_STATE.ready:
        raise HTTPException(status_code=503, detail="Network not ready")
    if req.bank_id not in APP_STATE.index_by_id:
        raise HTTPException(status_code=404, detail=f"Unknown bank_id: {req.bank_id}")

    algo = req.algorithm.value
    sid = cache.scenario_id(req.bank_id, req.shock_magnitude, algo)

    cached = await cache.get_cached(sid)
    if cached is not None:
        return SimulateResponse(
            scenario_id=sid,
            algorithm=req.algorithm,
            bank_id=req.bank_id,
            shock_magnitude=req.shock_magnitude,
            steps=cached["steps"],
            cached=True,
        )

    try:
        steps = run_simulation_steps(
            APP_STATE, req.bank_id, req.shock_magnitude, algo
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Simulation failed")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}")

    await cache.put_cached(sid, req.bank_id, req.shock_magnitude, algo, {"steps": steps})

    return SimulateResponse(
        scenario_id=sid,
        algorithm=req.algorithm,
        bank_id=req.bank_id,
        shock_magnitude=req.shock_magnitude,
        steps=steps,
        cached=False,
    )


@router.get("/stress-test/systemic-importance", response_model=SystemicImportanceResponse)
async def systemic_importance() -> SystemicImportanceResponse:
    if not APP_STATE.ready:
        raise HTTPException(status_code=503, detail="Network not ready")
    return SystemicImportanceResponse(
        rankings=APP_STATE.rankings,
        computed_at=APP_STATE.rankings_computed_at,
    )


@router.get("/stress-test/heatmap", response_model=HeatmapResponse)
async def heatmap() -> HeatmapResponse:
    if not APP_STATE.ready:
        raise HTTPException(status_code=503, detail="Network not ready")
    h = APP_STATE.heatmap
    return HeatmapResponse(
        matrix=h.get("matrix", []),
        bank_ids=h.get("bank_ids", []),
        bank_names=h.get("bank_names", []),
    )


@router.get("/monte-carlo")
async def monte_carlo_precomputed() -> dict:
    if not APP_STATE.ready:
        raise HTTPException(status_code=503, detail="Network not ready")
    return APP_STATE.monte_carlo


@router.post("/monte-carlo")
async def monte_carlo_run(req: MonteCarloRequest) -> dict:
    if not APP_STATE.ready:
        raise HTTPException(status_code=503, detail="Network not ready")
    try:
        return run_monte_carlo(
            APP_STATE.V,
            APP_STATE.equity,
            APP_STATE.bank_ids,
            n_simulations=req.n_simulations,
            shock_mean=req.shock_mean,
            shock_std=req.shock_std,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Monte Carlo failed")
        raise HTTPException(status_code=500, detail=f"Monte Carlo failed: {exc}")


# Compatibility alias matching the original spec path.
@router.post("/scenario/monte-carlo")
async def monte_carlo_run_alias(req: MonteCarloRequest) -> dict:
    return await monte_carlo_run(req)


@router.get("/scenario/{scenario_id}")
async def get_scenario(scenario_id: str) -> dict:
    result = await cache.get_cached(scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found in cache")
    return {"scenario_id": scenario_id, **result}


@router.get("/ecb")
async def ecb_aggregate() -> dict:
    return APP_STATE.ecb_aggregate or {"status": "unavailable"}
