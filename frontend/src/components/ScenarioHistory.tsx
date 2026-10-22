import type { ScenarioRun } from "../types/simulation";
import { useSimStore } from "../store";
import { pct } from "../lib/api";

export default function ScenarioHistory() {
  const history = useSimStore((s) => s.history);
  const loadHistory = useSimStore((s) => s.loadHistory);

  const exportRun = (run: ScenarioRun) => {
    const blob = new Blob([JSON.stringify(run, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scenario-${run.bankName.replace(/\s+/g, "_")}-${run.algorithm}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-panel rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wide">
        Scenario History
      </h2>
      {history.length === 0 && (
        <div className="text-xs text-gray-500">
          No runs yet. Trigger a failure to record a scenario.
        </div>
      )}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {history.map((run) => (
          <div
            key={run.id}
            className="bg-panelLight rounded p-2 text-xs hover:ring-1 hover:ring-blue-500"
          >
            <div className="flex justify-between">
              <span className="font-medium truncate pr-2">{run.bankName}</span>
              <span className="text-gray-400">{run.algorithm}</span>
            </div>
            <div className="text-gray-400 mt-0.5">
              shock {Math.round(run.shockMagnitude * 100)}% · loss{" "}
              {pct(run.totalSystemLoss)} · {run.numDefaults} defaults ·{" "}
              {run.contagionRounds} rounds
            </div>
            <div className="flex gap-2 mt-1">
              <button
                onClick={() => loadHistory(run)}
                className="bg-blue-600 hover:bg-blue-500 rounded px-2 py-0.5"
              >
                Replay
              </button>
              <button
                onClick={() => exportRun(run)}
                className="bg-gray-600 hover:bg-gray-500 rounded px-2 py-0.5"
              >
                Export JSON
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
