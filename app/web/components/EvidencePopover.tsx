import type {DemoClaim} from "@/lib/demoData";

export function EvidencePopover({claim, onClose}: {claim: DemoClaim; onClose: () => void}) {
  const evidence = claim.evidence[0];
  if (!evidence) return null;
  return <aside className="evidence-popover" aria-label="Evidence detail">
    <div className="panel-heading"><div><p className="eyebrow">Evidence / {claim.id}</p><h3>{claim.text}</h3></div><button className="icon-button" type="button" aria-label="Close evidence" onClick={onClose}>×</button></div>
    <p className="evidence-excerpt" data-testid="evidence-excerpt">“{evidence.excerpt}”</p>
    <p className="evidence-locator">{evidence.sourceRecordId} · {evidence.locator}</p>
  </aside>;
}
