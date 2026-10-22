import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import type { MonteCarloResult } from "../types/simulation";
import { pct, runMonteCarlo } from "../lib/api";

interface Props {
  data: MonteCarloResult;
}

export default function MonteCarloResults({ data }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  // Local, re-runnable copy of the results (initialized from the precomputed prop).
  const [result, setResult] = useState<MonteCarloResult>(data);
  const [nSims, setNSims] = useState(data.n_simulations ?? 2000);
  const [shockMean, setShockMean] = useState(0.05);
  const [shockStd, setShockStd] = useState(0.15);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If the precomputed prop changes (first load), adopt it.
  useEffect(() => {
    setResult(data);
  }, [data]);

  const rerun = async () => {
    setRunning(true);
    setError(null);
    try {
      const r = await runMonteCarlo({
        n_simulations: nSims,
        shock_mean: shockMean,
        shock_std: shockStd,
      });
      setResult(r);
    } catch (e: any) {
      setError(e?.message ?? "Failed to run Monte Carlo");
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    const width = 720;
    const height = 380;
    const margin = { top: 36, right: 20, bottom: 44, left: 56 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr("viewBox", `0 0 ${width} ${height}`);
    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const bins = result.histogram.bins;
    const counts = result.histogram.counts;
    const x = d3.scaleLinear().domain([0, bins[bins.length - 1] ?? 1]).range([0, innerW]);
    const y = d3
      .scaleLinear()
      .domain([0, d3.max(counts) ?? 1])
      .range([innerH, 0]);

    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(x).tickFormat((d) => `${(Number(d) * 100).toFixed(0)}%`))
      .attr("color", "#94a3b8");
    g.append("g").call(d3.axisLeft(y).ticks(5)).attr("color", "#94a3b8");

    g.append("text")
      .attr("x", innerW / 2)
      .attr("y", innerH + 36)
      .attr("text-anchor", "middle")
      .attr("fill", "#94a3b8")
      .attr("font-size", 12)
      .text("Total system equity loss");

    // Bars
    g.selectAll("rect")
      .data(counts)
      .join("rect")
      .attr("x", (_d, i) => x(bins[i]))
      .attr("y", (d) => y(d))
      .attr("width", (_d, i) => Math.max(0, x(bins[i + 1]) - x(bins[i]) - 1))
      .attr("height", (d) => innerH - y(d))
      .attr("fill", "#3b82f6")
      .attr("opacity", 0.8);

    // Marker lines with staggered label rows so they never overlap.
    // Each marker gets its own vertical "lane" for its label.
    const marker = (value: number, label: string, color: string, lane: number) => {
      const labelY = -6 - lane * 14; // stack labels above the plot at different heights
      g.append("line")
        .attr("x1", x(value))
        .attr("x2", x(value))
        .attr("y1", labelY + 4)
        .attr("y2", innerH)
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "4 3");
      // little tick connecting the label to the line top
      g.append("text")
        .attr("x", x(value) + 4)
        .attr("y", labelY)
        .attr("fill", color)
        .attr("font-size", 11)
        .attr("font-weight", 600)
        .text(label);
    };

    // Sort markers by x so adjacent ones land in different lanes.
    const markers = [
      { v: result.expected_loss, l: `E[loss] ${pct(result.expected_loss)}`, c: "#22c55e" },
      { v: result.crisis_threshold, l: `Crisis ${pct(result.crisis_threshold)}`, c: "#a855f7" },
      { v: result.var_95, l: `VaR95 ${pct(result.var_95)}`, c: "#f59e0b" },
      { v: result.var_99, l: `VaR99 ${pct(result.var_99)}`, c: "#ef4444" },
    ].sort((a, b) => a.v - b.v);

    // Assign lanes: if a marker is close (in x) to the previous one, bump its lane.
    let prevX = -Infinity;
    let lane = 0;
    for (const m of markers) {
      const px = x(m.v);
      if (px - prevX < 90) {
        lane = (lane + 1) % 3; // cycle through 3 stacked lanes
      } else {
        lane = 0;
      }
      marker(m.v, m.l, m.c, lane);
      prevX = px;
    }
  }, [result]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card label="Expected Loss" value={pct(result.expected_loss)} />
        <Card label="VaR 95%" value={pct(result.var_95)} color="text-yellow-400" />
        <Card label="VaR 99%" value={pct(result.var_99)} color="text-red-400" />
        <Card label="CVaR 95%" value={pct(result.cvar_95)} color="text-red-500" />
        <Card label="P(Crisis)" value={pct(result.probability_crisis)} color="text-purple-400" />
      </div>

      {/* Interactive controls */}
      <div className="bg-panel rounded-lg p-4 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <Slider
          label={`Simulations: ${nSims.toLocaleString()}`}
          min={100}
          max={10000}
          step={100}
          value={nSims}
          onChange={setNSims}
        />
        <Slider
          label={`Avg shock: ${Math.round(shockMean * 100)}% of equity`}
          min={0}
          max={50}
          step={1}
          value={Math.round(shockMean * 100)}
          onChange={(v) => setShockMean(v / 100)}
        />
        <Slider
          label={`Shock volatility (σ): ${Math.round(shockStd * 100)}%`}
          min={1}
          max={50}
          step={1}
          value={Math.round(shockStd * 100)}
          onChange={(v) => setShockStd(v / 100)}
        />
        <button
          onClick={rerun}
          disabled={running}
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 rounded py-2 text-sm font-semibold"
        >
          {running ? "Running…" : "Re-run Simulation"}
        </button>
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      {/* Freshness / provenance line — proves each run is newly computed. */}
      <div className="text-xs text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
        <span>
          Showing <b className="text-gray-200">{result.n_simulations.toLocaleString()}</b> simulations
        </span>
        {result.shock_mean != null && (
          <span>
            avg shock <b className="text-gray-200">{Math.round((result.shock_mean ?? 0) * 100)}%</b>
          </span>
        )}
        {result.shock_std != null && (
          <span>
            σ <b className="text-gray-200">{Math.round((result.shock_std ?? 0) * 100)}%</b>
          </span>
        )}
        {result.min_loss != null && result.max_loss != null && (
          <span>
            loss range <b className="text-gray-200">{pct(result.min_loss)}</b> –{" "}
            <b className="text-gray-200">{pct(result.max_loss)}</b>
          </span>
        )}
        {result.median_loss != null && (
          <span>
            median <b className="text-gray-200">{pct(result.median_loss)}</b>
          </span>
        )}
        {result.computed_at && (
          <span className="text-gray-500">
            computed {new Date(result.computed_at).toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="bg-panel rounded-lg p-4">
        <svg ref={svgRef} className="w-full" />
      </div>

      <div className="text-sm text-gray-300 bg-panel rounded-lg p-4">
        There is a <b className="text-purple-400">{pct(result.probability_crisis)}</b>{" "}
        probability that a correlated market shock destroys more than{" "}
        <b>{pct(result.crisis_threshold)}</b> of total system equity (across{" "}
        {result.n_simulations.toLocaleString()} simulations).
      </div>
    </div>
  );
}

function Slider({
  label,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="text-xs text-gray-400">{label}</label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
    </div>
  );
}

function Card({
  label,
  value,
  color = "text-gray-100",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-panel rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
