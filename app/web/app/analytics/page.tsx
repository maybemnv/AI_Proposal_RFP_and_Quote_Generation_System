"use client";

import {useEffect, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {ChartTableView} from "@/components/ChartTableView";
import {EventTimeline} from "@/components/EventTimeline";
import {KpiTiles} from "@/components/KpiTiles";
import {ViewsBarChart} from "@/components/ViewsBarChart";
import {api} from "@/lib/api";
import {demoAnalytics, type AnalyticsData} from "@/lib/demoData";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData>(demoAnalytics);
  const [tableOpen, setTableOpen] = useState(false);
  useEffect(() => {
    api.get<AnalyticsData>("/v1/analytics/engagement").then(setData).catch(() => undefined);
  }, []);
  return <AppShell><div className="workspace-page"><div className="page-heading"><div><p className="eyebrow">Engagement analytics</p><h1>Know what happens after send.</h1><p className="lede">Provider activity stays connected to the proposal, while views are readable as a single time series.</p></div></div><KpiTiles kpis={data.kpis} /><div className="analytics-grid"><EventTimeline events={data.events} /><section className="panel chart-panel"><ViewsBarChart views={data.viewsByDay} /><ChartTableView views={data.viewsByDay} open={tableOpen} onToggle={() => setTableOpen((open) => !open)} /></section></div></div></AppShell>;
}
