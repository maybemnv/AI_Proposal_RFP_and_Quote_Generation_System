import Link from "next/link";

import {AppShell} from "@/components/AppShell";
import {StatTile} from "@/components/StatTile";
import {formatMinor} from "@/lib/format";

export default function HomePage() {
  return <AppShell>
    <section className="hero-block">
      <div><p className="eyebrow">Operations overview / 09 Aug 2026</p>
        <h1>Move from raw discovery to a proposal people can trust.</h1>
        <p className="lede">One workspace for grounded scope, deterministic pricing, review gates, and client-ready delivery.</p>
      </div>
      <Link className="button button-primary" href="/opportunities">Open workspace <span aria-hidden="true">↗</span></Link>
    </section>
    <section className="stat-grid" aria-label="Workspace snapshot">
      <StatTile label="Open opportunities" value="02" delta="One needs attention" />
      <StatTile label="Drafts in progress" value="01" delta="Trace A / v1" />
      <StatTile label="Pipeline value" value={formatMinor(1250000)} delta="From current quotes" />
      <StatTile label="Evidence coverage" value="100%" delta="Approved claims only" />
    </section>
    <section className="home-grid">
      <article className="panel panel-feature"><div className="panel-heading"><div><p className="eyebrow">Trace A / Northwind Retail Group</p><h2>Brand refresh and site rebuild</h2></div><span className="status-dot">Working</span></div>
        <p className="panel-copy">Six requirements extracted from the agency discovery call. One CMS question is ready for resolution before the proposal moves to review.</p>
        <div className="mini-meta"><span>6 requirements</span><span>5 deliverables</span><span>3 claims backed</span></div>
        <Link className="text-link" href="/proposals/prop_northwind">Continue proposal <span aria-hidden="true">→</span></Link>
      </article>
      <article className="panel"><p className="eyebrow">Format contract</p><h2>Money stays server-owned.</h2><p className="panel-copy">The UI mirrors the API’s integer minor units and never performs quote arithmetic.</p><span className="format-probe" data-testid="format-probe">{formatMinor(125000)}</span></article>
    </section>
  </AppShell>;
}
