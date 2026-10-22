"""
Layer 4 — Risk metrics: Systemic Importance application + Basel III LCR.

LCR (Liquidity Coverage Ratio) = HQLA / Net Cash Outflows over 30 days.
Basel III requires LCR >= 100%. Exact HQLA/outflow figures aren't in the FDIC
fields we pull, so we estimate them from balance-sheet proxies (academically
standard): HQLA from cash-like/liquid assets, outflows from short-term funding.
"""
from __future__ import annotations

import numpy as np

from engine.graph_builder import BankNode

# Proxy coefficients for LCR estimation.
HQLA_FRACTION_OF_ASSETS = 0.15      # share of assets treated as high-quality liquid
OUTFLOW_FRACTION_OF_LIAB = 0.25     # share of interbank liabilities running off in 30d


def estimate_lcr(bank: BankNode) -> float:
    """
    Estimate a bank's Liquidity Coverage Ratio from balance-sheet proxies.
    Returns a ratio (1.0 == 100%). Capped at a sane display maximum.
    """
    hqla = HQLA_FRACTION_OF_ASSETS * bank.total_assets
    net_outflows = OUTFLOW_FRACTION_OF_LIAB * bank.interbank_liabilities
    if net_outflows <= 0:
        return 5.0  # no measurable short-term outflow -> very liquid
    return float(min(hqla / net_outflows, 10.0))


def apply_systemic_importance(
    bank_nodes: list[BankNode], rankings: list[dict]
) -> None:
    """Write SIR scores onto BankNode.systemic_importance from the ranking."""
    score_by_id = {r["bank_id"]: r["systemic_importance_score"] for r in rankings}
    for node in bank_nodes:
        node.systemic_importance = float(score_by_id.get(node.id, 0.0))


def apply_lcr(bank_nodes: list[BankNode]) -> None:
    """Write estimated LCR onto each BankNode."""
    for node in bank_nodes:
        node.lcr = estimate_lcr(node)


def system_level_metrics(
    bank_nodes: list[BankNode], rankings: list[dict]
) -> dict:
    """Aggregate system-wide metrics for the dashboard header."""
    total_equity = sum(n.equity for n in bank_nodes)
    total_assets = sum(n.total_assets for n in bank_nodes)
    avg_lcr = float(np.mean([n.lcr for n in bank_nodes])) if bank_nodes else 0.0
    most_important = rankings[0] if rankings else None
    n_below_lcr = sum(1 for n in bank_nodes if n.lcr < 1.0)
    return {
        "total_banks": len(bank_nodes),
        "total_system_equity": total_equity,
        "total_system_assets": total_assets,
        "average_lcr": avg_lcr,
        "banks_below_lcr_minimum": n_below_lcr,
        "most_systemically_important_bank": (
            most_important["bank_name"] if most_important else None
        ),
        "most_systemically_important_score": (
            most_important["systemic_importance_score"] if most_important else 0.0
        ),
    }
