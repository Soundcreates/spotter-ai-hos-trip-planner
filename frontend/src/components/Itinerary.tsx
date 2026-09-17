import type { TripPlanResponse } from '../api'

const EVENT_LABELS: Record<string, string> = {
  drive: 'Driving',
  pickup: 'Pickup',
  dropoff: 'Dropoff',
  break_30m: '30-min break',
  rest_10h: '10-hour reset',
  fuel: 'Fuel stop',
}

interface Props {
  plan: TripPlanResponse
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function ComplianceCard({ plan }: Props) {
  const { compliance, route } = plan
  const final = compliance.finalState

  return (
    <section className="compliance-card">
      <header>
        <h2>Trip summary</h2>
        <p>
          {route.totalDistanceMiles.toFixed(0)} mi ·{' '}
          {compliance.totalScheduledHours.toFixed(1)} hrs scheduled · provider{' '}
          {route.provider}
        </p>
      </header>
      <dl className="stat-grid">
        <div>
          <dt>Cycle remaining</dt>
          <dd>{Number(final.remainingCycleHours).toFixed(1)} h</dd>
        </div>
        <div>
          <dt>Drive remaining</dt>
          <dd>{Number(final.remainingDriveHours).toFixed(1)} h</dd>
        </div>
        <div>
          <dt>Window remaining</dt>
          <dd>{Number(final.remainingWindowHours).toFixed(1)} h</dd>
        </div>
        <div>
          <dt>Started with</dt>
          <dd>{compliance.initialCycleUsedHours.toFixed(1)} h used</dd>
        </div>
      </dl>
      {compliance.warnings?.length > 0 && (
        <ul className="warnings">
          {compliance.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function ItineraryList({ plan }: Props) {
  return (
    <section className="itinerary">
      <h2>Stops &amp; rests</h2>
      <ol>
        {plan.itinerary.map((event, idx) => (
          <li key={`${event.start}-${idx}`} className={`event event-${event.type}`}>
            <div className="event-head">
              <strong>{EVENT_LABELS[event.type] ?? event.type}</strong>
              <span>
                {fmt(event.start)} → {fmt(event.end)}
              </span>
            </div>
            <p>{event.explanation}</p>
            {event.miles > 0 && (
              <small>{event.miles.toFixed(1)} miles</small>
            )}
          </li>
        ))}
      </ol>

      {plan.route.maneuvers?.length > 0 && (
        <details className="maneuvers">
          <summary>Route instructions ({plan.route.maneuvers.length})</summary>
          <ol>
            {plan.route.maneuvers.map((m, i) => (
              <li key={i}>
                {m.instruction}{' '}
                <span className="muted">
                  ({m.distanceMiles} mi / {m.durationMinutes} min)
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
