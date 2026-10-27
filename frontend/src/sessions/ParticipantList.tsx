import { useResponseStatus } from '../api/hooks/responseStatus'
import type { ResponseStatus } from '../api/types'
import { StatusMessage } from '../components/StatusMessage'
import { formatTime } from '../lib/time'
import './ParticipantList.css'

const STATUS: Record<ResponseStatus, { label: string; tone: string; icon: string }> = {
  SUBMITTED: { label: 'Submitted', tone: 'ok', icon: '✓' },
  NOT_SUBMITTED: { label: 'Not yet', tone: 'muted', icon: '…' },
  WITHDRAWN: { label: 'Withdrawn', tone: 'warn', icon: '–' },
}

/** UC-03 / FR-B7: who has submitted, withdrawn or not replied. Names only (NFR-13). */
export function ParticipantList({ sessionId, timeZone }: { sessionId: string; timeZone: string }) {
  const responses = useResponseStatus(sessionId)

  if (responses.isPending) return <StatusMessage busy title="Loading responses…" />
  if (responses.isError) {
    return (
      <StatusMessage
        title="Couldn't load responses"
        action={
          <button type="button" className="btn-primary" onClick={() => void responses.refetch()}>
            Try again
          </button>
        }
      >
        {responses.error.message}
      </StatusMessage>
    )
  }

  const { participants, counts, refreshedAt } = responses.data
  const others = participants.filter((p) => p.role !== 'ORGANISER')

  return (
    <section className="plist" aria-labelledby="plist-title">
      <div className="plist__head">
        <h3 className="plist__title" id="plist-title">
          Responses · {counts.SUBMITTED} of {participants.length}
        </h3>
        <button
          type="button"
          className="plist__refresh"
          onClick={() => void responses.refetch()}
          disabled={responses.isFetching}
        >
          {responses.isFetching ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <ul className="plist__list">
        {participants.map((p) => {
          const st = STATUS[p.responseStatus]
          return (
            <li key={p.participantId} className="plist__row">
              <span className="plist__name">
                {p.displayName}
                {p.role === 'ORGANISER' && <span className="plist__role"> (you)</span>}
              </span>
              <span className={`plist__status plist__status--${st.tone}`}>
                <span aria-hidden="true">{st.icon}</span> {st.label}
              </span>
            </li>
          )
        })}
      </ul>

      {/* UC-03.AC.1 */}
      {others.length === 0 && (
        <p className="plist__empty">No one has joined yet. Share the invite link below.</p>
      )}
      <p className="field__hint">
        People appear here once they open the invite link and sign in. Updated {formatTime(refreshedAt, timeZone)}.
      </p>
    </section>
  )
}
