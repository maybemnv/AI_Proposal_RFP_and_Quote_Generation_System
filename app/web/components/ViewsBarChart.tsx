"use client";

import {useState} from "react";

type View = {day: string; count: number};

export function ViewsBarChart({views}: {views: View[]}) {
  const [hovered, setHovered] = useState<View | null>(null);
  const width = 760;
  const height = 300;
  const baseline = 240;
  const left = 48;
  const chartWidth = 680;
  const max = Math.max(...views.map((view) => view.count), 1);
  const barWidth = 54;
  const gap = (chartWidth - barWidth * views.length) / Math.max(views.length - 1, 1);
  const maxIndex = views.findIndex((view) => view.count === max);
  const latestIndex = views.length - 1;
  return <div className="views-chart-wrap"><div className="chart-heading"><div><p className="eyebrow">Views over time</p><h2>Document views</h2></div><span className="muted-label">Single series · views</span></div><div className="chart-shell" data-testid="views-chart"><svg className="views-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Document views by day"><line data-testid="y-axis" x1={left} y1="20" x2={left} y2={baseline} /><line data-testid="x-axis" x1={left} y1={baseline} x2={left + chartWidth} y2={baseline} />{views.map((view, index) => { const x = left + index * (barWidth + gap); const barHeight = Math.max(4, (view.count / max) * 190); const y = baseline - barHeight; return <g key={view.day}><rect data-testid="bar" x={x} y={y} width={barWidth} height={barHeight} rx="4" fill="var(--accent)" />{(index === maxIndex || index === latestIndex) && <text data-testid="bar-label" x={x + barWidth / 2} y={y - 8} textAnchor="middle">{view.count}</text>}<text className="bar-day" x={x + barWidth / 2} y={baseline + 22} textAnchor="middle">{view.day.slice(5)}</text><rect data-testid="bar-hit" className="bar-hit" x={x - gap / 2} y="20" width={barWidth + gap} height={baseline - 20} fill="transparent" onMouseEnter={() => setHovered(view)} onMouseLeave={() => setHovered(null)} /></g>})}</svg>{hovered && <div className="chart-tooltip" data-testid="chart-tooltip"><strong>{hovered.day}</strong><span>{hovered.count} view{hovered.count === 1 ? "" : "s"}</span></div>}</div></div>;
}
