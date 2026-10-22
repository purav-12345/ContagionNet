import { useMemo } from "react";
import type { SystemicRanking } from "../types/simulation";
import { useSimStore } from "../store";
import { pct } from "../lib/api";

interface Props {
  rankings: SystemicRanking[];
}

function systemStatus(loss: number): { label: string; color: string } {
  if (loss < 0.1) return { label: "STABLE", color: "text-green-400" };
  if (loss < 0.3) return { label: "STRESSED", color: "text-yellow-400" };
  return { label: "CRISIS", color: "text-red-500" };
}

export default function MetricsPanel({ rankings }: Props) {
  const currentStep = useSimStore((s) => s.currentStep);
  const bankStateById = useSimStore((s) => s.bankStateById);

  const totalLoss = currentStep?.total_system_loss ?? 0;
  const status = systemStatus(totalLoss);

  const numDefaulted = useMemo(
    () => Object.values(bankStateById).filter((b) => b.distress >= 1.0).length,
    [bankStateById]
  );
  const numDistressed = useMemo(
    () => Object.values(bankStateById).filter((b) => b.distress > 0).length,
    [bankStateById]
  );

  const top = rankings.slice(0, 10);
  const maxScore = top.length ? top[0].systemic_importance_score : 1;

  return (
    <div className="bg-panel rounded-lg p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wide">
        Systemic Risk Metrics
      </h2>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="System Equity Loss" value={pct(totalLoss)} valueClass="text-red-400 text-2xl" />
        <Stat label="System Status" value={status.label} valueClass={`${status.color} text-2xl`} />
        <Stat label="Banks Defaulted" value={String(numDefaulted)} />
        <Stat label="Banks Affected" value={String(numDistressed)} />
        <Stat label="Contagion Rounds" value={String(currentStep?.step ?? 0)} />
        <Stat
          label="Most Systemic"
          value={rankings[0]?.bank_name ?? "—"}
          valueClass="text-sm truncate"
        />
      </div>

      {currentStep && (currentStep.newly_distressed.length > 0 || currentStep.new_defaults.length > 0) && (
        <div className="text-xs text-gray-400">
          {currentStep.new_defaults.length > 0 && (
            <div className="text-red-400">
              Defaulted this round: {currentStep.new_defaults.length}
            </div>
          )}
          {currentStep.newly_distressed.length > 0 && (
            <div className="text-yellow-400">
              Newly distressed: {currentStep.newly_distressed.length}
            </div>
          )}
        </div>
      )}

      <div>
        <h3 className="text-xs text-gray-400 mb-2">Top 10 by Systemic Importance (SIR)</h3>
        <div className="space-y-1">
          {top.map((r) => (
            <div key={r.bank_id} className="text-xs">
              <div className="flex justify-between">
                <span className="truncate pr-2">
                  #{r.rank} {r.bank_name}
                </span>
                <span className="text-gray-400">{pct(r.systemic_importance_score)}</span>
              </div>
              <div className="h-1.5 bg-panelLight rounded mt-0.5">
                <div
                  className="h-1.5 bg-blue-500 rounded"
                  style={{
                    width: `${Math.max(
                      4,
                      (r.systemic_importance_score / (maxScore || 1)) * 100
                    )}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  valueClass = "text-xl",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="bg-panelLight rounded p-2">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`font-bold ${valueClass}`}>{value}</div>
    </div>
  );
}
