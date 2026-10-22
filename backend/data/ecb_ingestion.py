"""
Layer 1 — ECB Statistical Warehouse ingestion (shown in the architecture image).

Hits the ECB Data Portal REST API (no API key) for euro-area bank balance-sheet
aggregates (BSI dataset). Used to enrich the network with European banking-sector
context. Parsed from SDMX-JSON into a tidy structure.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("data.ecb")

ECB_BASE_URL = "https://data-api.ecb.europa.eu/service/data"
# BSI: Balance Sheet Items. Monthly, euro area, total assets/liabilities series.
ECB_FLOW = "BSI"
ECB_KEY = "M.U2.N.A.A20.A.1.U2.2240.Z01.E"
REQUEST_TIMEOUT = 30.0


def fetch_ecb_aggregate() -> dict:
    """
    Fetch an ECB euro-area banking aggregate and return a small summary dict:
        {"series_id": str, "latest_period": str, "latest_value": float,
         "observations": {period: value}, "source": "ECB"}

    Raises RuntimeError on failure so callers can fall back.
    """
    url = f"{ECB_BASE_URL}/{ECB_FLOW}/{ECB_KEY}"
    headers = {"Accept": "application/json"}

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"ECB API request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"ECB API returned malformed JSON: {exc}") from exc

    observations = _parse_ecb_sdmx(payload)
    if not observations:
        raise RuntimeError("ECB API parsed to empty observations")

    latest_period = max(observations.keys())
    summary = {
        "series_id": f"{ECB_FLOW}.{ECB_KEY}",
        "latest_period": latest_period,
        "latest_value": observations[latest_period],
        "observations": observations,
        "source": "ECB",
    }
    logger.info(
        "Fetched ECB aggregate %s: latest %s = %.1f",
        summary["series_id"], latest_period, summary["latest_value"],
    )
    return summary


def _parse_ecb_sdmx(payload: dict) -> dict[str, float]:
    """Parse ECB SDMX-JSON into {period: value}."""
    try:
        data_sets = payload["dataSets"]
        obs_dims = payload["structure"]["dimensions"]["observation"]
        time_values = obs_dims[0].get("values", []) if obs_dims else []
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected ECB SDMX-JSON structure: {exc}") from exc

    observations: dict[str, float] = {}
    for ds in data_sets:
        series = ds.get("series", {})
        for series_val in series.values():
            for obs_key, obs_val in series_val.get("observations", {}).items():
                period_idx = int(obs_key.split(":")[0])
                period = (
                    time_values[period_idx].get("id")
                    if period_idx < len(time_values)
                    else str(period_idx)
                )
                value = obs_val[0] if obs_val else None
                if value is not None:
                    observations[period] = float(value)
    return observations


def generate_synthetic_ecb(seed: int = 11) -> dict:
    """Generate a plausible ECB aggregate series when the API is unavailable."""
    import numpy as np

    rng = np.random.default_rng(seed)
    periods = [f"2023-{m:02d}" for m in range(1, 13)]
    base = 30_000_000.0  # EUR millions, euro-area MFI total assets order of magnitude
    observations = {}
    val = base
    for p in periods:
        val *= 1.0 + rng.normal(0.001, 0.01)
        observations[p] = float(val)
    latest = periods[-1]
    logger.warning("Using synthetic ECB data — real API unavailable")
    return {
        "series_id": f"{ECB_FLOW}.{ECB_KEY}",
        "latest_period": latest,
        "latest_value": observations[latest],
        "observations": observations,
        "source": "SYNTHETIC",
    }


def load_ecb_aggregate() -> dict:
    """Primary entry point: try real ECB API, fall back to synthetic."""
    try:
        return fetch_ecb_aggregate()
    except RuntimeError as exc:
        logger.warning("ECB ingestion failed (%s); falling back to synthetic", exc)
        return generate_synthetic_ecb()
