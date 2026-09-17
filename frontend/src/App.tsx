import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { planTrip, type TripPlanResponse } from './api'
import { TripForm, type TripFormValues } from './components/TripForm'
import { RouteMap } from './components/RouteMap'
import { ComplianceCard, ItineraryList } from './components/Itinerary'
import { DailyLogSheets } from './components/DailyLogSheets'
import './App.css'

function App() {
  const [plan, setPlan] = useState<TripPlanResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: planTrip,
    onSuccess: (data) => {
      setPlan(data)
      setError(null)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  function handleSubmit(values: TripFormValues) {
    setError(null)
    mutation.mutate({
      currentLocation: values.currentLocation,
      pickupLocation: values.pickupLocation,
      dropoffLocation: values.dropoffLocation,
      currentCycleUsedHours: values.currentCycleUsedHours,
      shiftStart: new Date(values.shiftStart).toISOString(),
    })
  }

  return (
    <div className="app">
      <header className="site-header no-print">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <div>
            <p className="eyebrow">Spotter assessment</p>
            <h1>HOS Trip Planner</h1>
          </div>
        </div>
        <p className="tagline">
          Route a property-carrying trip, insert required breaks and fuel stops, and
          generate FMCSA-style daily logs for the 70-hour / 8-day cycle.
        </p>
      </header>

      <main>
        <section className="panel input-panel no-print">
          <h2>Trip details</h2>
          <TripForm onSubmit={handleSubmit} isLoading={mutation.isPending} />
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
        </section>

        {mutation.isPending && (
          <p className="loading no-print" aria-live="polite">
            Calculating route and HOS schedule…
          </p>
        )}

        {plan && !mutation.isPending && (
          <>
            <div className="results-grid no-print">
              <ComplianceCard plan={plan} />
              <RouteMap plan={plan} />
              <ItineraryList plan={plan} />
            </div>
            <DailyLogSheets logs={plan.logs} />
          </>
        )}
      </main>

      <footer className="site-footer no-print">
        <p>
          Modeled rules: 11-hr drive · 14-hr window · 30-min break after 8 hrs driving ·
          10-hr reset · fuel every 1,000 mi · 1-hr pickup/dropoff. Not a legal ELD.
        </p>
      </footer>
    </div>
  )
}

export default App
