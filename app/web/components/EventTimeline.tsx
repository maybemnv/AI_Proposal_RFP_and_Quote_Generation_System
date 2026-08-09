import type {AnalyticsEvent} from "@/lib/demoData";

const eventIcons: Record<string, string> = {sent: "→", viewed: "◉", signed: "✓", declined: "×", expired: "!"};

export function EventTimeline({events}: {events: AnalyticsEvent[]}) {
  return <section className="panel event-timeline"><div className="panel-heading"><div><p className="eyebrow">Provider activity</p><h2>Sent → viewed → signed</h2></div><span className="muted-label">Latest first</span></div><div className="timeline-list">{events.slice().reverse().map((event) => <article className={`timeline-event timeline-${event.type}`} data-testid="timeline-event" key={event.id}><span className="event-icon" data-testid="event-icon" aria-hidden="true">{eventIcons[event.type] ?? "•"}</span><div><strong className="event-label" data-testid="event-label">{event.type}</strong><p>{event.actor} · {new Date(event.at).toLocaleString("en-US", {month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC"})}</p></div><small>{event.proposalId}</small></article>)}</div></section>;
}
