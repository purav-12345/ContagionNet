"""
Layer 1 — FDIC Call Report ingestion.

Fetches the largest US banks by total assets from the FDIC public API
(no API key required) and extracts balance-sheet figures used to build the
interbank network: total assets, equity (loss buffer), and proxies for
interbank lending/borrowing derived from interest income/expense.

All FDIC monetary values are reported in THOUSANDS of USD.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("data.fdic")

FDIC_FINANCIALS_URL = "https://api.fdic.gov/banks/financials"
FDIC_INSTITUTIONS_URL = "https://api.fdic.gov/banks/institutions"

# Multiples used to turn interest income/expense into rough interbank totals.
# These are estimates and are academically standard when exact interbank
# positions are unavailable.
INTERBANK_ASSET_MULTIPLE = 12.5
INTERBANK_LIABILITY_MULTIPLE = 10.0

REQUEST_TIMEOUT = 30.0


def _safe_float(value, default: float = 0.0) -> float:
    """Coerce an FDIC field to float, tolerating None/strings/empty."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_top_banks(limit: int = 100) -> list[dict]:
    """
    Fetch the `limit` largest active US banks by total assets and return a list
    of normalized bank dicts.

    Each dict has keys:
        id, name, total_assets, equity, net_loans,
        interest_income, interest_expense,
        interbank_assets, interbank_liabilities

    Raises:
        RuntimeError on network/parse failure so callers can fall back to
        synthetic data.
    """
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            # Step 1: find the most recent reporting date. The financials
            # endpoint stores every historical quarter, so we must pin to one
            # date or sorting by ASSET returns the biggest banks repeated.
            latest_resp = client.get(
                FDIC_FINANCIALS_URL,
                params={
                    "fields": "REPDTE",
                    "sort_by": "REPDTE",
                    "sort_order": "DESC",
                    "limit": "1",
                    "output": "json",
                },
            )
            latest_resp.raise_for_status()
            latest_rows = latest_resp.json().get("data")
            if not latest_rows:
                raise RuntimeError("FDIC API returned no reporting dates")
            latest_repdte = latest_rows[0].get("data", latest_rows[0]).get("REPDTE")

            # Step 2: top `limit` banks by assets at that reporting date.
            params = {
                "fields": "NAME,REPDTE,ASSET,EQ,LIAB,LNLSNET,INTINC,EINTEXP,CERT,DEP",
                "filters": f"REPDTE:{latest_repdte}",
                "limit": str(limit),
                "sort_by": "ASSET",
                "sort_order": "DESC",
                "output": "json",
            }
            resp = client.get(FDIC_FINANCIALS_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"FDIC API request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"FDIC API returned malformed JSON: {exc}") from exc

    rows = payload.get("data")
    if not rows:
        raise RuntimeError("FDIC API returned no data rows")

    banks: list[dict] = []
    seen_ids: set[str] = set()
    for entry in rows:
        rec = entry.get("data", entry)  # financials nest fields under "data"
        cert = rec.get("CERT")
        if cert is None:
            continue
        bank_id = str(cert)
        if bank_id in seen_ids:
            continue
        seen_ids.add(bank_id)

        total_assets = _safe_float(rec.get("ASSET"))
        equity = _safe_float(rec.get("EQ"))
        net_loans = _safe_float(rec.get("LNLSNET"))
        interest_income = _safe_float(rec.get("INTINC"))
        interest_expense = _safe_float(rec.get("EINTEXP"))
        name = rec.get("NAME") or f"Bank {bank_id}"

        # Skip degenerate records that would break the V matrix.
        if total_assets <= 0:
            continue

        interbank_assets = interest_income * INTERBANK_ASSET_MULTIPLE
        interbank_liabilities = interest_expense * INTERBANK_LIABILITY_MULTIPLE

        # Guard against banks whose interest figures are missing — fall back to
        # a small fraction of assets so they still participate in the network.
        if interbank_assets <= 0:
            interbank_assets = 0.10 * total_assets
        if interbank_liabilities <= 0:
            interbank_liabilities = 0.08 * total_assets

        # Equity must be positive (it is the loss buffer / denominator of V).
        if equity <= 0:
            equity = max(0.08 * total_assets, 1.0)

        banks.append(
            {
                "id": bank_id,
                "name": str(name).strip(),
                "total_assets": total_assets,
                "equity": equity,
                "net_loans": net_loans,
                "interest_income": interest_income,
                "interest_expense": interest_expense,
                "interbank_assets": interbank_assets,
                "interbank_liabilities": interbank_liabilities,
                "source": "FDIC",
            }
        )

    if not banks:
        raise RuntimeError("FDIC API returned data but no usable banks")

    logger.info("Fetched %d banks from FDIC API", len(banks))
    return banks


def generate_synthetic_banks(n: int = 50, seed: int = 42) -> list[dict]:
    """
    Generate a realistic synthetic US-bank network when the FDIC API is
    unavailable. Sizes follow a log-normal distribution; capital ratios follow
    Basel III conventions.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    banks: list[dict] = []
    # Draw assets (in thousands USD) — lognormal gives a realistic heavy tail.
    assets = np.sort(rng.lognormal(mean=15.5, sigma=1.6, size=n))[::-1]

    for i, total_assets in enumerate(assets):
        total_assets = float(total_assets)
        equity = 0.08 * total_assets  # Basel III minimum capital ratio
        interbank_assets = 0.15 * total_assets
        interbank_liabilities = 0.12 * total_assets
        banks.append(
            {
                "id": f"BANK_{i:03d}",
                "name": f"Synthetic Bank {i + 1}",
                "total_assets": total_assets,
                "equity": equity,
                "net_loans": 0.55 * total_assets,
                "interest_income": interbank_assets / INTERBANK_ASSET_MULTIPLE,
                "interest_expense": interbank_liabilities / INTERBANK_LIABILITY_MULTIPLE,
                "interbank_assets": interbank_assets,
                "interbank_liabilities": interbank_liabilities,
                "source": "SYNTHETIC",
            }
        )

    logger.warning("Using synthetic data — real FDIC API unavailable (%d banks)", n)
    return banks


def load_banks(limit: int = 100, allow_synthetic: bool = True) -> list[dict]:
    """
    Primary entry point. Try the real FDIC API; fall back to synthetic banks.
    """
    try:
        return fetch_top_banks(limit=limit)
    except RuntimeError as exc:
        if not allow_synthetic:
            raise
        logger.warning("FDIC ingestion failed (%s); falling back to synthetic", exc)
        return generate_synthetic_banks(n=min(limit, 50))
