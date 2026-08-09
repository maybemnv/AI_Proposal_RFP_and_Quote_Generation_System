import {StatTile} from "@/components/StatTile";
import {formatMinor} from "@/lib/format";
import type {AnalyticsKpi} from "@/lib/demoData";

export function KpiTiles({kpis}: {kpis: AnalyticsKpi[]}) {
  return <div className="stat-grid analytics-kpis">{kpis.map((kpi) => <StatTile key={kpi.key} label={kpi.label} value={kpi.valueMinor !== undefined ? formatMinor(kpi.valueMinor) : `${kpi.value ?? 0} ${kpi.unit}`} />)}</div>;
}
