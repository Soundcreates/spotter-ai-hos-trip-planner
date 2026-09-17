import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'

const schema = z.object({
  currentLocation: z.string().min(2, 'Enter current location'),
  pickupLocation: z.string().min(2, 'Enter pickup location'),
  dropoffLocation: z.string().min(2, 'Enter dropoff location'),
  currentCycleUsedHours: z
    .number({ error: 'Must be 0–70' })
    .min(0, 'Must be 0–70')
    .max(70, 'Must be 0–70'),
  shiftStart: z.string().min(1, 'Choose a shift start'),
})

export type TripFormValues = z.infer<typeof schema>

const SAMPLE: TripFormValues = {
  currentLocation: 'Chicago, IL',
  pickupLocation: 'Dallas, TX',
  dropoffLocation: 'Atlanta, GA',
  currentCycleUsedHours: 12,
  shiftStart: '2026-03-01T06:00',
}

interface Props {
  onSubmit: (values: TripFormValues) => void
  isLoading: boolean
}

export function TripForm({ onSubmit, isLoading }: Props) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TripFormValues>({
    resolver: zodResolver(schema),
    defaultValues: SAMPLE,
  })

  return (
    <form className="trip-form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <div className="form-grid">
        <label>
          <span>Current location</span>
          <input
            type="text"
            placeholder="e.g. Chicago, IL"
            {...register('currentLocation')}
          />
          {errors.currentLocation && (
            <em className="field-error">{errors.currentLocation.message}</em>
          )}
        </label>

        <label>
          <span>Pickup location</span>
          <input
            type="text"
            placeholder="e.g. Dallas, TX"
            {...register('pickupLocation')}
          />
          {errors.pickupLocation && (
            <em className="field-error">{errors.pickupLocation.message}</em>
          )}
        </label>

        <label>
          <span>Dropoff location</span>
          <input
            type="text"
            placeholder="e.g. Atlanta, GA"
            {...register('dropoffLocation')}
          />
          {errors.dropoffLocation && (
            <em className="field-error">{errors.dropoffLocation.message}</em>
          )}
        </label>

        <label>
          <span>Current cycle used (hrs)</span>
          <input
            type="number"
            step="0.25"
            min={0}
            max={70}
            {...register('currentCycleUsedHours', { valueAsNumber: true })}
          />
          {errors.currentCycleUsedHours && (
            <em className="field-error">{errors.currentCycleUsedHours.message}</em>
          )}
        </label>

        <label>
          <span>Shift start</span>
          <input type="datetime-local" {...register('shiftStart')} />
          {errors.shiftStart && (
            <em className="field-error">{errors.shiftStart.message}</em>
          )}
        </label>
      </div>

      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={isLoading}>
          {isLoading ? 'Planning trip…' : 'Plan trip'}
        </button>
        <button
          type="button"
          className="btn ghost"
          onClick={() => reset(SAMPLE)}
          disabled={isLoading}
        >
          Load sample
        </button>
      </div>
    </form>
  )
}
