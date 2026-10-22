export type BankStatus = "UNDISTRESSED" | "DISTRESSED" | "INACTIVE";
export type AlgorithmType = "debtrank" | "eisenberg_noe" | "threshold_cascade";

export interface BankState {
  id: string;
  name: string;
  distress: number;
  state: BankStatus;
  equity_remaining: number;
}

export interface SimulationStep {
  step: number;
  banks: BankState[];
  total_system_loss: number;
  new_defaults: string[];
  newly_distressed: string[];
  simulation_complete: boolean;
  error?: string;
}

export interface NetworkNode {
  id: string;
  name: string;
  total_assets: number;
  equity: number;
  interbank_assets: number;
  interbank_liabilities: number;
  degree_centrality: number;
  betweenness_centrality: number;
  eigenvector_centrality: number;
  systemic_importance: number;
  lcr: number;
  // d3-force runtime fields
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface NetworkLink {
  source: string | NetworkNode;
  target: string | NetworkNode;
  weight: number;
}

export interface NetworkData {
  nodes: NetworkNode[];
  links: NetworkLink[];
  total_banks: number;
  total_system_equity: number;
  total_system_assets: number;
}

export interface SystemicRanking {
  rank: number;
  bank_id: string;
  bank_name: string;
  systemic_importance_score: number;
  num_defaults_caused: number;
  total_system_loss: number;
  contagion_rounds: number;
}

export interface SystemicImportanceResponse {
  rankings: SystemicRanking[];
  computed_at: string;
}

export interface MonteCarloResult {
  loss_distribution: number[];
  expected_loss: number;
  var_95: number;
  var_99: number;
  cvar_95: number;
  probability_crisis: number;
  crisis_threshold: number;
  n_simulations: number;
  min_loss?: number;
  max_loss?: number;
  median_loss?: number;
  shock_mean?: number;
  shock_std?: number;
  computed_at?: string;
  histogram: {
    bins: number[];
    counts: number[];
  };
}

export interface HeatmapData {
  matrix: number[][];
  bank_ids: string[];
  bank_names: string[];
}

export interface ScenarioRun {
  id: string;
  bankId: string;
  bankName: string;
  algorithm: AlgorithmType;
  shockMagnitude: number;
  totalSystemLoss: number;
  numDefaults: number;
  contagionRounds: number;
  steps: SimulationStep[];
  timestamp: number;
}
