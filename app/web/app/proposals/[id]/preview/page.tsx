"use client";

import Link from "next/link";
import {use, useEffect, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {Button} from "@/components/Button";
import {FlagList} from "@/components/FlagList";
import {ProposalDocument, type ProposalDocumentVersion} from "@/components/ProposalDocument";
import {StatusPill} from "@/components/StatusPill";
import {api, ApiError, type ValidationFlag} from "@/lib/api";
import {versionIdForRoute} from "@/lib/demoData";

type PageProps = {params: Promise<{id: string}>};

type StoredQuoteLine = {
  id: string;
  label: string;
  ruleId: string;
  quantity: number;
  unitPriceMinor: number;
  subtotalMinor: number;
  optional: boolean;
  selected: boolean;
  sourceRecordIds: string[];
};

type StoredPaymentInstallment = {
  sequence: number;
  label: string;
  amountMinor: number;
  dueDescription: string;
};

type StoredQuote = {
  currency: string;
  lines: StoredQuoteLine[];
  subtotalMinor: number;
  discountMinor: number;
  taxMinor: number;
  totalMinor: number;
  paymentSchedule: StoredPaymentInstallment[];
  pricingRuleVersion: string;
  inputHash: string;
  calculatedAt: string;
};

type StoredSection = {
  key: string;
  blocks: {blockId: string; content: string}[];
};

type StoredVersionResponse = {
  title: string;
  versionNumber: number;
  status: string;
  scope: ProposalDocumentVersion["scope"];
  quote: StoredQuote;
  sections: StoredSection[];
  document?: {id: string; status: string} | null;
};

type RenderResponse = {
  status: string;
  document?: {id: string; status: string} | null;
  flags?: ValidationFlag[];
};

function toPreviewVersion(response: StoredVersionResponse): ProposalDocumentVersion {
  return {
    title: response.title,
    versionNumber: response.versionNumber,
    scope: {
      deliverables: response.scope?.deliverables ?? [],
      milestones: response.scope?.milestones ?? [],
      assumptions: response.scope?.assumptions ?? [],
      exclusions: response.scope?.exclusions ?? [],
    },
    sections: response.sections ?? [],
    quote: {
      ...response.quote,
      status: "calculated",
      lines: response.quote.lines.map((line: StoredQuoteLine) => ({
        ...line, ruleVersion: response.quote.pricingRuleVersion,
      })),
      paymentSchedule: response.quote.paymentSchedule.map((item: StoredPaymentInstallment) => ({
        ...item, id: `installment-${item.sequence}`,
      })),
    },
  };
}

export default function PreviewPage({params}: PageProps) {
  const {id} = use(params);
  const [version, setVersion] = useState<ProposalDocumentVersion | null>(null);
  const [status, setStatus] = useState("loading");
  const [loading, setLoading] = useState(true);
  const [flags, setFlags] = useState<ValidationFlag[]>([]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setVersion(null);
    setFlags([]);
    api.get<StoredVersionResponse>(`/v1/proposal-versions/${versionIdForRoute(id)}`).then((response) => {
      if (!active) return;
      setVersion(toPreviewVersion(response));
      setStatus(response.document?.status ?? response.status ?? "ready");
    }).catch((error) => {
      if (!active) return;
      setStatus("error");
      setFlags(error instanceof ApiError && error.flags.length ? error.flags : [{code: "API_UNAVAILABLE", severity: "blocking", message: "The fixture API could not load this proposal."}]);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  const downloadPdf = async () => {
    if (!version) return;
    try {
      setFlags([]);
      setStatus("rendering");
      const latest = await api.get<StoredVersionResponse>(`/v1/proposal-versions/${versionIdForRoute(id)}`);
      setVersion(toPreviewVersion(latest));
      let documentId: string | null = latest.document?.status === "ready" ? latest.document.id : null;
      if (!documentId) {
        const response = await api.post<RenderResponse>(`/v1/proposal-versions/${versionIdForRoute(id)}/render`, {});
        if (response.status === "failed" || response.document?.status !== "ready") {
          setStatus("error");
          setFlags(response.flags?.length ? response.flags : [{code: "RENDER_ERROR", severity: "blocking", message: "The fixture API could not render this proposal."}]);
          return;
        }
        documentId = response.document?.id ?? null;
        if (!documentId) {
          setStatus("error");
          setFlags([{code: "RENDER_ERROR", severity: "blocking", message: "The fixture API returned no rendered document."}]);
          return;
        }
      }
      const response = await fetch(api.url(`/v1/documents/${documentId}/download`));
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new ApiError(response.status, body);
      }
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (new TextDecoder().decode(bytes.slice(0, 4)) !== "%PDF") throw new Error("download did not return a PDF");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([bytes], {type: "application/pdf"}));
      link.download = `${id}-proposal.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      setStatus("downloaded");
    } catch (error) {
      setStatus("error");
      setFlags(error instanceof ApiError && error.flags.length ? error.flags : [{code: "API_UNAVAILABLE", severity: "blocking", message: "The fixture API could not download this proposal."}]);
    }
  };

  return <AppShell><div className="workspace-page"><div className="page-heading"><div><p className="eyebrow">Client proposal / {id}</p><h1>Proposal preview</h1><p className="lede">The client-facing document follows the same ordered story as the generated PDF.</p></div><div className="preview-actions"><StatusPill status={status} /><Button disabled={loading || !version} onClick={() => void downloadPdf()}>Download PDF</Button></div></div><FlagList flags={flags} /><div className="workspace-nav"><Link href={`/proposals/${id}`}>Draft</Link><Link href={`/proposals/${id}/quote`}>Quote</Link><Link href={`/proposals/${id}/approval`}>Approval</Link><Link href={`/proposals/${id}/preview`}>Preview</Link></div>{loading && <p role="status">Loading proposal preview.</p>}{version && <ProposalDocument version={version} />}</div></AppShell>;
}
