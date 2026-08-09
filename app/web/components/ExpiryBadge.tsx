type ExpiryBadgeProps = {status: string; validUntil: string};

export function ExpiryBadge({status, validUntil}: ExpiryBadgeProps) {
  if (status === "expired") return <span className="expiry-badge expiry-expired">Expired · {validUntil}</span>;
  if (validUntil <= "2026-09-08") return <span className="expiry-badge expiry-soon">Expires soon · {validUntil}</span>;
  return <span className="expiry-badge">Valid · {validUntil}</span>;
}
