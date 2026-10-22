import { useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";
import type { NetworkData, NetworkLink, NetworkNode } from "../types/simulation";
import { formatUSD, getNodeColor, pct } from "../lib/api";
import { useSimStore } from "../store";

interface Props {
  data: NetworkData;
  rankByBankId: Record<string, number>;
  height?: number;
}

export default function NetworkGraph({ data, rankByBankId, height = 640 }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const nodeSelRef = useRef<d3.Selection<SVGCircleElement, NetworkNode, any, any> | null>(null);

  const bankStateById = useSimStore((s) => s.bankStateById);
  const setSelectedBank = useSimStore((s) => s.setSelectedBank);
  const selectedBankId = useSimStore((s) => s.selectedBankId);

  // Stable copies for the force simulation (d3 mutates node/link objects).
  const { nodes, links } = useMemo(() => {
    const nodes = data.nodes.map((n) => ({ ...n }));
    const links = data.links.map((l) => ({ ...l }));
    return { nodes, links };
  }, [data]);

  // Build the force layout once per dataset.
  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;
    const width = containerRef.current.clientWidth || 800;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const root = svg.append("g");

    // Node radius by sqrt(assets), normalized to [8, 40].
    const assetExtent = d3.extent(nodes, (d) => d.total_assets) as [number, number];
    const rScale = d3
      .scaleSqrt()
      .domain([Math.max(assetExtent[0], 1), Math.max(assetExtent[1], 1)])
      .range([8, 40]);
    const nodeRadius = (d: NetworkNode) => rScale(Math.max(d.total_assets, 1));

    const weightExtent = d3.extent(links, (l) => l.weight) as [number, number];
    const widthScale = d3
      .scaleLinear()
      .domain([Math.max(weightExtent[0], 0), Math.max(weightExtent[1], 1)])
      .range([1, 4]);
    const opacityScale = d3
      .scaleLinear()
      .domain([Math.max(weightExtent[0], 0), Math.max(weightExtent[1], 1)])
      .range([0.06, 0.4]);

    const linkSel = root
      .append("g")
      .attr("stroke", "#64748b")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-width", (d) => widthScale(d.weight))
      .attr("stroke-opacity", (d) => opacityScale(d.weight));

    const nodeSel = root
      .append("g")
      .attr("stroke", "#0b0f17")
      .attr("stroke-width", 1.5)
      .selectAll<SVGCircleElement, NetworkNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", nodeRadius)
      .attr("fill", "#16a34a")
      .style("cursor", "pointer");
    nodeSelRef.current = nodeSel;

    const tooltip = d3.select(tooltipRef.current);

    nodeSel
      .on("mouseover", (event, d) => {
        const st = useSimStore.getState().bankStateById[d.id];
        const rank = rankByBankId[d.id];
        tooltip
          .style("opacity", "1")
          .html(
            `<div style="font-weight:600;margin-bottom:4px">${d.name}</div>` +
              `Assets: ${formatUSD(d.total_assets)}<br/>` +
              `Equity: ${formatUSD(d.equity)}<br/>` +
              `LCR: ${(d.lcr * 100).toFixed(0)}%<br/>` +
              `SIR rank: #${rank ?? "?"} (${pct(d.systemic_importance)})<br/>` +
              (st
                ? `Distress: ${pct(st.distress)} — ${st.state}`
                : `Distress: 0.0% — UNDISTRESSED`)
          );
      })
      .on("mousemove", (event) => {
        const [x, y] = d3.pointer(event, containerRef.current);
        tooltip.style("left", `${x + 14}px`).style("top", `${y + 14}px`);
      })
      .on("mouseout", () => tooltip.style("opacity", "0"))
      .on("click", (_event, d) => setSelectedBank(d.id));

    const drag = d3
      .drag<SVGCircleElement, NetworkNode>()
      .on("start", (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
    nodeSel.call(drag as any);

    const sim = d3
      .forceSimulation<NetworkNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<NetworkNode, NetworkLink>(links)
          .id((d) => d.id)
          .distance(80)
          .strength(0.3)
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<NetworkNode>().radius((d) => nodeRadius(d) + 5)
      );

    sim.on("tick", () => {
      linkSel
        .attr("x1", (d) => (d.source as NetworkNode).x ?? 0)
        .attr("y1", (d) => (d.source as NetworkNode).y ?? 0)
        .attr("x2", (d) => (d.target as NetworkNode).x ?? 0)
        .attr("y2", (d) => (d.target as NetworkNode).y ?? 0);
      nodeSel.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
    });

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 6])
      .on("zoom", (event) => root.attr("transform", event.transform));
    svg.call(zoom as any);

    return () => {
      sim.stop();
    };
  }, [nodes, links, height, rankByBankId, setSelectedBank]);

  // Live recolor on each simulation step — only update fill, do not re-run sim.
  useEffect(() => {
    const nodeSel = nodeSelRef.current;
    if (!nodeSel) return;
    nodeSel
      .transition()
      .duration(600)
      .attr("fill", (d) => {
        const st = bankStateById[d.id];
        if (!st) return "#16a34a";
        return getNodeColor(st.distress, st.state);
      });
  }, [bankStateById]);

  // Highlight the selected (shock target) node.
  useEffect(() => {
    const nodeSel = nodeSelRef.current;
    if (!nodeSel) return;
    nodeSel
      .attr("stroke", (d) => (d.id === selectedBankId ? "#f8fafc" : "#0b0f17"))
      .attr("stroke-width", (d) => (d.id === selectedBankId ? 3 : 1.5));
  }, [selectedBankId]);

  return (
    <div ref={containerRef} className="relative w-full" style={{ height }}>
      <svg ref={svgRef} className="w-full h-full" />
      <div ref={tooltipRef} className="tooltip" style={{ opacity: 0 }} />
      <Legend />
    </div>
  );
}

function Legend() {
  const items = [
    ["#16a34a", "Healthy (0%)"],
    ["#84cc16", "Slight (5–25%)"],
    ["#eab308", "Stressed (25–50%)"],
    ["#f97316", "Severe (50–75%)"],
    ["#dc2626", "Critical (75–99%)"],
    ["#1a1a1a", "Defaulted (100%)"],
  ];
  return (
    <div className="absolute bottom-3 left-3 bg-black/40 rounded-md px-3 py-2 text-xs space-y-1">
      {items.map(([c, label]) => (
        <div key={label} className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded-full border border-black/50"
            style={{ background: c }}
          />
          <span className="text-gray-300">{label}</span>
        </div>
      ))}
    </div>
  );
}
