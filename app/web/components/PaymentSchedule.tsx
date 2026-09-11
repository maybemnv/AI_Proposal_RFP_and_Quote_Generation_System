import type {DemoQuote} from "@/lib/demoData";
import {formatMinor} from "@/lib/format";

export function PaymentSchedule({quote, showHeading = true}: {quote: DemoQuote; showHeading?: boolean}) {
  return <div className="payment-schedule">{showHeading && <div className="panel-heading"><div><p className="eyebrow">Payment schedule</p><h2>Three predictable gates</h2></div><span className="muted-label">Server-calculated</span></div>}
    <div className="installment-list">{quote.paymentSchedule.map((item) => <div className="installment" data-testid="installment" data-minor={item.amountMinor} key={item.id}><span><strong>{item.label}</strong>{item.percent !== undefined && <small>{item.percent}% of total</small>}{item.dueDescription && <small>{item.dueDescription}</small>}</span><strong>{formatMinor(item.amountMinor, quote.currency)}</strong></div>)}</div>
  </div>;
}
