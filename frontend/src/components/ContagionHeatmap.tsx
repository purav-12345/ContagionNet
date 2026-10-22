import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { HeatmapData } from "../types/simulation";
import { pct } from "../lib/api";

interface Props {
  data: HeatmapData;
  onScenarioSelect: (rowBankId: string, colBankId: string) => void;
}

export default function ContagionHeatmap({ data, onScenarioSelect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const n = data.bank_ids.length;
  const cell = Math.max(6, Math.min(16, Math.floor(720 / Math.max(n, 1))));
  const size = n * cell;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const color = d3.scaleSequential(d3.interpolateReds).domain([0, 1]);
    ctx.clearRect(0, 0, size, size);
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        ctx.fillStyle = color(data.matrix[i][j]);
        ctx.fillRect(j * cell, i * cell, cell, cell);
      }
    }
  }, [data, n, cell, size]);

  const handleMove = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    const tooltip = tooltipRef.current;
    if (!canvas || !tooltip) return;
    const rect = canvas.getBoundingClientRect();
    const j = Math.floor((e.clientX - rect.left) / cell);
    const i = Math.floor((e.clientY - rect.top) / cell);
    if (i < 0 || j < 0 || i >= n || j >= n) {
      tooltip.style.opacity = "0";
      return;
    }
    const value = data.matrix[i][j];
    tooltip.style.opacity = "1";
    const wrapRect = wrapRef.current!.getBoundingClientRect();
    tooltip.style.left = `${e.clientX - wrapRect.left + 14}px`;
    tooltip.style.top = `${e.clientY - wrapRect.top + 14}px`;
    tooltip.innerHTML = `When <b>${data.bank_names[j]}</b> fails,<br/><b>${data.bank_names[i]}</b> loses <b>${pct(value)}</b> of its equity`;
  };

  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const j = Math.floor((e.clientX - rect.left) / cell);
    const i = Math.floor((e.clientY - rect.top) / cell);
    if (i < 0 || j < 0 || i >= n || j >= n) return;
    // Clicking cell (row i, col j) sets up: simulate column bank j's failure.
    onScenarioSelect(data.bank_ids[i], data.bank_ids[j]);
  };

  return (
    <div className="space-y-3">
      <div className="text-sm text-gray-300">
        Contagion heatmap — cell (row <i>i</i>, col <i>j</i>) = fraction of bank{" "}
        <i>i</i>'s equity lost when bank <i>j</i> fails. Click a cell to set up
        that scenario.
      </div>
      <div className="flex gap-4 items-start">
        <div ref={wrapRef} className="relative">
          <canvas
            ref={canvasRef}
            width={size}
            height={size}
            onMouseMove={handleMove}
            onMouseLeave={() => {
              if (tooltipRef.current) tooltipRef.current.style.opacity = "0";
            }}
            onClick={handleClick}
            className="border border-white/10 cursor-crosshair"
          />
          <div ref={tooltipRef} className="tooltip" style={{ opacity: 0 }} />
        </div>
        <div className="text-xs text-gray-400">
          <div className="mb-1">Initial failure → (columns)</div>
          <div>Affected bank ↓ (rows)</div>
          <ColorRamp />
        </div>
      </div>
    </div>
  );
}

function ColorRamp() {
  const stops = d3.range(0, 1.001, 0.1);
  return (
    <div className="mt-3">
      <div className="flex h-3 w-40">
        {stops.map((s) => (
          <div
            key={s}
            className="flex-1"
            style={{ background: d3.interpolateReds(s) }}
          />
        ))}
      </div>
      <div className="flex justify-between w-40 text-[10px] text-gray-500">
        <span>0%</span>
        <span>100% equity lost</span>
      </div>
    </div>
  );
}
