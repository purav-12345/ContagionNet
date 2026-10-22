import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import type {
  AlgorithmType,
  BankState,
  NetworkData,
  SimulationStep,
} from "../types/simulation";
import { getNodeColor, pct, runSimulationREST } from "../lib/api";
import { useSimStore } from "../store";

const ALGOS: { value: AlgorithmType; label: string }[] = [
  { value: "debtrank", label: "DebtRank" },
  { value: "eisenberg_noe", label: "Eisenberg-Noe" },
  { value: "threshold_cascade", label: "Threshold Cascade" },
];

interface Props {
  network: NetworkData;
}

export default function AlgorithmComparison({ network }: Props) {
  const selectedBankId = useSimStore((s) => s.selectedBankId);
  const shockMagnitude = useSimStore((s) => s.shockMagnitude);

  const [results, setResults] = useState<Record<AlgorithmType, SimulationStep[]>>(
    {} as any
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);

  const maxFrames = useMemo(() => {
    const lens = Object.values(results).map((s) => s.length);
    return lens.length ? Math.max(...lens) : 0;
  }, [results]);

  const runAll = async () => {
    if (!selectedBankId) return;
    setLoading(true);
    setError(null);
    try {
      const out: Record<string, SimulationStep[]> = {};
      for (const a of ALGOS) {
        const r = await runSimulationREST(selectedBankId, shockMagnitude, a.value);
        out[a.value] = r.steps;
      }
      setResults(out as any);
      setFrame(0);
      setPlaying(true);
    } catch (e: any) {
      setError(e.message ?? "Failed to run comparison");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!playing || maxFrames === 0) return;
    const id = setInterval(() => {
      setFrame((f) => {
        if (f + 1 >= maxFrames) {
          setPlaying(false);
          return f;
        }
        return f + 1;
      });
    }, 700);
    return () => clearInterval(id);
  }, [playing, maxFrames]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={runAll}
          disabled={!selectedBankId || loading}
          className="bg-red-600 hover:bg-red-500 disabled:bg-gray-600 rounded px-4 py-2 text-sm font-semibold"
        >
          {loading ? "Running…" : "Run all three algorithms"}
        </button>
        {selectedBankId ? (
          <span className="text-sm text-gray-400">
            Shocking{" "}
            {network.nodes.find((n) => n.id === selectedBankId)?.name} at{" "}
            {Math.round(shockMagnitude * 100)}%
          </span>
        ) : (
          <span className="text-sm text-yellow-400">
            Select a bank in the sidebar first.
          </span>
        )}
        {maxFrames > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => setPlaying((p) => !p)}
              className="bg-panelLight rounded px-3 py-1 text-sm"
            >
              {playing ? "Pause" : "Play"}
            </button>
            <input
              type="range"
              min={0}
              max={Math.max(0, maxFrames - 1)}
              value={frame}
              onChange={(e) => {
                setPlaying(false);
                setFrame(Number(e.target.value));
              }}
            />
            <span className="text-xs text-gray-400">
              step {frame + 1}/{maxFrames}
            </span>
          </div>
        )}
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {ALGOS.map((a) => (
          <ComparisonPanel
            key={a.value}
            title={a.label}
            network={network}
            steps={results[a.value]}
            frame={frame}
          />
        ))}
      </div>
    </div>
  );
}

function ComparisonPanel({
  title,
  network,
  steps,
  frame,
}: {
  title: string;
  network: NetworkData;
  steps?: SimulationStep[];
  frame: number;
}) {
  const step = steps ? steps[Math.min(frame, steps.length - 1)] : undefined;
  const finalStep = steps ? steps[steps.length - 1] : undefined;
  const stateById = useMemo(() => {
    const m: Record<string, BankState> = {};
    if (step) for (const b of step.banks) m[b.id] = b;
    return m;
  }, [step]);

  return (
    <div className="bg-panel rounded-lg p-3">
      <div className="flex justify-between items-baseline mb-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {finalStep && (
          <span className="text-xs text-gray-400">
            loss {pct(finalStep.total_system_loss)} ·{" "}
            {finalStep.banks.filter((b) => b.distress >= 1).length} defaults
          </span>
        )}
      </div>
      <MiniGraph network={network} stateById={stateById} />
    </div>
  );
}

function MiniGraph({
  network,
  stateById,
}: {
  network: NetworkData;
  stateById: Record<string, BankState>;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const positionsRef = useRef<Record<string, { x: number; y: number }>>({});
  const W = 320;
  const H = 240;

  // Compute a static layout once per network.
  useEffect(() => {
    const nodes = network.nodes.map((n) => ({ ...n })) as any[];
    const links = network.links.map((l) => ({ ...l })) as any[];
    const sim = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d: any) => d.id)
          .distance(30)
          .strength(0.2)
      )
      .force("charge", d3.forceManyBody().strength(-60))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .stop();
    for (let i = 0; i < 200; i++) sim.tick();
    const pos: Record<string, { x: number; y: number }> = {};
    for (const n of nodes) pos[n.id] = { x: n.x, y: n.y };
    positionsRef.current = pos;
    draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [network]);

  const draw = () => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${W} ${H}`);
    const pos = positionsRef.current;
    const rScale = d3
      .scaleSqrt()
      .domain([
        d3.min(network.nodes, (d) => d.total_assets) ?? 1,
        d3.max(network.nodes, (d) => d.total_assets) ?? 1,
      ])
      .range([2, 9]);
    svg
      .append("g")
      .selectAll("circle")
      .data(network.nodes)
      .join("circle")
      .attr("cx", (d) => pos[d.id]?.x ?? W / 2)
      .attr("cy", (d) => pos[d.id]?.y ?? H / 2)
      .attr("r", (d) => rScale(Math.max(d.total_assets, 1)))
      .attr("fill", (d) => {
        const st = stateById[d.id];
        return st ? getNodeColor(st.distress, st.state) : "#16a34a";
      })
      .attr("stroke", "#0b0f17")
      .attr("stroke-width", 0.5);
  };

  // Redraw on state change (positions stay fixed).
  useEffect(() => {
    if (Object.keys(positionsRef.current).length) draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateById]);

  return <svg ref={svgRef} className="w-full" style={{ height: H }} />;
}
