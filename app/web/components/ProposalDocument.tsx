import {QuoteTable} from "@/components/QuoteTable";
import {PaymentSchedule} from "@/components/PaymentSchedule";
import {formatMinor} from "@/lib/format";
import {demoQuote, previewSectionOrder, type DemoQuote} from "@/lib/demoData";

export function ProposalDocument({quote = demoQuote}: {quote?: DemoQuote}) {
  const mandatoryLines = quote.lines.filter((line) => !line.optional);
  const optionalTotal = quote.lines.filter((line) => line.optional).reduce((sum, line) => sum + line.subtotalMinor, 0);
  const copy: Record<string, string> = {
    "Executive summary": "Northwind gets a clear proposition, a launch-ready design system, and an accountable path from alignment to handover.",
    Understanding: "The work responds to a fragmented customer journey, inconsistent publishing patterns, and a need for measurable launch readiness.",
    Scope: "Four facilitated workshops, priority journey design, an accessible component system, and a documented handover are included.",
    Milestones: "Alignment complete, design system accepted, priority build ready, and launch readiness are the four decision gates.",
    Assumptions: "Northwind provides subject-matter experts, approved copy, and steering-group decisions within five working days.",
    "Case studies": "A comparable retailer reduced onboarding time by 40% and moved time to first value from six weeks to three weeks.",
    "Next steps": "Confirm the legacy CMS decision, nominate workshop attendees, and approve the first milestone.",
  };
  return <article className="proposal-document"><div className="document-cover"><p className="eyebrow">Arc / Studio client proposal</p><h1>Brand refresh and site rebuild</h1><p>Prepared for Northwind Retail Group · Version 1</p></div>{previewSectionOrder.map((heading) => <section className="preview-section" data-section={heading} data-testid={heading === "Options" ? "options-section" : undefined} key={heading}><h2>{heading}</h2>{heading === "Options" ? <div className="option-summary"><p><strong>Optional</strong> services are available without changing the headline commitment.</p><div className="option-line"><span>Training session</span><span data-minor={optionalTotal} data-testid="optional-total-minor">{formatMinor(optionalTotal, quote.currency)}</span></div></div> : heading === "Pricing" ? <><QuoteTable lines={mandatoryLines} onOptionalToggle={() => undefined} readOnly /><div className="preview-total"><span>Headline total</span><strong data-testid="total-minor" data-minor={quote.totalMinor}>{formatMinor(quote.totalMinor, quote.currency)}</strong></div></> : heading === "Payment schedule" ? <PaymentSchedule quote={quote} showHeading={false} /> : <p>{copy[heading] ?? "The proposal uses source-linked content and a clear decision trail."}</p>}</section>)}</article>;
}
