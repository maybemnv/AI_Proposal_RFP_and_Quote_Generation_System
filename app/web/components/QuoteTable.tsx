import type {DemoQuoteLine} from "@/lib/demoData";
import {formatMinor} from "@/lib/format";

type QuoteTableProps = {
  lines: DemoQuoteLine[];
  onOptionalToggle: (lineId: string, selected: boolean) => void;
  readOnly?: boolean;
};

export function QuoteTable({lines, onOptionalToggle, readOnly = false}: QuoteTableProps) {
  return <div className="table-wrap"><table className="data-table quote-table"><thead><tr>
    <th>Line</th><th>Rule</th><th>Qty</th><th>Unit price</th><th>Subtotal</th>
  </tr></thead><tbody>{lines.map((line) => <tr data-testid="quote-line" key={line.id}>
    <td><label className="quote-line-label">{line.optional && <input type="checkbox" data-testid={line.id} checked={line.selected} disabled={readOnly} onChange={(event) => onOptionalToggle(line.id, event.target.checked)} />}<span>{line.label}</span>{line.optional && <small>Optional</small>}</label></td>
    <td><span data-testid="rule-version" className="rule-version">{line.ruleVersion}</span><small className="table-subline">{line.ruleId}</small></td>
    <td>{line.quantity}{line.unit ? ` ${line.unit}` : ""}</td>
    <td data-minor={line.unitPriceMinor}>{formatMinor(line.unitPriceMinor)}</td>
    <td data-minor={line.subtotalMinor}>{formatMinor(line.subtotalMinor)}</td>
  </tr>)}</tbody></table></div>;
}
