import { useState } from 'react'
import type { DailyLog, DutyStatus } from '../api'

const STATUS_ROW: Record<DutyStatus, number> = {
  OFF_DUTY: 0,
  SLEEPER_BERTH: 1,
  DRIVING: 2,
  ON_DUTY_NOT_DRIVING: 3,
}

const ROW_LABELS = ['Off Duty', 'Sleeper Berth', 'Driving', 'On Duty (not driving)']

interface Props {
  logs: DailyLog[]
}

export function DailyLogSheets({ logs }: Props) {
  const [active, setActive] = useState(0)
  if (!logs.length) return null

  return (
    <section className="log-section">
      <div className="log-toolbar no-print">
        <h2>Daily log sheets</h2>
        <div className="day-tabs" role="tablist" aria-label="Log days">
          {logs.map((l, i) => (
            <button
              key={l.date}
              type="button"
              role="tab"
              aria-selected={i === active}
              className={i === active ? 'tab active' : 'tab'}
              onClick={() => setActive(i)}
            >
              Day {i + 1} · {l.date}
            </button>
          ))}
        </div>
        <button type="button" className="btn ghost" onClick={() => window.print()}>
          Print / PDF
        </button>
      </div>

      {logs.map((l, i) => (
        <div
          key={l.date}
          className={i === active ? 'log-print-page is-active' : 'log-print-page'}
          data-print-day={i + 1}
        >
          <LogSheet log={l} />
        </div>
      ))}
    </section>
  )
}

function LogSheet({ log }: { log: DailyLog }) {
  const width = 960
  const height = 220
  const left = 130
  const top = 20
  const gridW = width - left - 70
  const rowH = 40
  const minutesInDay = 24 * 60

  const xFor = (minute: number) => left + (minute / minutesInDay) * gridW
  const yFor = (status: DutyStatus) => top + STATUS_ROW[status] * rowH + rowH / 2

  // Build path: horizontal lines per segment + vertical connectors
  const pathParts: string[] = []
  log.segments.forEach((seg, idx) => {
    const y = yFor(seg.status)
    const x1 = xFor(seg.startMinute)
    const x2 = xFor(Math.min(seg.endMinute, minutesInDay))
    pathParts.push(`M ${x1} ${y} L ${x2} ${y}`)
    const next = log.segments[idx + 1]
    if (next) {
      const ny = yFor(next.status)
      pathParts.push(`M ${x2} ${y} L ${x2} ${ny}`)
    }
  })

  return (
    <article className="log-sheet">
      <header className="log-header">
        <div>
          <h3>Drivers Daily Log (24 hours)</h3>
          <p className="log-sub">U.S. Department of Transportation — Record of Duty Status</p>
        </div>
        <div className="log-date">
          <span>
            <strong>Month</strong> {String(log.month).padStart(2, '0')}
          </span>
          <span>
            <strong>Day</strong> {String(log.day).padStart(2, '0')}
          </span>
          <span>
            <strong>Year</strong> {log.year}
          </span>
        </div>
      </header>

      <div className="log-meta">
        <div>
          <label>From</label>
          <p>{log.fromLocation || '—'}</p>
        </div>
        <div>
          <label>To</label>
          <p>{log.toLocation || '—'}</p>
        </div>
        <div>
          <label>Total miles driving</label>
          <p>{log.totalMilesDriving}</p>
        </div>
        <div>
          <label>Carrier</label>
          <p>{log.carrierName}</p>
        </div>
        <div>
          <label>Main office</label>
          <p>{log.mainOfficeAddress}</p>
        </div>
        <div>
          <label>Vehicle / trailer</label>
          <p>{log.vehicleNumbers}</p>
        </div>
        <div>
          <label>Driver</label>
          <p>{log.driverName}</p>
        </div>
        <div>
          <label>Shipping doc</label>
          <p>{log.shippingDoc}</p>
        </div>
      </div>

      <div className="grid-wrap">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="duty-grid"
          role="img"
          aria-label={`Duty status grid for ${log.date}`}
        >
          {/* Row backgrounds */}
          {ROW_LABELS.map((label, i) => (
            <g key={label}>
              <rect
                x={left}
                y={top + i * rowH}
                width={gridW}
                height={rowH}
                fill={i % 2 === 0 ? '#f6f4ef' : '#fff'}
                stroke="#2c2c2c"
                strokeWidth={0.6}
              />
              <text
                x={8}
                y={top + i * rowH + rowH / 2 + 4}
                fontSize={12}
                fontFamily="IBM Plex Sans, sans-serif"
                fill="#1a1a1a"
              >
                {label}
              </text>
            </g>
          ))}

          {/* Hour lines */}
          {Array.from({ length: 25 }, (_, h) => {
            const x = xFor(h * 60)
            return (
              <g key={h}>
                <line
                  x1={x}
                  y1={top}
                  x2={x}
                  y2={top + 4 * rowH}
                  stroke={h === 12 ? '#1a1a1a' : '#9a9590'}
                  strokeWidth={h % 6 === 0 ? 1.2 : 0.5}
                />
                <text
                  x={x}
                  y={top + 4 * rowH + 14}
                  fontSize={10}
                  textAnchor="middle"
                  fill="#444"
                  fontFamily="IBM Plex Sans, sans-serif"
                >
                  {h === 0 ? 'Mid' : h === 12 ? 'Noon' : h}
                </text>
              </g>
            )
          })}

          {/* Duty path */}
          <path
            d={pathParts.join(' ')}
            fill="none"
            stroke="#0b3d2e"
            strokeWidth={2.4}
            strokeLinejoin="miter"
          />

          {/* Totals column */}
          <text x={left + gridW + 12} y={top - 4} fontSize={11} fill="#333">
            Total
          </text>
          {[
            log.totals.offDuty,
            log.totals.sleeperBerth,
            log.totals.driving,
            log.totals.onDutyNotDriving,
          ].map((val, i) => (
            <text
              key={i}
              x={left + gridW + 12}
              y={top + i * rowH + rowH / 2 + 4}
              fontSize={13}
              fontFamily="IBM Plex Mono, monospace"
              fill="#111"
            >
              {val.toFixed(2)}
            </text>
          ))}
        </svg>
      </div>

      <div className="remarks-block">
        <h4>Remarks</h4>
        {log.remarks.length === 0 ? (
          <p className="muted">No status-change remarks.</p>
        ) : (
          <ul>
            {log.remarks.map((r, i) => (
              <li key={i}>
                <strong>{r.time}</strong> — {r.location || '—'} · {r.text}
              </li>
            ))}
          </ul>
        )}
      </div>

      <footer className="log-recap">
        <span>On duty today (lines 3 &amp; 4): {log.recap.onDutyToday.toFixed(2)} hrs</span>
        <span>Grid total: {log.totals.all.toFixed(2)} / 24</span>
      </footer>
    </article>
  )
}
