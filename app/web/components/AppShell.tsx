import Link from "next/link";
import type {ReactNode} from "react";

const nav = [
  {href: "/opportunities", label: "Opportunities"},
  {href: "/content", label: "Content library"},
  {href: "/analytics", label: "Analytics"},
];

export function AppShell({children}: {children: ReactNode}) {
  return <div className="app-frame">
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="Proposal studio home">
        <span className="brand-mark" aria-hidden="true">A</span>
        <span><strong>Arc / Studio</strong><small>Proposal operations</small></span>
      </Link>
      <nav className="primary-nav" aria-label="Workspace navigation">
        {nav.map((item) => <Link key={item.href} href={item.href}>{item.label}</Link>)}
      </nav>
      <div className="sidebar-footer"><span className="live-dot" aria-hidden="true" />Fixture workspace online</div>
    </aside>
    <div className="main-column">
      <header className="topbar"><span>Proposal / RFP / Quote</span><span className="actor-chip">Demo workspace · Manav</span></header>
      <main className="page-content">{children}</main>
    </div>
  </div>;
}
