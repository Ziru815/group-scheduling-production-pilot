import { useEffect, useRef, useState } from 'react'
import { useUpdateSession } from '../api/hooks/sessions'
import { TRAVEL_OBJECTIVES, type SessionDetail } from '../api/types'
import { WEIGHT_STEP_PERCENT } from '../config'
import { OBJECTIVE_LABELS } from './labels'
import { weightSplitText } from './scoring'
import './ScoringControls.css'

/**
 * Organiser's ranking controls: Travel Objective (FR-D6) and the attendance
 * vs travel weighting (FR-D9), which snaps to 10% steps (FR-D9.1). Changes are
 * saved to the Session and re-rank existing results without re-routing.
 */
export function ScoringControls({ session, disabled }: { session: SessionDetail; disabled?: boolean }) {
  const update = useUpdateSession(session.id)
  const [weight, setWeight] = useState(session.attendanceWeightPercent)
  const saveTimer = useRef<number | undefined>(undefined)
  const pendingWeight = useRef<number | null>(null)
  const mutate = update.mutate

  // Follow the saved value when it changes from outside this slider.
  const [savedWeight, setSavedWeight] = useState(session.attendanceWeightPercent)
  if (savedWeight !== session.attendanceWeightPercent) {
    setSavedWeight(session.attendanceWeightPercent)
    setWeight(session.attendanceWeightPercent)
  }

  // Leaving the page mid-debounce still saves the last position.
  useEffect(
    () => () => {
      window.clearTimeout(saveTimer.current)
      if (pendingWeight.current !== null) mutate({ attendanceWeightPercent: pendingWeight.current })
    },
    [mutate],
  )

  function changeWeight(next: number) {
    const snapped = Math.round(next / WEIGHT_STEP_PERCENT) * WEIGHT_STEP_PERCENT
    setWeight(snapped)
    pendingWeight.current = snapped
    // Save once the slider settles rather than on every step.
    window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => {
      pendingWeight.current = null
      update.mutate({ attendanceWeightPercent: snapped })
    }, 400)
  }

  const status = update.isPending ? 'Saving…' : update.isError ? update.error.message : update.isSuccess ? 'Saved' : ''

  return (
    <div className="scoring">
      <fieldset className="scoring__group" disabled={disabled || update.isPending}>
        <legend className="chips__legend">Travel objective</legend>
        <div className="scoring__segmented">
          {TRAVEL_OBJECTIVES.map((o) => (
            <label key={o} className="scoring__seg">
              <input
                type="radio"
                name="travel-objective"
                value={o}
                checked={session.travelObjective === o}
                onChange={() => update.mutate({ travelObjective: o })}
              />
              <span>{OBJECTIVE_LABELS[o]}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="scoring__group">
        <label className="chips__legend" htmlFor="score-weighting">
          Score weighting
        </label>
        <input
          id="score-weighting"
          className="scoring__range"
          type="range"
          min={0}
          max={100}
          step={WEIGHT_STEP_PERCENT}
          value={weight}
          disabled={disabled}
          aria-valuetext={weightSplitText(weight)}
          onChange={(e) => changeWeight(Number(e.target.value))}
        />
        <div className="scoring__ends" aria-hidden="true">
          <span>Travel</span>
          <span>Attendance</span>
        </div>
        <p className="scoring__split">{weightSplitText(weight)}</p>
      </div>

      <p className={`scoring__status${update.isError ? ' scoring__status--error' : ''}`} role="status">
        {status}
      </p>
    </div>
  )
}
