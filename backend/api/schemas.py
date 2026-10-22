"""Layer 5 — Pydantic v2 request/response contracts."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AlgorithmType(str, Enum):
    DEBTRANK = "debtrank"
    EISENBERG_NOE = "eisenberg_noe"
    THRESHOLD_CASCADE = "threshold_cascade"


class SimulateRequest(BaseModel):
    bank_id: str
    shock_magnitude: float = Field(ge=0.0, le=1.0)
    algorithm: AlgorithmType = AlgorithmType.DEBTRANK


class BankStateMessage(BaseModel):
    id: str
    name: str
    distress: float
    state: str  # UNDISTRESSED | DISTRESSED | INACTIVE
    equity_remaining: float


class SimulationStepMessage(BaseModel):
    step: int
    banks: list[BankStateMessage]
    total_system_loss: float
    new_defaults: list[str]
    newly_distressed: list[str]
    simulation_complete: bool


class SimulateResponse(BaseModel):
    scenario_id: str
    algorithm: AlgorithmType
    bank_id: str
    shock_magnitude: float
    steps: list[SimulationStepMessage]
    cached: bool = False


class NetworkResponse(BaseModel):
    nodes: list[dict]
    links: list[dict]
    total_banks: int
    total_system_equity: float
    total_system_assets: float


class SystemicImportanceResponse(BaseModel):
    rankings: list[dict]
    computed_at: str


class MonteCarloRequest(BaseModel):
    n_simulations: int = Field(default=2000, ge=10, le=20000)
    shock_mean: float = Field(default=0.05, ge=0.0, le=1.0)
    shock_std: float = Field(default=0.15, ge=0.0, le=1.0)


class HeatmapResponse(BaseModel):
    matrix: list[list[float]]
    bank_ids: list[str]
    bank_names: list[str]


class HealthResponse(BaseModel):
    status: str
    banks_loaded: int
    network_ready: bool
    data_source: str
