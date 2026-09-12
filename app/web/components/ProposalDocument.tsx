import {PaymentSchedule} from "@/components/PaymentSchedule";
import {QuoteTable} from "@/components/QuoteTable";
import {formatMinor} from "@/lib/format";
import {previewSectionOrder, type DemoQuote} from "@/lib/demoData";

type PreviewSection = {key: string; blocks: {blockId: string; content: string}[]};
type PreviewScope = {
  deliverables: {id: string; name: string; description: string; quantity: number; unit: string; optional?: boolean}[];
  milestones: {id: string; name: string; sequence: number; targetDescription: string}[];
  assumptions: {id: string; text: string; customerConfirmationRequired?: boolean}[];
  exclusions: string[];
};

export type ProposalDocumentVersion = {
  title: string;
  versionNumber: number;
  scope: PreviewScope;
  quote: DemoQuote;
  sections: PreviewSection[];
};

const sectionKeys: Record<string, string> = {
  "Executive summary": "executive_summary", Understanding: "understanding", Scope: "scope",
  Milestones: "milestones", Assumptions: "assumptions", Options: "options", Pricing: "pricing",
  "Payment schedule": "payment_schedule", "Case studies": "case_studies", "Next steps": "next_steps",
  "RFP answers": "rfp_answers",
};

export function ProposalDocument({version}: {version: ProposalDocumentVersion}) {
  const sectionByKey = new Map(version.sections.map((section) => [section.key, section]));
  const order = version.sections.some((section) => section.key === "rfp_answers")
    ? [...previewSectionOrder.slice(0, -1), "RFP answers", "Next steps"]
    : previewSectionOrder;
  const optionalLines = version.quote.lines.filter((line) => line.optional);

  return <article className="proposal-document">
    <div className="document-cover"><p className="eyebrow">Arc / Studio client proposal</p><h1>{version.title}</h1><p>Version {version.versionNumber}</p></div>
    {order.map((heading) => {
      const section = sectionByKey.get(sectionKeys[heading]);
      if (heading === "Options" && !optionalLines.length) return null;
      if (heading === "Payment schedule" && !version.quote.paymentSchedule.length) return null;
      return <section className="preview-section" data-section={heading} data-testid={heading === "Options" ? "options-section" : undefined} key={heading}>
        <h2>{heading}</h2>
        {section?.blocks.map((block) => <p key={block.blockId}>{block.content}</p>)}
        {heading === "Scope" && <>
          {version.scope.deliverables.length > 0 && <ul>{version.scope.deliverables.map((item) => <li key={item.id}><strong>{item.name}</strong>{item.optional && <span className="optional-tag">Optional</span>} — {item.description} ({item.quantity} {item.unit})</li>)}</ul>}
          {version.scope.exclusions.length > 0 && <p className="note">Not included: {version.scope.exclusions.join("; ")}.</p>}
        </>}
        {heading === "Milestones" && version.scope.milestones.length > 0 && <ul>{version.scope.milestones.map((item) => <li key={item.id}><strong>{item.sequence}. {item.name}</strong> — {item.targetDescription}</li>)}</ul>}
        {heading === "Assumptions" && version.scope.assumptions.length > 0 && <ul>{version.scope.assumptions.map((item) => <li key={item.id}>{item.text}{item.customerConfirmationRequired && <em> (confirmation required)</em>}</li>)}</ul>}
        {heading === "Options" && <div className="option-summary"><p><strong>Optional</strong> services are available without changing the headline commitment.</p>{optionalLines.map((line) => <div className="option-line" data-minor={line.subtotalMinor} data-selected={String(line.selected)} data-testid="optional-line" key={line.id}><span>{line.label}</span><span>{formatMinor(line.subtotalMinor, version.quote.currency)}</span></div>)}</div>}
        {heading === "Pricing" && <><QuoteTable lines={version.quote.lines} onOptionalToggle={() => undefined} readOnly /><div className="preview-total"><span>Headline total</span><strong data-testid="total-minor" data-minor={version.quote.totalMinor}>{formatMinor(version.quote.totalMinor, version.quote.currency)}</strong></div></>}
        {heading === "Payment schedule" && <PaymentSchedule quote={version.quote} showHeading={false} />}
      </section>;
    })}
  </article>;
}
