"""
Layer 5 — Shared application state.

Holds the precomputed network, matrices, and analytics produced at startup.
Route handlers and the WebSocket endpoint read from the single AppState
instance. Built once in main.py during the startup pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import networkx as nx

from engine.graph_builder import BankNode


@dataclass
class AppState:
    ready: bool = False
    data_source: str = "unknown"

    banks: list[dict] = field(default_factory=list)
    bank_nodes: list[BankNode] = field(default_factory=list)
    bank_ids: list[str] = field(default_factory=list)
    bank_names: dict[str, str] = field(default_factory=dict)
    index_by_id: dict[str, int] = field(default_factory=dict)

    graph: nx.DiGraph | None = None
    exposure_matrix: np.ndarray | None = None
    V: np.ndarray | None = None
    equity: np.ndarray | None = None
    external_assets: np.ndarray | None = None

    network_json: dict = field(default_factory=dict)
    scenarios: list[dict] = field(default_factory=list)
    rankings: list[dict] = field(default_factory=list)
    heatmap: dict = field(default_factory=dict)
    monte_carlo: dict = field(default_factory=dict)
    system_metrics: dict = field(default_factory=dict)
    ecb_aggregate: dict = field(default_factory=dict)

    rankings_computed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def get_index(self, bank_id: str) -> int:
        if bank_id not in self.index_by_id:
            raise KeyError(f"Unknown bank_id: {bank_id}")
        return self.index_by_id[bank_id]


# Module-level singleton accessed by routes/websocket.
APP_STATE = AppState()
