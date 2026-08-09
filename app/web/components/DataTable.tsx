import type {ReactNode} from "react";

export type Column<T> = {key: string; label: string; render?: (row: T) => ReactNode};

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  rowLabel,
}: {columns: Column<T>[]; rows: T[]; rowLabel?: (row: T) => string}) {
  return <div className="table-wrap"><table className="data-table">
    <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)} aria-label={rowLabel?.(row)}>
      {columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : String(row[column.key] ?? "—")}</td>)}
    </tr>)}</tbody>
  </table></div>;
}
