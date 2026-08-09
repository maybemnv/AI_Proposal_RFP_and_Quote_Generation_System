"use client";

import Link from "next/link";
import {use, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {Button} from "@/components/Button";
import {ProposalDocument} from "@/components/ProposalDocument";
import {StatusPill} from "@/components/StatusPill";
import {api} from "@/lib/api";
import {demoQuote, versionIdForRoute} from "@/lib/demoData";

type PageProps = {params: Promise<{id: string}>};

export default function PreviewPage({params}: PageProps) {
  const {id} = use(params);
  const [quote, setQuote] = useState(demoQuote);
  const [status, setStatus] = useState("ready");

  const downloadPdf = async () => {
    try {
      const response = await api.post<any>(`/v1/proposal-versions/${versionIdForRoute(id)}/render`, {});
      if (response.document?.storageUri) {
        const link = document.createElement("a");
        link.href = response.document.storageUri;
        link.download = `${id}-proposal.pdf`;
        link.click();
        return;
      }
    } catch {
      // The fixture download below keeps the portfolio screen demoable without the API.
    }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob(["%PDF-1.4\n% Arc proposal fixture\n"], {type: "application/pdf"}));
    link.download = `${id}-proposal.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setStatus("downloaded");
  };

  return <AppShell><div className="workspace-page"><div className="page-heading"><div><p className="eyebrow">Client proposal / {id}</p><h1>Proposal preview</h1><p className="lede">The client-facing document follows the same ordered story as the generated PDF.</p></div><div className="preview-actions"><StatusPill status={status} /><Button onClick={() => void downloadPdf()}>Download PDF</Button></div></div><div className="workspace-nav"><Link href={`/proposals/${id}`}>Draft</Link><Link href={`/proposals/${id}/quote`}>Quote</Link><Link href={`/proposals/${id}/approval`}>Approval</Link><Link href={`/proposals/${id}/preview`}>Preview</Link></div><ProposalDocument quote={quote} /></div></AppShell>;
}
