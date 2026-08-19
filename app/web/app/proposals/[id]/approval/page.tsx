"use client";

import Link from "next/link";
import {use, useEffect, useMemo, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {ApprovalCard} from "@/components/ApprovalCard";
import {Button} from "@/components/Button";
import {FlagList} from "@/components/FlagList";
import {StatusPill} from "@/components/StatusPill";
import {api, ApiError, type ValidationFlag} from "@/lib/api";
import {demoApprovals, versionIdForRoute, type DemoApproval} from "@/lib/demoData";

type PageProps = {params: Promise<{id: string}>};
type Role = DemoApproval["requiredRole"];

const flagsFor = (id: string) => id === "prop_blocked" ? [{code: "UNRESOLVED_REQUIREMENT", severity: "blocking" as const, message: "Resolve the legacy CMS requirement before submission."}] : [];

export default function ApprovalPage({params}: PageProps) {
  const {id} = use(params);
  const [approvals, setApprovals] = useState<DemoApproval[]>(id === "prop_ready" ? demoApprovals.map((item) => item.kind === "proposal" ? {...item, decision: "pending"} : {...item, decision: "approved"}) : demoApprovals);
  const [locked, setLocked] = useState(false);
  const [flags, setFlags] = useState<ValidationFlag[]>(flagsFor(id));
  const role = (new URLSearchParams(typeof window === "undefined" ? "" : window.location.search).get("as") ?? "proposal_approver") as Role;
  const versionId = versionIdForRoute(id);

  useEffect(() => {
    api.get<any>(`/v1/proposal-versions/${versionId}`).then((response) => {
      if (response.approvals?.length) setApprovals(response.approvals);
      if (response.status === "locked" || response.status === "rendered" || response.status === "delivered") setLocked(true);
      if (response.unresolvedFlags?.length) setFlags(response.unresolvedFlags.map((code: string) => ({code, severity: "blocking" as const, message: code})));
    }).catch(() => setFlags([{code: "API_UNAVAILABLE", severity: "blocking", message: "Fixture API unavailable; approvals cannot be changed."}]));
  }, [versionId]);

  const pending = useMemo(() => approvals.filter((item) => item.decision === "pending"), [approvals]);
  const approve = async (approval: DemoApproval) => {
    try {
      const response = await api.post<any>(`/v1/approvals/${approval.id}/decide`, {decision: "approved", reviewerRole: role});
      setApprovals(response.version.approvals);
      setLocked(["locked", "rendered", "delivered"].includes(response.version.status));
      setFlags([]);
    } catch (error) {
      setFlags(error instanceof ApiError && error.flags.length ? error.flags : [{code: "API_UNAVAILABLE", severity: "blocking", message: "The fixture API could not record this approval."}]);
    }
  };

  return <AppShell><div className="workspace-page">
    <div className="page-heading"><div><p className="eyebrow">Approval gate / {id}</p><h1>Make the decision visible.</h1><p className="lede">Role-gated approvals are recorded beside the submission action, with no hidden blockers.</p></div><StatusPill status={locked ? "locked" : "submitted"} /></div>
    <div className="workspace-nav"><Link href={`/proposals/${id}`}>Draft</Link><Link href={`/proposals/${id}/scope`}>Scope</Link><Link href={`/proposals/${id}/quote`}>Quote</Link><Link href={`/proposals/${id}/approval`}>Approval</Link></div>
    <div className="approval-layout"><section className="approval-cards"><div className="panel-heading"><div><p className="eyebrow">Required approvals</p><h2>{locked ? "All approvals recorded" : `${pending.length} decision${pending.length === 1 ? "" : "s"} remaining`}</h2></div>{locked && <span className="locked-label">Read-only</span>}</div>{approvals.map((approval) => <ApprovalCard key={approval.id} approval={approval} currentRole={role} locked={locked} onApprove={approve} />)}</section><aside className="panel submit-panel"><p className="eyebrow">Submission</p><h2>{locked ? "Read-only version" : "Ready for the final gate"}</h2><p>{locked ? "All required approvals are recorded. Further changes require a new version." : "Submit is available only when blocking validation flags are closed."}</p>{flags.length > 0 && <div className="approval-flags"><FlagList flags={flags} /></div>}<Button disabled={locked || flags.some((flag) => flag.severity === "blocking") || pending.length > 0} onClick={() => undefined}>Submit for approval</Button></aside></div>
  </div></AppShell>;
}
