import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchHeatmap,
  fetchMonteCarlo,
  fetchNetwork,
  fetchSystemicImportance,
} from "./lib/api";
import { useContagionSocket } from "./hooks/useContagionSocket";
import { useSimStore } from "./store";
import type { ScenarioRun, SimulationStep } from "./types/simulation";

import NetworkGraph from "./components/NetworkGraph";
import ContagionHeatmap from "./components/ContagionHeatmap";
import MetricsPanel from "./components/MetricsPanel";
import ScenarioControls from "./components/ScenarioControls";
import AlgorithmComparison from "./components/AlgorithmComparison";
import MonteCarloResults from "./components/MonteCarloResults";
import ScenarioHistory from "./components/ScenarioHistory";

type Tab = "network" | "heatmap" | "comparison" | "montecarlo";

const TABS: { id: Tab; label: string }[] = [
  { id: "network", label: "Network Graph" },
  { id: "heatmap", label: "Contagion Heatmap" },
  { id: "comparison", label: "Algorithm Comparison" },
  { id: "montecarlo", label: "Monte Carlo" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("network");
  const [wsError, setWsError] = useState<string | null>(null);

  const applyStep = useSimStore((s) => s.applyStep);
  const resetSimulation = useSimStore((s) => s.resetSimulation);
  const setRunning = useSimStore((s) => s.setRunning);
  const addHistory = useSimStore((s) => s.addHistory);
  const setSelectedBank = useSimStore((s) => s.setSelectedBank);
  const setAlgorithm = useSimStore((s) => s.setAlgorithm);
  const selectedBankId = useSimStore((s) => s.selectedBankId);
  const shockMagnitude = useSimStore((s) => s.shockMagnitude);
  const algorithm = useSimStore((s) => s.algorithm);
  const stepDelayMs = useSimStore((s) => s.stepDelayMs);

  const networkQ = useQuery({ queryKey: ["network"], queryFn: fetchNetwork });
  const sirQ = useQuery({
    queryKey: ["sir"],
    queryFn: fetchSystemicImportance,
  });
  const heatmapQ = useQuery({ queryKey: ["heatmap"], queryFn: fetchHeatmap });
  const mcQ = useQuery({ queryKey: ["montecarlo"], queryFn: fetchMonteCarlo });

  const rankings = sirQ.data?.rankings ?? [];
  const rankByBankId = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of rankings) m[r.bank_id] = r.rank;
    return m;
  }, [rankings]);

  const { runSimulation, stopSimulation, isRunning } = useContagionSocket({
    onStep: (step: SimulationStep) => applyStep(step),
    onComplete: (steps: SimulationStep[]) => {
      setRunning(false);
      const last = steps[steps.length - 1];
      if (last && selectedBankId) {
        const node = networkQ.data?.nodes.find((n) => n.id === selectedBankId);
        const run: ScenarioRun = {
          id: `${Date.now()}`,
          bankId: selectedBankId,
          bankName: node?.name ?? selectedBankId,
          algorithm,
          shockMagnitude,
          totalSystemLoss: last.total_system_loss,
          numDefaults: last.banks.filter((b) => b.distress >= 1).length,
          contagionRounds: last.step,
          steps,
          timestamp: Date.now(),
        };
        addHistory(run);
      }
    },
    onError: (e) => {
      setWsError(e);
      setRunning(false);
    },
  });

  const handleRun = () => {
    if (!selectedBankId) return;
    setWsError(null);
    resetSimulation();
    setRunning(true);
    runSimulation({
      bank_id: selectedBankId,
      shock_magnitude: shockMagnitude,
      algorithm,
      step_delay_ms: stepDelayMs,
    });
  };

  const handleStop = () => {
    stopSimulation();
    setRunning(false);
  };

  const handleHeatmapSelect = (_rowBankId: string, colBankId: string) => {
    // Clicking cell (row i, col j) -> simulate column bank j's failure.
    setSelectedBank(colBankId);
    setAlgorithm("debtrank");
    setTab("network");
  };

  if (networkQ.isLoading || sirQ.isLoading) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400">
        Loading interbank network &amp; precomputed analytics…
      </div>
    );
  }

  if (networkQ.isError || !networkQ.data) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center gap-2">
        <div className="text-red-400 text-lg">Failed to load backend.</div>
        <div className="text-gray-400 text-sm">
          Is the API running at the configured base URL? Start the backend, then
          reload.
        </div>
        <div className="text-gray-600 text-xs">{String(networkQ.error)}</div>
      </div>
    );
  }

  const network = networkQ.data;

  return (
    <div className="h-full flex flex-col">
      <header className="px-5 py-3 border-b border-white/10 flex items-center gap-4">
        <h1 className="text-lg font-semibold">
          Real-Time Systemic Risk Contagion Simulator
        </h1>
        <span className="text-xs text-gray-400">
          {network.total_banks} banks · system equity{" "}
          {(network.total_system_equity * 1000) / 1e12 >= 1
            ? `$${((network.total_system_equity * 1000) / 1e12).toFixed(2)}T`
            : `$${((network.total_system_equity * 1000) / 1e9).toFixed(1)}B`}
        </span>
        {isRunning && (
          <span className="text-xs text-green-400 animate-pulse ml-auto">
            ● simulating…
          </span>
        )}
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-80 shrink-0 border-r border-white/10 p-4 space-y-4 overflow-y-auto">
          <ScenarioControls
            network={network}
            rankings={rankings}
            isRunning={isRunning}
            onRun={handleRun}
            onStop={handleStop}
          />
          <MetricsPanel rankings={rankings} />
          <ScenarioHistory />
        </aside>

        {/* Main */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <nav className="flex gap-1 px-4 pt-3 border-b border-white/10">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-4 py-2 text-sm rounded-t ${
                  tab === t.id
                    ? "bg-panel text-white"
                    : "text-gray-400 hover:text-gray-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>

          <div className="flex-1 overflow-auto p-4">
            {wsError && (
              <div className="mb-3 text-sm text-red-400 bg-red-950/40 rounded px-3 py-2">
                {wsError}
              </div>
            )}

            {tab === "network" && (
              <NetworkGraph data={network} rankByBankId={rankByBankId} />
            )}

            {tab === "heatmap" &&
              (heatmapQ.data ? (
                <ContagionHeatmap
                  data={heatmapQ.data}
                  onScenarioSelect={handleHeatmapSelect}
                />
              ) : (
                <Loading label="heatmap" />
              ))}

            {tab === "comparison" && <AlgorithmComparison network={network} />}

            {tab === "montecarlo" &&
              (mcQ.data ? (
                <MonteCarloResults data={mcQ.data} />
              ) : (
                <Loading label="Monte Carlo results" />
              ))}
          </div>
        </main>
      </div>
    </div>
  );
}

function Loading({ label }: { label: string }) {
  return <div className="text-gray-400 text-sm">Loading {label}…</div>;
}
