"""
Layer 1 — BIS Consolidated Banking Statistics ingestion.

Hits the BIS SDMX REST API (no API key) to retrieve cross-border bilateral
bank exposure data and parses the SDMX-JSON response into a tidy structure.

BIS monetary values are reported in MILLIONS of USD.
"""
from __future__ import annotations

import logging

import httpx
import pandas as pd

logger = logging.getLogger("data.bis")

BIS_BASE_URL = "https://stats.bis.org/api/v1/data/WS_CBS_PUB"
# Q: quarterly, consolidated, total claims, immediate counterparty basis, USD.
BIS_KEY = "Q.S.A.A.TO1.A.5J.USD/all"
REQUEST_TIMEOUT = 30.0

# Realistic country-level cross-border exposures (USD millions) for fallback.
FALLBACK_COUNTRY_SCALE = {
    "US": (2_000_000, 5_000_000),
    "GB": (1_000_000, 3_000_000),
    "DE": (500_000, 2_000_000),
    "FR": (500_000, 2_000_000),
    "JP": (1_000_000, 4_000_000),
    "CH": (300_000, 1_500_000),
    "NL": (200_000, 1_000_000),
    "CA": (200_000, 1_000_000),
}


def fetch_bis_exposures(start_period: str = "2020-Q1") -> dict[tuple[str, str], float]:
    """
    Fetch BIS consolidated banking statistics and return a dict keyed by
    (reporting_country, counterparty_country) -> exposure_usd_millions, using
    the most recent period available for each pair.

    Raises RuntimeError on failure so callers can fall back.
    """
    url = f"{BIS_BASE_URL}/{BIS_KEY}"
    params = {"startPeriod": start_period, "detail": "dataonly"}
    headers = {"Accept": "application/json"}

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"BIS API request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"BIS API returned malformed JSON: {exc}") from exc

    df = _parse_sdmx_json(payload)
    if df.empty:
        raise RuntimeError("BIS API parsed to an empty DataFrame")

    # Keep most recent period per (reporting, counterparty) pair.
    df = df.sort_values("period").drop_duplicates(
        subset=["reporting_country", "counterparty_country"], keep="last"
    )

    result: dict[tuple[str, str], float] = {}
    for _, row in df.iterrows():
        key = (row["reporting_country"], row["counterparty_country"])
        result[key] = float(row["exposure_usd_millions"])

    logger.info("Fetched %d BIS country-pair exposures", len(result))
    return result


def _parse_sdmx_json(payload: dict) -> pd.DataFrame:
    """
    Parse SDMX-JSON (BIS v1 dialect) into a tidy DataFrame with columns:
        reporting_country, counterparty_country, period, exposure_usd_millions

    The SDMX-JSON structure encodes dimensions separately from observations.
    We map each series key (a tuple of dimension indices) back to dimension
    values, and each observation key to the time dimension value.
    """
    try:
        data_sets = payload["dataSets"]
        structure = payload["structure"]
        series_dims = structure["dimensions"]["series"]
        obs_dims = structure["dimensions"]["observation"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected SDMX-JSON structure: {exc}") from exc

    # Identify dimension positions by id (BIS uses L_REP_CTY / L_CP_COUNTRY).
    def find_dim_index(dims, candidates):
        for idx, dim in enumerate(dims):
            if dim.get("id") in candidates:
                return idx, dim.get("values", [])
        return None, []

    rep_idx, rep_values = find_dim_index(
        series_dims, {"L_REP_CTY", "REP_COUNTRY", "CL_BIS_IF_REF_AREA"}
    )
    cp_idx, cp_values = find_dim_index(
        series_dims, {"L_CP_COUNTRY", "CP_COUNTRY", "L_CP_CTY"}
    )
    time_values = obs_dims[0].get("values", []) if obs_dims else []

    records: list[dict] = []
    for ds in data_sets:
        series = ds.get("series", {})
        for series_key, series_val in series.items():
            key_parts = series_key.split(":")
            rep = (
                rep_values[int(key_parts[rep_idx])].get("id")
                if rep_idx is not None and rep_idx < len(key_parts)
                else "NA"
            )
            cp = (
                cp_values[int(key_parts[cp_idx])].get("id")
                if cp_idx is not None and cp_idx < len(key_parts)
                else "NA"
            )
            observations = series_val.get("observations", {})
            for obs_key, obs_val in observations.items():
                period_idx = int(obs_key.split(":")[0])
                period = (
                    time_values[period_idx].get("id")
                    if period_idx < len(time_values)
                    else str(period_idx)
                )
                value = obs_val[0] if obs_val else None
                if value is None:
                    continue
                records.append(
                    {
                        "reporting_country": rep,
                        "counterparty_country": cp,
                        "period": period,
                        "exposure_usd_millions": float(value),
                    }
                )

    return pd.DataFrame.from_records(records)


def generate_synthetic_bis(seed: int = 7) -> dict[tuple[str, str], float]:
    """Generate realistic country-to-country exposures when BIS is unavailable."""
    import numpy as np

    rng = np.random.default_rng(seed)
    countries = list(FALLBACK_COUNTRY_SCALE.keys())
    result: dict[tuple[str, str], float] = {}
    for rep in countries:
        lo, hi = FALLBACK_COUNTRY_SCALE[rep]
        for cp in countries:
            if rep == cp:
                continue
            # log-normal around the midpoint of the country's range
            mid = (lo + hi) / 2
            value = float(rng.lognormal(mean=np.log(mid), sigma=0.5))
            result[(rep, cp)] = value
    logger.warning("Using synthetic BIS data — real API unavailable (%d pairs)", len(result))
    return result


def load_bis_exposures(start_period: str = "2020-Q1") -> dict[tuple[str, str], float]:
    """Primary entry point: try real BIS API, fall back to synthetic."""
    try:
        return fetch_bis_exposures(start_period=start_period)
    except RuntimeError as exc:
        logger.warning("BIS ingestion failed (%s); falling back to synthetic", exc)
        return generate_synthetic_bis()
