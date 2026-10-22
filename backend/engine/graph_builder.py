"""
Layer 2 — The Graph Engine.

Converts raw bank balance sheets + the estimated bilateral exposure matrix into
a NetworkX directed weighted graph, the vulnerability matrix V, and network
topology (centrality) metrics. Also serializes the graph to D3-compatible JSON.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

logger = logging.getLogger("engine.graph")


@dataclass
class BankNode:
    id: str
    name: str
    total_assets: float
    equity: float
    interbank_assets: float
    interbank_liabilities: float
    # Computed metrics — populated after the graph is built.
    degree_centrality: float = 0.0
    betweenness_centrality: float = 0.0
    eigenvector_centrality: float = 0.0
    systemic_importance: float = 0.0
    # Liquidity Coverage Ratio (Basel III) — populated by analytics.metrics.
    lcr: float = 0.0
    extra: dict = field(default_factory=dict)


def build_bank_nodes(banks: list[dict]) -> list[BankNode]:
    """Balance Sheet Parser: list[dict] -> list[BankNode]."""
    nodes: list[BankNode] = []
    for b in banks:
        nodes.append(
            BankNode(
                id=str(b["id"]),
                name=str(b["name"]),
                total_assets=float(b["total_assets"]),
                equity=float(b["equity"]),
                interbank_assets=float(b["interbank_assets"]),
                interbank_liabilities=float(b["interbank_liabilities"]),
            )
        )
    return nodes


def build_graph(banks: list[dict], exposure_matrix: np.ndarray) -> nx.DiGraph:
    """
    Adjacency Matrix Builder: directed weighted graph.
    Edge i -> j with weight = exposure_matrix[i][j] (amount bank i lent to j).
    Edges below a small threshold (relative to the mean) are pruned to keep the
    graph readable.
    """
    n = len(banks)
    G = nx.DiGraph()
    for b in banks:
        G.add_node(
            str(b["id"]),
            name=str(b["name"]),
            total_assets=float(b["total_assets"]),
            equity=float(b["equity"]),
            interbank_assets=float(b["interbank_assets"]),
            interbank_liabilities=float(b["interbank_liabilities"]),
        )

    positive = exposure_matrix[exposure_matrix > 0]
    mean_exposure = positive.mean() if positive.size else 0.0
    threshold = 0.01 * mean_exposure

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            w = float(exposure_matrix[i, j])
            if w > threshold:
                G.add_edge(str(banks[i]["id"]), str(banks[j]["id"]), weight=w)

    logger.info("Built graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G


def compute_vulnerability_matrix(
    banks: list[dict], exposure_matrix: np.ndarray
) -> np.ndarray:
    """
    Vulnerability Matrix: V[i][j] = exposure_matrix[i][j] / equity[i].
    The fraction of bank i's equity wiped out if bank j fully defaults.
    Equity is floored at 1.0 to avoid divide-by-zero.
    """
    n = len(banks)
    equity = np.array([max(float(b["equity"]), 1.0) for b in banks], dtype=float)
    V = exposure_matrix / equity[:, np.newaxis]
    np.fill_diagonal(V, 0.0)
    # V is a fraction of equity-at-risk; an exposure can exceed equity, so V can
    # exceed 1. We leave it uncapped here — DebtRank caps distress at 1.0.
    return V


def compute_network_metrics(G: nx.DiGraph) -> dict[str, dict]:
    """
    Network Topology Metrics: degree, betweenness, eigenvector centrality.
    Returns dict keyed by node id -> {metric: value}.
    """
    metrics: dict[str, dict] = {nid: {} for nid in G.nodes()}

    degree = nx.degree_centrality(G)
    try:
        betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("betweenness failed (%s); using zeros", exc)
        betweenness = {nid: 0.0 for nid in G.nodes()}

    try:
        eigenvector = nx.eigenvector_centrality_numpy(G, weight="weight")
    except Exception as exc:
        logger.warning("eigenvector_centrality_numpy failed (%s); using degree", exc)
        eigenvector = degree

    for nid in G.nodes():
        metrics[nid] = {
            "degree_centrality": float(degree.get(nid, 0.0)),
            "betweenness_centrality": float(betweenness.get(nid, 0.0)),
            "eigenvector_centrality": float(eigenvector.get(nid, 0.0)),
        }
    return metrics


def apply_metrics_to_nodes(
    bank_nodes: list[BankNode], metrics: dict[str, dict]
) -> None:
    """Mutate BankNode objects with computed centrality metrics."""
    for node in bank_nodes:
        m = metrics.get(node.id, {})
        node.degree_centrality = m.get("degree_centrality", 0.0)
        node.betweenness_centrality = m.get("betweenness_centrality", 0.0)
        node.eigenvector_centrality = m.get("eigenvector_centrality", 0.0)


def graph_to_d3_json(G: nx.DiGraph, bank_nodes: list[BankNode]) -> dict:
    """
    Serialize to D3-compatible JSON: {"nodes": [...], "links": [...]}.
    """
    node_by_id = {n.id: n for n in bank_nodes}
    nodes = []
    for nid in G.nodes():
        n = node_by_id.get(nid)
        if n is None:
            data = G.nodes[nid]
            n = BankNode(
                id=nid,
                name=data.get("name", nid),
                total_assets=data.get("total_assets", 0.0),
                equity=data.get("equity", 0.0),
                interbank_assets=data.get("interbank_assets", 0.0),
                interbank_liabilities=data.get("interbank_liabilities", 0.0),
            )
        nodes.append(
            {
                "id": n.id,
                "name": n.name,
                "total_assets": n.total_assets,
                "equity": n.equity,
                "interbank_assets": n.interbank_assets,
                "interbank_liabilities": n.interbank_liabilities,
                "degree_centrality": n.degree_centrality,
                "betweenness_centrality": n.betweenness_centrality,
                "eigenvector_centrality": n.eigenvector_centrality,
                "systemic_importance": n.systemic_importance,
                "lcr": n.lcr,
            }
        )

    links = [
        {"source": u, "target": v, "weight": float(d.get("weight", 0.0))}
        for u, v, d in G.edges(data=True)
    ]
    return {"nodes": nodes, "links": links}
