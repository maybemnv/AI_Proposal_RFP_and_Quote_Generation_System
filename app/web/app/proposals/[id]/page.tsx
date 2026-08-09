"use client";

import Link from "next/link";
import {use, useEffect, useState} from "react";

import {AppShell} from "@/components/AppShell";
import {EvidencePopover} from "@/components/EvidencePopover";
import {SourceChip} from "@/components/SourceChip";
import {StatusPill} from "@/components/StatusPill";
import {api} from "@/lib/api";
import {demoClaims, demoSections, demoVersion, versionIdForRoute, type DemoClaim, type DemoSection} from "@/lib/demoData";
import {titleCase} from "@/lib/format";

type PageProps = {params: Promise<{id: string}>};

export default function ProposalPage({params}: PageProps) {
  const {id} = use(params);
  const [sections, setSections] = useState<DemoSection[]>(demoSections);
  const [title, setTitle] = useState(demoVersion.title);
  const [status, setStatus] = useState(demoVersion.status);
  const [selectedClaim, setSelectedClaim] = useState<DemoClaim | null>(null);

  useEffect(() => {
    let active = true;
    api.get<any>(`/v1/proposal-versions/${versionIdForRoute(id)}`).then((response) => {
      if (!active) return;
      setTitle(response.title ?? demoVersion.title);
      setStatus(response.status ?? demoVersion.status);
      if (response.sections?.length) setSections(response.sections);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [id]);

  return <AppShell><div className="workspace-page">
    <div className="page-heading"><div><p className="eyebrow">Proposal editor / {id}</p><h1>{title}</h1><p className="lede">Every client-facing assertion stays close to its source evidence.</p></div><StatusPill status={status} /></div>
    <div className="workspace-nav"><Link href={`/proposals/${id}`}>Draft</Link><Link href={`/proposals/${id}/scope`}>Scope</Link><Link href={`/proposals/${id}/quote`}>Quote</Link><Link href={`/proposals/${id}/approval`}>Approval</Link></div>
    <div className="editor-layout"><aside className="panel section-rail"><p className="eyebrow">Sections</p>{sections.map((section) => <a href={`#${section.key}`} key={section.key}>{titleCase(section.key)}</a>)}</aside>
      <section className="panel editor-main"><div className="panel-heading"><div><p className="eyebrow">Generated draft</p><h2>Working copy / version 1</h2></div><span className="muted-label">Editable until locked</span></div>
        <div className="draft-sections">{sections.map((section) => <section id={section.key} className="draft-section" key={section.key}><h2>{titleCase(section.key)}</h2>{section.blocks.map((block) => <article className={block.claimIds?.length ? "draft-block draft-block-claimed" : "draft-block"} key={block.blockId}><p>{block.content}</p>{block.claimIds?.length ? <div className="source-row">{block.claimIds.flatMap((claimId) => demoClaims[claimId]?.evidence.map((evidence) => evidence.sourceRecordId) ?? []).map((sourceId, index) => <SourceChip key={`${sourceId}-${index}`} sourceRecordId={sourceId} onClick={() => { const claimId = block.claimIds?.[0]; if (claimId && demoClaims[claimId]) setSelectedClaim(demoClaims[claimId]); }} />)}</div> : null}</article>)}</section>)}</div>
      </section>
      <aside className="evidence-rail">{selectedClaim ? <EvidencePopover claim={selectedClaim} onClose={() => setSelectedClaim(null)} /> : <div className="panel evidence-empty"><p className="eyebrow">Evidence rail</p><h2>Follow the proof.</h2><p>Choose a source chip on a claim-backed block to inspect its locator and excerpt.</p></div>}</aside>
    </div>
  </div></AppShell>;
}
