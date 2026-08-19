"use client";

import Link from "next/link";
import {use, useEffect, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {Button} from "@/components/Button";
import {DiscountControl} from "@/components/DiscountControl";
import {FlagList} from "@/components/FlagList";
import {PaymentSchedule} from "@/components/PaymentSchedule";
import {QuoteTable} from "@/components/QuoteTable";
import {StatusPill} from "@/components/StatusPill";
import {api, ApiError, type ValidationFlag} from "@/lib/api";
import {demoQuote, versionIdForRoute, type DemoQuote} from "@/lib/demoData";
import {formatMinor} from "@/lib/format";

type PageProps = {params: Promise<{id: string}>};

function minorFromInput(value: string): number {
  const parsed = Number(value.replace(/,/g, ""));
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : 0;
}

export default function QuotePage({params}: PageProps) {
  const {id} = use(params);
  const [quote, setQuote] = useState<DemoQuote>(demoQuote);
  const [discount, setDiscount] = useState("0.00");
  const [tax, setTax] = useState("0.00");
  const [selectedOptionalIds, setSelectedOptionalIds] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [flags, setFlags] = useState<ValidationFlag[]>([]);

  useEffect(() => {
    api.get<any>(`/v1/proposal-versions/${versionIdForRoute(id)}`).then((response) => {
      if (response.quote?.lines?.length) setQuote((current) => ({...current, ...response.quote}));
    }).catch(() => setMessage("Fixture API unavailable; displayed quote is read-only."));
  }, [id]);

  const recalculate = async (nextOptionalIds = selectedOptionalIds) => {
    const discountMinor = minorFromInput(discount);
    const taxMinor = minorFromInput(tax);
    setFlags([]); setMessage("");
    const body = {currency: "USD", discountMinor, taxMinor, lines: quote.lines.map((line) => ({
      id: line.id, label: line.label, ruleId: line.ruleId, quantity: line.quantity,
      optional: line.optional, selected: line.optional ? nextOptionalIds.includes(line.id) : true,
      sourceRecordIds: [],
    }))};
    try {
      const response = await api.post<any>(`/v1/proposal-versions/${versionIdForRoute(id)}/quote/calculate`, body);
      setQuote((current) => ({...current, ...response, lines: response.lines.map((line: any) => ({
        ...line, ruleVersion: current.lines.find((item) => item.id === line.id)?.ruleVersion ?? response.pricingRuleVersion,
      }))}));
    } catch (error) {
      if (error instanceof ApiError && error.flags.length) setFlags(error.flags);
      else setMessage("The fixture API could not recalculate this quote.");
    }
  };

  const toggleOptional = (lineId: string, selected: boolean) => {
    const next = selected ? [...selectedOptionalIds, lineId] : selectedOptionalIds.filter((item) => item !== lineId);
    setSelectedOptionalIds(next);
    void recalculate(next);
  };

  return <AppShell><div className="workspace-page">
    <div className="page-heading"><div><p className="eyebrow">Pricing configurator / {id}</p><h1>Build a quote the team can defend.</h1><p className="lede">Every line carries the rule that priced it. Optional work never hides in the headline total.</p></div><StatusPill status={quote.status} /></div>
    <div className="workspace-nav"><Link href={`/proposals/${id}`}>Draft</Link><Link href={`/proposals/${id}/scope`}>Scope</Link><Link href={`/proposals/${id}/quote`}>Quote</Link><Link href={`/proposals/${id}/approval`}>Approval</Link></div>
    <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Quote lines</p><h2>Rule-backed services</h2></div><span className="muted-label">USD / minor-unit evidence</span></div><div className="quote-table-space"><QuoteTable lines={quote.lines} onOptionalToggle={toggleOptional} /></div></section>
    <div className="quote-grid"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">Controls</p><h2>Commercial terms</h2></div><span className="muted-label">Recalculate before submit</span></div><DiscountControl discount={discount} tax={tax} onDiscountChange={setDiscount} onTaxChange={setTax} /><Button onClick={() => void recalculate()} className="recalculate-button">Recalculate</Button>{message && <p className="adapter-error">{message}</p>}<FlagList flags={flags} /></section>
      <section className="panel totals-panel"><p className="eyebrow">Totals</p><div className="total-list"><div><span>Subtotal</span><strong data-testid="subtotal-minor" data-minor={quote.subtotalMinor}>{formatMinor(quote.subtotalMinor, quote.currency)}</strong></div><div><span>Discount</span><strong data-testid="discount-minor" data-minor={quote.discountMinor}>{formatMinor(quote.discountMinor, quote.currency)}</strong></div><div><span>Tax</span><strong data-testid="tax-minor" data-minor={quote.taxMinor}>{formatMinor(quote.taxMinor, quote.currency)}</strong></div><div className="grand-total"><span>Total</span><strong data-testid="total-minor" data-minor={quote.totalMinor}>{formatMinor(quote.totalMinor, quote.currency)}</strong></div></div>{quote.status === "review_required" && <div className="review-callout"><p>{quote.policyMessage ?? "This quote exceeds the configured discount policy."}</p></div>}</section></div>
    <section className="panel"><PaymentSchedule quote={quote} /></section>
  </div></AppShell>;
}
