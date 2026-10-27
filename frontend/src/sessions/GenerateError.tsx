import { isApiError } from '../api/client'
import './GenerateError.css'

/** UC-09.AC.1 (nothing qualifies) and UC-09.EX.1 (provider failed), shown in place. */
export function GenerateError({ error, onRetry }: { error: Error | null; onRetry: () => void }) {
  if (!error) return null
  const code = isApiError(error) ? error.code : 'UNKNOWN'
  if (code === 'NO_RESPONSES') {
    return <p className="generr">No one has submitted their times yet, so there's nothing to rank.</p>
  }
  if (code === 'NO_FEASIBLE_TIMESLOT') {
    return (
      <p className="generr">
        No time works for at least the minimum number of people. Lower the minimum attendees in Session details, or wait
        for more responses.
      </p>
    )
  }
  return (
    <div className="generr generr--retry" role="alert">
      <span>{code === 'EXTERNAL_SERVICE_UNAVAILABLE' ? 'Travel times are unavailable right now.' : error.message}</span>
      <button type="button" className="generr__retry" onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}
