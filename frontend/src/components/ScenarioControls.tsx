import { useMemo, useState } from "react";
import type {
  AlgorithmType,
  NetworkData,
  SystemicRanking,
} from "../types/simulation";
import { useSimStore } from "../store";
import { pct } from "../lib/api";

interface Props {
  network: NetworkData;
  rankings: SystemicRanking[];
  isRunning: boolean;
  onRun: () => void;
  onStop: () => void;
}

const ALGORITHMS: { value: AlgorithmType; label: string }[] = [
  { value: "debtrank", label: "DebtRank (continuous distress)" },
  { value: "eisenberg_noe", label: "Eisenberg-Noe (clearing)" },
  { value: "threshold_cascade", label: "Threshold Cascade (domino)" },
];

export default function ScenarioControls({
  network,
  rankings,
  isRunning,
  onRun,
  onStop,
}: Props) {
  const selectedBankId = useSimStore((s) => s.selectedBankId);
  const setSelectedBank = useSimStore((s) => s.setSelectedBank);
  const shockMagnitude = useSimStore((s) => s.shockMagnitude);
  const setShockMagnitude = useSimStore((s) => s.setShockMagnitude);
  const algorithm = useSimStore((s) => s.algorithm);
  const setAlgorithm = useSimStore((s) => s.setAlgorithm);
  const stepDelayMs = useSimStore((s) => s.stepDelayMs);
  const setStepDelay = useSimStore((s) => s.setStepDelay);

  const [search, setSearch] = useState("");

  const rankByBankId = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of rankings) m[r.bank_id] = r.rank;
    return m;
  }, [rankings]);

  const filtered = useMemo(() => {
    const list = [...network.nodes].sort(
      (a, b) => (rankByBankId[a.id] ?? 9999) - (rankByBankId[b.id] ?? 9999)
    );
    if (!search.trim()) return list.slice(0, 200);
    const q = search.toLowerCase();
    return list.filter((n) => n.name.toLowerCase().includes(q)).slice(0, 200);
  }, [network.nodes, search, rankByBankId]);

  return (
    <div className="bg-panel rounded-lg p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wide">
        Shock Injector
      </h2>

      <div>
        <label className="text-xs text-gray-400">Bank (sorted by systemic rank)</label>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search banks…"
          className="w-full mt-1 bg-panelLight rounded px-2 py-1 text-sm outline-none border border-transparent focus:border-blue-500"
        />
        <div className="mt-2 max-h-44 overflow-y-auto rounded border border-white/5">
          {filtered.map((n) => (
            <button
              key={n.id}
              onClick={() => setSelectedBank(n.id)}
              className={`w-full text-left px-2 py-1 text-xs flex justify-between gap-2 ${
                n.id === selectedBankId
                  ? "bg-blue-600 text-white"
                  : "hover:bg-panelLight text-gray-300"
              }`}
            >
              <span className="truncate">
                #{rankByBankId[n.id] ?? "?"} {n.name}
              </span>
              <span className="opacity-70">{pct(n.systemic_importance)}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-400">
          Shock magnitude: {Math.round(shockMagnitude * 100)}% of equity
        </label>
        <input
          type="range"
          min={1}
          max={100}
          value={Math.round(shockMagnitude * 100)}
          onChange={(e) => setShockMagnitude(Number(e.target.value) / 100)}
          className="w-full"
        />
      </div>

      <div>
        <label className="text-xs text-gray-400">Algorithm</label>
        <select
          value={algorithm}
          onChange={(e) => setAlgorithm(e.target.value as AlgorithmType)}
          className="w-full mt-1 bg-panelLight rounded px-2 py-1 text-sm outline-none"
        >
          {ALGORITHMS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-gray-400">
          Animation speed: {stepDelayMs} ms / step
        </label>
        <input
          type="range"
          min={200}
          max={2000}
          step={100}
          value={stepDelayMs}
          onChange={(e) => setStepDelay(Number(e.target.value))}
          className="w-full"
        />
      </div>

      <div className="flex gap-2">
        {!isRunning ? (
          <button
            onClick={onRun}
            disabled={!selectedBankId}
            className="flex-1 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded py-2 text-sm font-semibold"
          >
            {selectedBankId ? "Trigger Failure" : "Select a bank"}
          </button>
        ) : (
          <button
            onClick={onStop}
            className="flex-1 bg-gray-600 hover:bg-gray-500 rounded py-2 text-sm font-semibold"
          >
            Stop
          </button>
        )}
      </div>
    </div>
  );
}
