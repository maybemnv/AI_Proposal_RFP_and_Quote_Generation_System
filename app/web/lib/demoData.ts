export type DemoEvidence = {sourceRecordId: string; locator: string; excerpt: string};
export type DemoClaim = {id: string; text: string; status: string; evidence: DemoEvidence[]};
export type DemoBlock = {blockId: string; content: string; claimIds: string[]; sourceRecordIds: string[]};
export type DemoSection = {key: string; blocks: DemoBlock[]};
export type DemoQuoteLine = {
  id: string;
  label: string;
  ruleId: string;
  ruleVersion: string;
  quantity: number;
  unit: string;
  unitPriceMinor: number;
  subtotalMinor: number;
  optional: boolean;
  selected: boolean;
};
export type DemoQuote = {
  currency: string;
  lines: DemoQuoteLine[];
  subtotalMinor: number;
  discountMinor: number;
  taxMinor: number;
  totalMinor: number;
  paymentSchedule: {id: string; label: string; percent: number; amountMinor: number}[];
  status: "calculated" | "review_required";
  policyMessage?: string;
};
export type DemoApproval = {
  id: string;
  kind: "claim" | "scope" | "quote" | "proposal";
  requiredRole: "content_editor" | "quote_approver" | "proposal_approver";
  decision: "pending" | "approved" | "rejected";
  reviewer?: string;
  comment?: string;
};

export const demoClaims: Record<string, DemoClaim> = {
  "claim-onboarding-40": {
    id: "claim-onboarding-40", text: "Cut onboarding time by 40% for a comparable mid-size retailer", status: "approved",
    evidence: [{sourceRecordId: "src-agency-case", locator: "case-study.pdf#page=2", excerpt: "The comparable retailer reduced onboarding time by 40%."}],
  },
  "claim-time-to-value": {
    id: "claim-time-to-value", text: "Reduced time to first value from six weeks to three weeks", status: "approved",
    evidence: [{sourceRecordId: "src-agency-case", locator: "case-study.pdf#page=3", excerpt: "Time to first value moved from six weeks to three weeks."}],
  },
  "claim-csat-uplift": {
    id: "claim-csat-uplift", text: "Post-onboarding CSAT rose from 3.8 to 4.5", status: "approved",
    evidence: [{sourceRecordId: "src-agency-case", locator: "case-study.pdf#page=4", excerpt: "Post-onboarding CSAT increased from 3.8 to 4.5."}],
  },
};

export const demoSections: DemoSection[] = [
  {key: "scope", blocks: [
    {blockId: "scope-1", content: "The engagement covers four facilitated discovery workshops, a written findings pack, and a handover session with the onboarding team.", claimIds: [], sourceRecordIds: ["src-agency-discovery"]},
    {blockId: "scope-2", content: "Four facilitated discovery workshops, a findings pack, sequenced process changes, and two review cycles.", claimIds: [], sourceRecordIds: ["src-agency-discovery"]},
  ]},
  {key: "case_studies", blocks: [
    {blockId: "case_studies-1", content: "The closest comparison is a mid-size retail client with the same onboarding challenge.", claimIds: [], sourceRecordIds: ["src-agency-case"]},
    {blockId: "case_studies-2", content: "The programme reduced onboarding time by 40% from its starting point.", claimIds: ["claim-onboarding-40"], sourceRecordIds: ["src-agency-case"]},
    {blockId: "case_studies-3", content: "Post-onboarding CSAT increased from 3.8 to 4.5.", claimIds: ["claim-csat-uplift"], sourceRecordIds: ["src-agency-case"]},
  ]},
];

