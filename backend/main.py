"""
Real-Time Systemic Risk Contagion Simulator — backend entry point.

Startup pipeline (data flow, end to end):
  1. Run correctness self-tests (DebtRank + max-entropy). Refuse to start on fail.
  2. Ingest FDIC bank balance sheets (real API, synthetic fallback).
  3. Ingest BIS cross-border exposures + ECB aggregate (context).
  4. Estimate the bilateral exposure matrix (RAS max-entropy).
  5. Build the NetworkX graph, vulnerability matrix V, centralities.
  6. Compute LCR + system metrics.
  7. Precompute all single-node shock scenarios + Systemic Importance Ranking.
  8. Precompute the N×N contagion heatmap.
  9. Precompute Monte Carlo (2000 sims).
 10. Initialize the SQLite cache and serve.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analytics.metrics import (
    apply_lcr,
    apply_systemic_importance,
    system_level_metrics,
)
from analytics.monte_carlo import run_monte_carlo
from analytics.stress_tester import (
    compute_contagion_heatmap,
    compute_systemic_importance_ranking,
    run_all_single_shock_scenarios,
)
from api import cache
from api.routes import router as rest_router
from api.state import APP_STATE
from api.websocket import router as ws_router
from data.bis_ingestion import load_bis_exposures
from data.ecb_ingestion import load_ecb_aggregate
from data.fdic_ingestion import load_banks
from data.network_estimator import (
    build_exposure_matrix,
    maximum_entropy_estimation,
)
from engine.debtrank import run_debtrank
from engine.graph_builder import (
    apply_metrics_to_nodes,
    build_bank_nodes,
    build_graph,
    compute_network_metrics,
    compute_vulnerability_matrix,
    graph_to_d3_json,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

BANK_LIMIT = 100


def run_self_tests() -> None:
    """Two correctness gates. Raise RuntimeError on failure (server won't start)."""
    logger.info("Running correctness self-tests...")

    # --- DebtRank state machine ---
    V_test = np.array([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.4, 0.0]])
    equity_test = np.array([100.0, 100.0, 100.0])
    history = run_debtrank(V_test, equity_test, ["B0", "B1", "B2"], 0, 0.8)
    assert len(history) == 4, f"expected 4 steps, got {len(history)}"
    assert abs(history[1].distress_levels["B1"] - 0.4) < 1e-6
    assert abs(history[2].distress_levels["B2"] - 0.16) < 1e-6
    assert history[1].states["B0"] == "INACTIVE"
    assert history[2].states["B1"] == "INACTIVE"
    assert abs(history[-1].total_system_loss - (0.8 + 0.4 + 0.16) / 3) < 1e-3
    logger.info("  [PASS] DebtRank correctness test")

    # --- Maximum entropy estimator ---
    assets = np.array([100.0, 80.0, 60.0, 40.0])
    liabilities = np.array([70.0, 90.0, 50.0, 70.0])
    X = maximum_entropy_estimation(assets, liabilities)
    assert X.diagonal().sum() == 0.0, "diagonal must be zero (no self-lending)"
    assert np.all(X >= 0), "no negative exposures"
    assert np.allclose(X.sum(axis=1), assets, rtol=0.01), "row sums must match assets"
    assert np.allclose(X.sum(axis=0), liabilities, rtol=0.01), "col sums must match liabilities"
    logger.info("  [PASS] Maximum entropy estimator test")

    logger.info("All correctness self-tests passed.")


def build_pipeline() -> None:
    """Execute the full data -> analytics pipeline and populate APP_STATE."""
    state = APP_STATE

    # 2. FDIC ingestion (with synthetic fallback)
    banks = load_banks(limit=BANK_LIMIT, allow_synthetic=True)
    state.banks = banks
    state.data_source = banks[0].get("source", "unknown") if banks else "none"

    # 3. BIS + ECB context (best-effort; never blocks startup)
    try:
        bis = load_bis_exposures()
        logger.info("BIS exposures loaded: %d country pairs", len(bis))
    except Exception as exc:  # noqa: BLE001
        logger.warning("BIS load failed entirely: %s", exc)
    try:
        state.ecb_aggregate = load_ecb_aggregate()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ECB load failed entirely: %s", exc)

    # 4. Bilateral exposure matrix (RAS max-entropy)
    exposure_matrix = build_exposure_matrix(banks)
    state.exposure_matrix = exposure_matrix

    # 5. Graph + V + centralities
    graph = build_graph(banks, exposure_matrix)
    V = compute_vulnerability_matrix(banks, exposure_matrix)
    bank_nodes = build_bank_nodes(banks)
    metrics = compute_network_metrics(graph)
    apply_metrics_to_nodes(bank_nodes, metrics)

    state.graph = graph
    state.V = V
    state.bank_nodes = bank_nodes
    state.bank_ids = [b["id"] for b in banks]
    state.bank_names = {b["id"]: b["name"] for b in banks}
    state.index_by_id = {bid: i for i, bid in enumerate(state.bank_ids)}
    state.equity = np.array([max(float(b["equity"]), 1.0) for b in banks])
    # External (non-interbank) assets for Eisenberg-Noe.
    state.external_assets = np.array(
        [max(float(b["total_assets"]) - float(b["interbank_assets"]), 0.0) for b in banks]
    )

    # 6. LCR + system metrics (rankings applied after stress test)
    apply_lcr(bank_nodes)

    # 7. Single-node shocks + SIR
    scenarios = run_all_single_shock_scenarios(
        V, exposure_matrix, state.equity, state.bank_ids, state.bank_names
    )
    rankings = compute_systemic_importance_ranking(scenarios)
    state.scenarios = scenarios
    state.rankings = rankings
    state.rankings_computed_at = datetime.now(timezone.utc).isoformat()
    apply_systemic_importance(bank_nodes, rankings)

    # System metrics + D3 JSON (after SIR + LCR are on the nodes)
    state.system_metrics = system_level_metrics(bank_nodes, rankings)
    state.network_json = graph_to_d3_json(graph, bank_nodes)

    # 8. Heatmap
    state.heatmap = compute_contagion_heatmap(
        V, state.equity, state.bank_ids, state.bank_names
    )

    # 9. Monte Carlo
    state.monte_carlo = run_monte_carlo(
        V, state.equity, state.bank_ids, n_simulations=2000
    )

    state.ready = True
    logger.info(
        "Pipeline ready: %d banks, source=%s, top SIR=%s",
        len(state.bank_ids), state.data_source,
        rankings[0]["bank_name"] if rankings else "n/a",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_self_tests()  # raises -> server does not start
    await cache.init_cache()
    build_pipeline()
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Systemic Risk Contagion Simulator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_router)
app.include_router(ws_router)


@app.get("/")
async def root() -> dict:
    return {
        "name": "Systemic Risk Contagion Simulator",
        "status": "ok" if APP_STATE.ready else "starting",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
