import type { RankedCombination } from '../api/types'
import { formatTimeRange } from '../lib/time'
import './ConfirmPlanPanel.css'

type Props = {
  option: RankedCombination
  requestedMinimum: number
  timeZone: string
  busy: boolean
  error: string | null
  onConfirm: () => void
  onCancel: () => void
}

/**
 * UC-12 steps 2–4: show the selected time, Venue and expected attendance, state
 * that live booking availability isn't guaranteed (step 3, §5.2), then confirm.
 * Backing out leaves the Session open and unchanged (UC-12.AC.1).
 */
export function ConfirmPlanPanel({ option: o, requestedMinimum, timeZone, busy, error, onConfirm, onCancel }: Props) {
  return (
    <section className="cplan" role="alertdialog" aria-labelledby="cplan-title" aria-describedby="cplan-booking">
      <h3 className="cplan__title" id="cplan-title">
        Confirm this plan?
      </h3>
      <dl className="cplan__facts">
        <div>
          <dt>Venue</dt>
          <dd>{o.venue.name}</dd>
        </div>
        <div>
          <dt>When</dt>
          <dd>{formatTimeRange(o.start, o.end, timeZone)}</dd>
        </div>
        <div>
          <dt>Attending</dt>
          <dd>
            {o.attendeeCount} {o.attendeeCount === 1 ? 'person' : 'people'}
          </dd>
        </div>
      </dl>
      <p className="cplan__booking" id="cplan-booking">
        <strong>This doesn't book the venue.</strong> Live availability isn't guaranteed, and booking it is the group's
        responsibility.
      </p>
      {!o.meetsRequestedMinimum && (
        <p className="cplan__booking">
          <strong>This is a near match.</strong> It has {o.attendeeCount} attendees instead of the requested {requestedMinimum}.
          The people listed as not going will not be included in the confirmed plan.
        </p>
      )}
      <p className="cplan__note">Everyone in the session will see the confirmed plan. This can't be undone.</p>
      {error && (
        <p className="cplan__error" role="alert">
          {error}
        </p>
      )}
      <div className="cplan__actions">
        <button type="button" className="btn-primary" onClick={onConfirm} disabled={busy} autoFocus>
          {busy ? 'Confirming…' : 'Confirm plan'}
        </button>
        <button type="button" className="cplan__cancel" onClick={onCancel} disabled={busy}>
          Not yet
        </button>
      </div>
    </section>
  )
}
