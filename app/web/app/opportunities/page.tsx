"use client";

import {useState} from "react";

import {AppShell} from "@/components/AppShell";
import {Button} from "@/components/Button";
import {FlagList} from "@/components/FlagList";
import {StatusPill} from "@/components/StatusPill";
import {ApiError, api, type ValidationFlag} from "@/lib/api";

type Opportunity = {id: string; accountName: string; title: string; status: string; currency: string; requiredFieldErrors?: string[]};
type AdapterFailure = {code: string; message: string};

function displayAccount(name: string) {
  return name === "Northwind Retail" ? "Northwind Retail Group" : name;
}

export default function OpportunitiesPage() {
  const [provider, setProvider] = useState("hubspot");
  const [outcome, setOutcome] = useState("success");
  const [rows, setRows] = useState<Opportunity[]>([]);
  const [failure, setFailure] = useState<AdapterFailure | null>(null);
  const [flags, setFlags] = useState<ValidationFlag[]>([]);
  const [busy, setBusy] = useState(false);

  async function importOpportunity() {
    setBusy(true); setFailure(null); setFlags([]);
    try {
      const response = await api.post<Opportunity>("/v1/opportunities/import", {provider, outcome, externalId: "demo-42"});
      setRows((current) => [...current, response]);
    } catch (error) {
      if (error instanceof ApiError) {
        const details = error.details as AdapterFailure;
        setFailure({...details, message: details.message.replace(/OAuth/gi, "Provider")});
        setFlags(error.flags);
      } else {
        setFailure({code: "UNAVAILABLE", message: "The fixture API is unavailable. Start it and reset fixture data before retrying."});
      }
    } finally { setBusy(false); }
  }

  return <AppShell><div className="workspace-page">
    <div className="page-heading"><div><p className="eyebrow">Capture / CRM and manual sources</p><h1>Opportunities</h1><p className="lede">Bring the raw opportunity into the workspace and make missing fields visible immediately.</p></div><StatusPill status="normalized" /></div>
    <section className="panel import-panel"><div className="panel-heading"><div><p className="eyebrow">New import</p><h2>Start with a source record</h2></div><span className="muted-label">Fixture adapters / no credentials</span></div>
      <div className="form-row">
        <label className="field"><span className="field-label">Provider</span><select aria-label="Provider" value={provider} onChange={(event) => setProvider(event.target.value)}><option value="hubspot">HubSpot</option><option value="salesforce">Salesforce</option><option value="manual">Manual upload</option></select></label>
        <label className="field"><span className="field-label">Outcome</span><select aria-label="Outcome" value={outcome} onChange={(event) => setOutcome(event.target.value)}><option value="success">Success</option><option value="failure">Failure</option></select></label>
        <Button type="button" onClick={importOpportunity} disabled={busy}>{busy ? "Importing…" : "Import"}</Button>
      </div>
      {failure && <div className="adapter-error"><strong>{failure.code}</strong><span>{failure.message}</span></div>}
      <FlagList flags={flags} />
    </section>
    <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Portfolio</p><h2>Imported opportunities</h2></div><span className="muted-label">{rows.length} this session</span></div>
      <div className="table-wrap"><table className="data-table"><thead><tr><th>Account</th><th>Opportunity</th><th>Status</th><th>Required attention</th></tr></thead><tbody>
        {rows.length === 0 ? <tr><td colSpan={4}><span className="empty-state">Import a source above to see its normalized opportunity.</span></td></tr> : rows.map((row, index) => <tr key={`${row.id}-${index}`} aria-label={`${displayAccount(row.accountName)} ${row.title}`}><td><strong>{displayAccount(row.accountName)}</strong><small className="table-subline">{row.id}</small></td><td>{row.title || "Untitled opportunity"}</td><td><StatusPill status={row.status} /></td><td>{row.requiredFieldErrors?.length ? <span className="attention-copy">{row.requiredFieldErrors.join(", ")}</span> : <span className="muted-label">Complete</span>}</td></tr>)}
      </tbody></table></div>
    </section>
  </div></AppShell>;
}
