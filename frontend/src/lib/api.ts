import type {
  BankStatus,
  HeatmapData,
  MonteCarloResult,
  NetworkData,
  SystemicImportanceResponse,
} from "../types/simulation";

export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";
export const WS_URL =
  (import.meta as any).env?.VITE_WS_URL ?? "ws://localhost:8000/ws/contagion";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const fetchNetwork = () => getJSON<NetworkData>("/api/network");
export const fetchSystemicImportance = () =>
  getJSON<SystemicImportanceResponse>("/api/stress-test/systemic-importance");
export const fetchHeatmap = () => getJSON<HeatmapData>("/api/stress-test/heatmap");
export const fetchMonteCarlo = () => getJSON<MonteCarloResult>("/api/monte-carlo");

export async function runMonteCarlo(params: {
  n_simulations: number;
  shock_mean: number;
  shock_std: number;
}): Promise<MonteCarloResult> {
  const res = await fetch(`${API_BASE}/api/monte-carlo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`monte-carlo -> ${res.status}`);
  return res.json() as Promise<MonteCarloResult>;
}

export async function runSimulationREST(
  bankId: string,
  shockMagnitude: number,
  algorithm: string
) {
  const res = await fetch(`${API_BASE}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      bank_id: bankId,
      shock_magnitude: shockMagnitude,
      algorithm,
    }),
  });
  if (!res.ok) throw new Error(`simulate -> ${res.status}`);
  return res.json();
}

/**
 * Node color mapping.
 *
 * Color is driven by the bank's DISTRESS LEVEL (how much equity it has lost),
 * which is the meaningful quantity to visualize. In DebtRank every affected
 * bank ends up INACTIVE (it propagated once and stopped) — but INACTIVE does
 * NOT mean "fine", so we must not gray those out or the whole network goes
 * gray. Gray is reserved for the rare case of an inactive bank with no distress.
 */
export function getNodeColor(distress: number, state: BankStatus): string {
  if (distress >= 1.0) return "#1a1a1a"; // defaulted: black
  if (distress >= 0.75) return "#dc2626"; // critical: red
  if (distress >= 0.5) return "#f97316"; // severe: orange
  if (distress >= 0.25) return "#eab308"; // moderate: yellow
  if (distress >= 0.05) return "#84cc16"; // slight stress: yellow-green
  if (distress > 0) return "#bef264"; // barely touched: pale lime
  if (state === "INACTIVE") return "#6b7280"; // inactive, no distress (rare)
  return "#16a34a"; // healthy: green
}

export function formatUSD(thousands: number): string {
  // FDIC values are in thousands of USD.
  const v = thousands * 1000;
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(2)}K`;
  return `$${v.toFixed(0)}`;
}

export function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}
