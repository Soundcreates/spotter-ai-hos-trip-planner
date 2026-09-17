import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { useEffect } from 'react'
import type { TripPlanResponse } from '../api'
import 'leaflet/dist/leaflet.css'

// Fix default marker icons under Vite
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length >= 2) {
      map.fitBounds(positions, { padding: [40, 40] })
    } else if (positions.length === 1) {
      map.setView(positions[0], 8)
    }
  }, [map, positions])
  return null
}

const roleColor: Record<string, string> = {
  current: '#1f6feb',
  pickup: '#1a7f37',
  dropoff: '#cf222e',
}

function pinIcon(role: string) {
  const color = roleColor[role] ?? '#57606a'
  return L.divIcon({
    className: '',
    html: `<span style="
      display:block;width:14px;height:14px;border-radius:50%;
      background:${color};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)
    "></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

interface Props {
  plan: TripPlanResponse
}

export function RouteMap({ plan }: Props) {
  const coords = (plan.route.geometry?.coordinates ?? []) as number[][]
  const latLngs: [number, number][] = coords.map((c) => [c[1], c[0]])
  const waypoints = plan.route.waypoints ?? []

  const center: [number, number] =
    latLngs[0] ??
    (waypoints[0] ? [waypoints[0].lat, waypoints[0].lon] : [39.5, -98.35])

  return (
    <div className="map-shell">
      <MapContainer
        center={center}
        zoom={5}
        scrollWheelZoom
        className="route-map"
        aria-label="Trip route map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {latLngs.length > 1 && (
          <Polyline positions={latLngs} pathOptions={{ color: '#0b3d2e', weight: 4 }} />
        )}
        <FitBounds positions={latLngs.length ? latLngs : waypoints.map((w) => [w.lat, w.lon])} />
        {waypoints.map((w) => (
          <Marker key={w.role} position={[w.lat, w.lon]} icon={pinIcon(w.role)}>
            <Popup>
              <strong>{w.role}</strong>
              <br />
              {w.label}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <ul className="map-legend" aria-label="Map legend">
        <li><span className="dot current" /> Current</li>
        <li><span className="dot pickup" /> Pickup</li>
        <li><span className="dot dropoff" /> Dropoff</li>
      </ul>
    </div>
  )
}
