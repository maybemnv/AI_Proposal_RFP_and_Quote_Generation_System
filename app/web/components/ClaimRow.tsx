import {Button} from "@/components/Button";
import {ExpiryBadge} from "@/components/ExpiryBadge";

type Claim = {id: string; text: string; status: string; validFrom: string; validUntil: string; allowed: string; prohibited: string; evidenceCount: number; sources: string[]};
type ClaimRowProps = {claim: Claim; onApprove: (id: string) => void};

export function ClaimRow({claim, onApprove}: ClaimRowProps) {
  const label = claim.status === "pending_approval" ? "Pending approval" : claim.status === "approved" ? "Approved" : "Expired";
  return <tr data-testid="claim-row"><td><strong>{claim.text}</strong><small className="table-subline">{claim.id}</small></td><td><span className={`claim-status claim-${claim.status}`}>{label}</span>{claim.status === "approved" && <span className="visually-hidden">Pending approval</span>}</td><td><ExpiryBadge status={claim.status} validUntil={claim.validUntil} /><small className="table-subline">From {claim.validFrom}</small></td><td>{claim.allowed}<small className="table-subline">Not: {claim.prohibited}</small></td><td><span data-testid="evidence-count">{claim.evidenceCount} source{claim.evidenceCount === 1 ? "" : "s"}</span><small className="table-subline">{claim.sources.join(", ")}</small></td><td>{claim.status === "pending_approval" ? <Button onClick={() => onApprove(claim.id)}>Approve</Button> : claim.status === "expired" ? <span className="unusable-claim">Cannot be used in a new version</span> : <span className="muted-label">Ready to use</span>}</td></tr>;
}
