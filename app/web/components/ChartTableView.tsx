type View = {day: string; count: number};

export function ChartTableView({views, open, onToggle}: {views: View[]; open: boolean; onToggle: () => void}) {
  return <div className="chart-table-wrap"><button className="button button-secondary" onClick={onToggle}>{open ? "Chart view" : "Table view"}</button>{open && <table className="data-table chart-table"><thead><tr><th>Day</th><th>Views</th></tr></thead><tbody>{views.map((view) => <tr data-testid="chart-table-row" key={view.day}><td>{view.day}</td><td>{view.count}</td></tr>)}</tbody></table>}</div>;
}
