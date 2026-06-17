import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { useAgents } from "@/hooks/useAgents";

const COLORS = ["#00D2FF", "#7B2FFF", "#00FF88", "#FF9500", "#FF3366"];

/**
 * d3 chord diagram of flow volume between agents. Each arc is a pipeline stage;
 * ribbons show how much work flows between them (including feedback loops).
 */
export function ArcDiagram() {
  const ref = useRef<SVGSVGElement>(null);
  const { pipeline, edges } = useAgents();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();
    if (!pipeline.length) return;

    const idx = new Map(pipeline.map((n, i) => [n, i]));
    const n = pipeline.length;
    const matrix: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));
    for (const e of edges) {
      const a = idx.get(e.source);
      const b = idx.get(e.target);
      if (a == null || b == null) continue;
      matrix[a][b] += (e.volume ?? 0) + 1;
    }

    const width = 320;
    const height = 320;
    const outer = Math.min(width, height) * 0.5 - 24;
    const inner = outer - 12;

    const g = svg
      .attr("viewBox", `0 0 ${width} ${height}`)
      .append("g")
      .attr("transform", `translate(${width / 2},${height / 2})`);

    const chord = d3.chord().padAngle(0.06).sortSubgroups(d3.descending)(matrix);
    const arc = d3.arc<d3.ChordGroup>().innerRadius(inner).outerRadius(outer);
    const ribbon = d3.ribbon<d3.Chord, d3.ChordSubgroup>().radius(inner);

    // group arcs
    g.append("g")
      .selectAll("path")
      .data(chord.groups)
      .join("path")
      .attr("d", arc as never)
      .attr("fill", (d) => COLORS[d.index % COLORS.length])
      .attr("stroke", "rgba(2,4,10,0.8)")
      .style("filter", (d) => `drop-shadow(0 0 6px ${COLORS[d.index % COLORS.length]})`);

    // labels
    g.append("g")
      .selectAll("text")
      .data(chord.groups)
      .join("text")
      .each((d: any) => (d.angle = (d.startAngle + d.endAngle) / 2))
      .attr("dy", "0.35em")
      .attr("font-size", 9)
      .attr("font-family", "JetBrains Mono, monospace")
      .attr("fill", "#E8F4FF")
      .attr("transform", (d: any) => {
        const rot = (d.angle * 180) / Math.PI - 90;
        return `rotate(${rot}) translate(${outer + 6}) ${d.angle > Math.PI ? "rotate(180)" : ""}`;
      })
      .attr("text-anchor", (d: any) => (d.angle > Math.PI ? "end" : "start"))
      .text((d) => pipeline[d.index].replace(/_/g, " "));

    // ribbons
    g.append("g")
      .attr("fill-opacity", 0.55)
      .selectAll("path")
      .data(chord)
      .join("path")
      .attr("d", ribbon as never)
      .attr("fill", (d) => COLORS[d.source.index % COLORS.length])
      .attr("stroke", "rgba(0,210,255,0.15)");
  }, [pipeline, edges]);

  return <svg ref={ref} className="h-full w-full" />;
}