export const demoScope = {
  deliverables: [
    {id: "del_proposition", name: "Brand proposition and messaging system", description: "Signed-off proposition, audience framing, and messaging hierarchy.", quantity: 1, unit: "pack", optional: false},
    {id: "del_journeys", name: "Priority journey design", description: "Responsive design for priority customer journeys.", quantity: 1, unit: "set", optional: false},
    {id: "del_component_system", name: "Accessible component system", description: "Documented component library for the delivery team.", quantity: 1, unit: "system", optional: false},
    {id: "del_content_migration", name: "Legacy content migration", description: "Migration of the agreed initial content set.", quantity: 1, unit: "workstream", optional: true},
    {id: "del_training", name: "Marketing team training", description: "Publishing and governance walkthrough.", quantity: 1, unit: "session", optional: true},
  ],
  milestones: [
    {id: "mile_alignment", name: "Alignment complete", sequence: 1, targetDescription: "Goals and constraints accepted."},
    {id: "mile_design", name: "Design system accepted", sequence: 2, targetDescription: "Journeys and component patterns accepted."},
    {id: "mile_build", name: "Priority build ready", sequence: 3, targetDescription: "Priority journeys ready for launch review."},
    {id: "mile_launch", name: "Launch readiness", sequence: 4, targetDescription: "Runbook and handover accepted."},
  ],
  assumptions: ["Northwind provides two subject-matter experts for each workshop.", "Northwind supplies approved product copy before build.", "The steering group returns decisions within five working days."],
  exclusions: ["Paid media and ongoing campaign operations", "Replatforming unrelated back-office tools"],
  openQuestions: ["req_legacy_cms"],
};

const quoteCatalog = [
  {id: "line-strategy", label: "Strategy days", ruleId: "rule_strategy_day", ruleVersion: "2026.1", quantity: 4, unit: "day", unitPriceMinor: 120000, optional: false},
  {id: "line-optional-training", label: "Training session", ruleId: "rule_training", ruleVersion: "2026.1", quantity: 1, unit: "session", unitPriceMinor: 150000, optional: true},
];

export function calculateDemoQuote(
  selectedOptionalIds: string[] = [], discountMinor = 0, taxMinor = 0,
): DemoQuote {
  const lines = quoteCatalog.map((line) => ({
    ...line,
    selected: !line.optional || selectedOptionalIds.includes(line.id),
    subtotalMinor: line.quantity * line.unitPriceMinor,
  }));
  const subtotalMinor = lines.filter((line) => line.selected)
    .reduce((sum, line) => sum + line.subtotalMinor, 0);
  const totalMinor = subtotalMinor - discountMinor + taxMinor;
  const reviewReasons = [
    discountMinor > subtotalMinor * 0.1 ? "exceeds 10%" : "",
    discountMinor > 250000 ? "exceeds the 2,500.00 USD limit" : "",
  ].filter(Boolean);
  const status = reviewReasons.length ? "review_required" : "calculated";
  return {
    currency: "USD", lines, subtotalMinor, discountMinor, taxMinor, totalMinor,
    paymentSchedule: [
      {id: "deposit", label: "Kickoff deposit", percent: 50, amountMinor: Math.floor(totalMinor * 0.5)},
      {id: "midpoint", label: "Midpoint acceptance", percent: 30, amountMinor: Math.floor(totalMinor * 0.3)},
      {id: "handover", label: "Handover", percent: 20, amountMinor: totalMinor - Math.floor(totalMinor * 0.5) - Math.floor(totalMinor * 0.3)},
    ],
    status,
    ...(reviewReasons.length ? {policyMessage: `Discount ${discountMinor / 100}.00 USD ${reviewReasons.join(" and ")}.`} : {}),
  };
}

export const demoQuote = calculateDemoQuote();

export const previewSectionOrder = [
  "Executive summary", "Understanding", "Scope", "Milestones", "Assumptions",
  "Options", "Pricing", "Payment schedule", "Case studies", "Next steps",
] as const;

