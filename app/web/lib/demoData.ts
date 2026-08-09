export type DemoEvidence = {sourceRecordId: string; locator: string; excerpt: string};
export type DemoClaim = {id: string; text: string; status: string; evidence: DemoEvidence[]};
export type DemoBlock = {blockId: string; content: string; claimIds: string[]; sourceRecordIds: string[]};
export type DemoSection = {key: string; blocks: DemoBlock[]};

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
