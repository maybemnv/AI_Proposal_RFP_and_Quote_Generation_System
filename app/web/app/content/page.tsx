"use client";

import {useState} from "react";

import {AppShell} from "@/components/AppShell";
import {ClaimRow} from "@/components/ClaimRow";
import {contentClaims} from "@/lib/demoData";

export default function ContentPage() {
  const [claims, setClaims] = useState(contentClaims);
  const approve = (id: string) => setClaims((current) => current.map((claim) => claim.id === id ? {...claim, status: "approved"} : claim));
  return <AppShell><div className="workspace-page"><div className="page-heading"><div><p className="eyebrow">Content library</p><h1>Claims that know their expiry.</h1><p className="lede">Every reusable assertion carries its context, evidence, and approval state.</p></div></div><section className="panel"><div className="panel-heading"><div><p className="eyebrow">Claim register</p><h2>Approved, pending, and expired</h2></div><span className="muted-label">{claims.length} tracked claims</span></div><div className="table-wrap content-table-wrap"><table className="data-table"><thead><tr><th>Claim</th><th>Status</th><th>Validity</th><th>Contexts</th><th>Evidence</th><th>Action</th></tr></thead><tbody>{claims.map((claim) => <ClaimRow claim={claim} onApprove={approve} key={claim.id} />)}</tbody></table></div></section></div></AppShell>;
}