export const contentClaims = [
  {id: "claim-pending-csat", text: "A governed content system improves review consistency", status: "pending_approval", validFrom: "2026-07-01", validUntil: "2026-11-30", allowed: "Governance proposals", prohibited: "Quantified performance promises", evidenceCount: 2, sources: ["research-notes.md#L44"]},
  {id: "claim-onboarding-40", text: "Cut onboarding time by 40% for a comparable mid-size retailer", status: "approved", validFrom: "2026-01-01", validUntil: "2026-12-31", allowed: "Retail onboarding proposals", prohibited: "Unrelated sectors", evidenceCount: 1, sources: ["case-study.pdf#page=2"]},
  {id: "claim-expired-retention", text: "The previous programme retained 92% of users", status: "expired", validFrom: "2025-01-01", validUntil: "2026-07-15", allowed: "Historical analysis", prohibited: "New version client claims", evidenceCount: 1, sources: ["legacy-case-study.pdf#page=6"]},
];

export type AnalyticsKpi = {key: string; label: string; value?: number; valueMinor?: number; unit: string};
export type AnalyticsEvent = {id: string; type: string; actor: string; at: string; proposalId: string; documentId?: string};
export type AnalyticsData = {kpis: AnalyticsKpi[]; events: AnalyticsEvent[]; viewsByDay: {day: string; count: number}[]};

export const demoAnalytics: AnalyticsData = {
  kpis: [
    {key: "proposals_sent", label: "Proposals sent", value: 18, unit: "proposals"},
    {key: "win_rate", label: "Win rate", value: 42, unit: "%"},
    {key: "median_cycle_days", label: "Median cycle", value: 9.5, unit: "days"},
    {key: "pipeline_value", label: "Pipeline value", valueMinor: 8640000, unit: "USD"},
  ],
  events: [
    {id: "event-sent", type: "sent", actor: "PandaDoc", at: "2026-08-01T09:00:00Z", proposalId: "proposal_northwind", documentId: "doc-northwind"},
    {id: "event-viewed", type: "viewed", actor: "PandaDoc", at: "2026-08-02T12:00:00Z", proposalId: "proposal_northwind", documentId: "doc-northwind"},
    {id: "event-signed", type: "signed", actor: "PandaDoc", at: "2026-08-03T15:00:00Z", proposalId: "proposal_northwind", documentId: "doc-northwind"},
    {id: "event-declined", type: "declined", actor: "PandaDoc", at: "2026-08-04T10:00:00Z", proposalId: "proposal_rfp_response", documentId: "doc-rfp"},
    {id: "event-expired", type: "expired", actor: "PandaDoc", at: "2026-08-05T08:00:00Z", proposalId: "proposal_rfp_response", documentId: "doc-rfp"},
  ],
  viewsByDay: [
    {day: "2026-08-01", count: 2}, {day: "2026-08-02", count: 4}, {day: "2026-08-03", count: 6},
    {day: "2026-08-04", count: 3}, {day: "2026-08-05", count: 8}, {day: "2026-08-06", count: 5},
    {day: "2026-08-07", count: 7},
  ],
};

export const demoApprovals: DemoApproval[] = [
  {id: "approval-claim", kind: "claim", requiredRole: "content_editor", decision: "approved", reviewer: "Maya Chen", comment: "Evidence links checked."},
  {id: "approval-scope", kind: "scope", requiredRole: "content_editor", decision: "approved", reviewer: "Maya Chen", comment: "Scope is inside the brief."},
  {id: "approval-quote", kind: "quote", requiredRole: "quote_approver", decision: "pending"},
  {id: "approval-proposal", kind: "proposal", requiredRole: "proposal_approver", decision: "pending"},
];

export const demoVersion = {
  id: "version_northwind", proposalId: "proposal_northwind", versionNumber: 1,
  status: "working", title: "Brand refresh and site rebuild", currency: "USD",
  sections: demoSections, scope: demoScope,
  quote: {currency: "USD", lines: [], subtotalMinor: 0, discountMinor: 0, taxMinor: 0, totalMinor: 0, paymentSchedule: []},
  approvals: [], unresolvedFlags: [],
};

export function versionIdForRoute(routeId: string): string {
  if (routeId === "prop_northwind") return "version_northwind";
  if (routeId === "prop_rfp_response") return "version_rfp_response";
  return routeId;
}
