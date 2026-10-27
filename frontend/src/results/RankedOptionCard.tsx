import type { RankedCombination } from '../api/types'
import { formatTimeRange } from '../lib/time'
import { ABSENCE_LABELS, TRANSPORT_LABELS } from '../sessions/labels'
import { mapsLink } from './maps'
import './RankedOptionCard.css'

type Props = {
  option: RankedCombination
  requestedMinimum: number
  timeZone: string
  expanded: boolean
  onToggle: () => void
  /** The Session's confirmed choice, if this is it. */
  isConfirmed?: boolean
}

/**
 * One ranked Combination (FR-E1). Expanded, it shows each attending
 * participant's travel time and mode (FR-E2) and who can't attend (FR-E3).
 * Names and travel times only: never anyone's address (NFR-13).
 */
export function RankedOptionCard({ option: o, requestedMinimum, timeZone, expanded, onToggle, isConfirmed }: Props) {
  const unavailable = o.feasibilityStatus === 'DATA_UNAVAILABLE'
  const detailsId = `option-${o.combinationId}-details`
  let cls = 'ropt'
  if (expanded) cls += ' ropt--expanded'
  if (o.rank === 1 && !unavailable) cls += ' ropt--top'

  return (
    <article className={cls}>
      <button type="button" className="ropt__summary" aria-expanded={expanded} aria-controls={detailsId} onClick={onToggle}>
        <div className="ropt__main">
          <div className="ropt__tags">
            {isConfirmed ? (
              <span className="ropt__tag ropt__tag--ok">Confirmed choice</span>
            ) : o.rank === 1 && !unavailable ? (
              <span className="ropt__tag ropt__tag--ok">Top match</span>
            ) : (
              <span className="ropt__tag">#{o.rank}</span>
            )}
            {unavailable && <span className="ropt__tag ropt__tag--warn">Some travel times unavailable</span>}
            {!o.meetsRequestedMinimum && (
              <span className="ropt__tag ropt__tag--warn">
                Near match · {o.attendeeCount} of {requestedMinimum}
              </span>
            )}
          </div>
          <span className="ropt__venue">{o.venue.name}</span>
          <span className="ropt__when">{formatTimeRange(o.start, o.end, timeZone)}</span>
          <span className="ropt__facts">
            {o.attendeeCount} attending ·{' '}
            {o.averageTravelMinutes === null ? 'avg travel unavailable' : `${o.averageTravelMinutes} min avg travel`}
          </span>
        </div>
        {/* With travel times missing, the score only covers part of the group, so it's de-emphasised. */}
        <div
          className={unavailable ? 'ropt__score ropt__score--partial' : 'ropt__score'}
          aria-label={unavailable ? `Partial score ${o.combinedScore}, some travel times missing` : `Score ${o.combinedScore} out of 100`}
        >
          <span className="ropt__score-num">{o.combinedScore}</span>
          <span className="ropt__score-label">{unavailable ? 'partial' : 'score'}</span>
        </div>
      </button>

      {expanded && (
        <div className="ropt__details" id={detailsId}>
          <p className="ropt__why">{o.explanation}</p>

          <h4 className="ropt__subhead">Who's going · travel</h4>
          <ul className="ropt__people">
            {o.attendees.map((a) => (
              <li key={a.participantId} className="ropt__person">
                <span>{a.displayName}</span>
                <span className={a.travelMinutes === null ? 'ropt__travel ropt__travel--na' : 'ropt__travel'}>
                  {a.travelMinutes === null
                    ? `Travel time unavailable · ${TRANSPORT_LABELS[a.transportMode]}`
                    : `${a.travelMinutes} min · ${TRANSPORT_LABELS[a.transportMode]}`}
                </span>
              </li>
            ))}
          </ul>

          {o.absentees.length > 0 && (
            <>
              <h4 className="ropt__subhead">Not going</h4>
              <ul className="ropt__people">
                {o.absentees.map((a) => (
                  <li key={a.participantId} className="ropt__person ropt__person--absent">
                    <span>{a.displayName}</span>
                    <span className="ropt__travel">{ABSENCE_LABELS[a.attendanceStatus]}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="ropt__venueinfo">
            <span>{o.venue.address}</span>
            <a href={mapsLink(o.venue.latitude, o.venue.longitude)} target="_blank" rel="noopener noreferrer">
              Open in Google Maps
            </a>
          </div>
          <p className="ropt__breakdown">
            Attendance score {o.attendanceScore} · travel score {o.travelScore}
            {o.totalTravelMinutes !== null && ` · ${o.totalTravelMinutes} min total travel, longest ${o.maxTravelMinutes} min`}
          </p>
        </div>
      )}
    </article>
  )
}
