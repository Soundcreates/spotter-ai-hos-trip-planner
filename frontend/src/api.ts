export type DutyStatus =
  | 'OFF_DUTY'
  | 'SLEEPER_BERTH'
  | 'DRIVING'
  | 'ON_DUTY_NOT_DRIVING'

export interface TripPlanRequest {
  currentLocation: string
  pickupLocation: string
  dropoffLocation: string
  currentCycleUsedHours: number
  shiftStart?: string
}

export interface Waypoint {
  role: string
  label: string
  lat: number
  lon: number
}

export interface ItineraryEvent {
  type: string
  status: DutyStatus
  start: string
  end: string
  durationMinutes: number
  location: string
  miles: number
  explanation: string
  stateBefore: Record<string, number | boolean>
  stateAfter: Record<string, number | boolean>
}

export interface LogSegment {
  status: DutyStatus
  startMinute: number
  endMinute: number
  hours: number
  location: string
  remark: string
}

export interface DailyLog {
  date: string
  month: number
  day: number
  year: number
  carrierName: string
  mainOfficeAddress: string
  driverName: string
  coDriverName: string
  vehicleNumbers: string
  shippingDoc: string
  totalMilesDriving: number
  fromLocation: string
  toLocation: string
  segments: LogSegment[]
  remarks: Array<{ time: string; location: string; text: string; status: string }>
  totals: {
    offDuty: number
    sleeperBerth: number
    driving: number
    onDutyNotDriving: number
    all: number
  }
  recap: { onDutyToday: number }
}

export interface TripPlanResponse {
  tripId: string
  createdAt: string
  inputs: TripPlanRequest & { shiftStart: string }
  route: {
    geometry: { type: string; coordinates: number[][] }
    totalDistanceMiles: number
    totalDurationHours: number
    averageSpeedMph: number
    legs: Array<{
      from: string
      to: string
      distanceMiles: number
      durationHours: number
    }>
    waypoints: Waypoint[]
    maneuvers: Array<{
      instruction: string
      distanceMiles: number
      durationMinutes: number
      type?: string | number
    }>
    provider: string
  }
  itinerary: ItineraryEvent[]
  compliance: {
    calculationVersion: string
    feasible: boolean
    initialCycleUsedHours: number
    finalState: Record<string, number | boolean>
    shiftStart: string
    shiftEnd: string
    totalScheduledHours: number
    warnings: string[]
    assumptions: Record<string, unknown>
  }
  logs: DailyLog[]
}

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export async function planTrip(payload: TripPlanRequest): Promise<TripPlanResponse> {
  const res = await fetch(`${API_BASE}/api/trips/plan/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail =
      typeof body.detail === 'string'
        ? body.detail
        : body.detail
          ? JSON.stringify(body.detail)
          : Object.values(body)
              .flat()
              .join(' ') || `Request failed (${res.status})`
    throw new Error(detail)
  }
  return body as TripPlanResponse
}
