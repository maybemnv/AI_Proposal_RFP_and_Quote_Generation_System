import type {DemoApproval} from "@/lib/demoData";
import {Button} from "@/components/Button";

const roleLabels: Record<DemoApproval["requiredRole"], string> = {
  content_editor: "Content editor", quote_approver: "Quote approver", proposal_approver: "Proposal approver",
};

type ApprovalCardProps = {approval: DemoApproval; currentRole: string; locked: boolean; onApprove: (approval: DemoApproval) => void};

export function ApprovalCard({approval, currentRole, locked, onApprove}: ApprovalCardProps) {
  const canDecide = !locked && approval.decision === "pending" && currentRole === approval.requiredRole;
  return <article className="approval-card" data-testid={`approval-${approval.kind}`}><div className="approval-card-heading"><div><p className="eyebrow">{approval.kind} approval</p><h2>{roleLabels[approval.requiredRole]}</h2></div><span className={`approval-decision approval-${approval.decision}`}>{locked && approval.decision === "pending" ? "Locked" : approval.decision}</span></div>
    <dl className="approval-details"><div><dt>Required role</dt><dd>{roleLabels[approval.requiredRole]}</dd></div><div><dt>Reviewer</dt><dd>{approval.reviewer ?? "Not yet assigned"}</dd></div><div><dt>Comment</dt><dd>{approval.comment ?? "Awaiting a decision."}</dd></div></dl>
    {!locked && approval.decision === "pending" && !canDecide && <p className="role-warning">Requires {roleLabels[approval.requiredRole].toLowerCase()}</p>}
    {!locked && approval.decision === "pending" && <Button disabled={!canDecide} onClick={() => onApprove(approval)}>Approve</Button>}
  </article>;
}
