"use client";

import Link from "next/link";
import {use, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {Button} from "@/components/Button";
import {FlagList} from "@/components/FlagList";
import {ProposalDocument} from "@/components/ProposalDocument";
import {StatusPill} from "@/components/StatusPill";
import {api, ApiError, type ValidationFlag} from "@/lib/api";
import {demoQuote, versionIdForRoute} from "@/lib/demoData";

type PageProps = {params: Promise<{id: string}>};

export default function PreviewPage({params}: PageProps) {
  const {id} = use(params);
  const [quote, setQuote] = useState(demoQuote);
  const [status, setStatus] = useState("ready");
  const [flags, setFlags] = useState<ValidationFlag[]>([]);

  const downloadPdf = async () => {
    try {
      const version = await api.get<any>(`/v1/proposal-versions/${versionIdForRoute(id)}`);
      let documentId = version.document?.status === "ready" ? version.document.id : null;
      if (!documentId) {
        const response = await api.post<any>(`/v1/proposal-versions/${versionIdForRoute(id)}/render`, {});
        if (response.status === "failed" || response.document?.status !== "ready") {
          setFlags(response.flags?.length ? response.flags : [{code: "RENDER_ERROR", severity: "blocking", message: "The fixture API could not render this proposal."}]);
          return;
        }
        documentId = response.document.id;
      }
      const link = document.createElement("a");
      link.href = api.url(`/v1/documents/${documentId}/download`);
      link.download = `${id}-proposal.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setStatus("downloaded");
    } catch (error) {
      setFlags(error instanceof ApiError && error.flags.length ? error.flags : [{code: "API_UNAVAILABLE", severity: "blocking", message: "The fixture API could not render this proposal."}]);
    }
  };

  return <AppShell><div className="workspace-page"><div className="page-heading"><div><p className="eyebrow">Client proposal / {id}</p><h1>Proposal preview</h1><p className="lede">The client-facing document follows the same ordered story as the generated PDF.</p></div><div className="preview-actions"><StatusPill status={status} /><Button onClick={() => void downloadPdf()}>Download PDF</Button></div></div><FlagList flags={flags} /><div className="workspace-nav"><Link href={`/proposals/${id}`}>Draft</Link><Link href={`/proposals/${id}/quote`}>Quote</Link><Link href={`/proposals/${id}/approval`}>Approval</Link><Link href={`/proposals/${id}/preview`}>Preview</Link></div><ProposalDocument quote={quote} /></div></AppShell>;
}
