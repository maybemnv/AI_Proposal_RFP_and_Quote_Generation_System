export function StatTile({label, value, delta}: {label: string; value: string; delta?: string}) {
  return <article className="stat-tile" data-testid="kpi-tile">
    <span className="eyebrow">{label}</span><strong>{value}</strong>{delta && <small>{delta}</small>}
  </article>;
}
