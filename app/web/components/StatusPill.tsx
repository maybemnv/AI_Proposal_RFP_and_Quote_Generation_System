const statusIcons: Record<string, string> = {
  normalized: "✓",
  needs_attention: "!",
  working: "•",
  submitted: "↗",
  locked: "⌁",
  rendered: "▣",
  delivered: "✓",
  pending: "○",
  approved: "✓",
  review_required: "!",
};

export function StatusPill({status}: {status: string}) {
  const tone = status.includes("attention") || status.includes("required") ? "warning" : status;
  return <span className={`status-pill status-${tone}`}>
    <span aria-hidden="true">{statusIcons[status] ?? "•"}</span>{status.replaceAll("_", " ")}
  </span>;
}
