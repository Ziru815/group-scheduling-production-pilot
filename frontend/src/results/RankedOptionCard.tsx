import { useState } from 'react'
import type { RankedCombination } from '../api/types'
import { formatTimeRange } from '../lib/time'
import { ABSENCE_LABELS, TRANSPORT_LABELS } from '../sessions/labels'
import { visibleTimeOptions } from './groupRecommendations'
import { mapsLink } from './maps'
import { venueAvailabilityGuidance, venueCategoryLabel } from './venueGuidance'
import './RankedOptionCard.css'

type Props = {
  options: RankedCombination[]
  selectedCombinationId: string
  displayRank: number
  requestedMinimum: number
  timeZone: string
  expanded: boolean
  interactionDisabled?: boolean
  onToggle: () => void
  onSelectOption: (combinationId: string) => void
  /** The Session's confirmed choice, if this is it. */
  isConfirmed?: boolean
}

/**
 * One ranked Combination (FR-E1). Expanded, it shows each attending
 * participant's travel time and mode (FR-E2) and who can't attend (FR-E3).
 * Names and travel times only: never anyone's address (NFR-13).
 */
export function RankedOptionCard({
  options,
  selectedCombinationId,
  displayRank,
  requestedMinimum,
  timeZone,
  expanded,
  interactionDisabled = false,
  onToggle,
  onSelectOption,
  isConfirmed,
}: Props) {
  const [showAllTimes, setShowAllTimes] = useState(false)
  const o = options.find((option) => option.combinationId === selectedCombinationId) ?? options[0]
  if (!o) throw new Error('RankedOptionCard requires at least one option')

  const unavailable = o.feasibilityStatus === 'DATA_UNAVAILABLE'
  const detailsId = `option-${options[0].combinationId}-details`
  const visibleTimes = visibleTimeOptions(options, showAllTimes)
  let cls = 'ropt'
  if (expanded) cls += ' ropt--expanded'
  if (displayRank === 1 && !unavailable) cls += ' ropt--top'
  const venueUpdated = o.venue.lastUpdated
    ? new Intl.DateTimeFormat('en-SG', { dateStyle: 'medium' }).format(new Date(o.venue.lastUpdated))
    : null

  return (
    <article className={cls}>
      <button
        type="button"
        className="ropt__summary"
        aria-expanded={expanded}
        aria-controls={detailsId}
        disabled={interactionDisabled}
        onClick={onToggle}
      >
        <div className="ropt__main">
          <div className="ropt__tags">
            {isConfirmed ? (
              <span className="ropt__tag ropt__tag--ok">Confirmed choice</span>
            ) : displayRank === 1 && !unavailable ? (
              <span className="ropt__tag ropt__tag--ok">Top match</span>
            ) : (
              <span className="ropt__tag">#{displayRank}</span>
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
          {options.length > 1 && <span className="ropt__time-count">{options.length} time options</span>}
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
          {options.length > 1 && (
            <section className="ropt__time-picker" aria-label={`Choose a time for ${o.venue.name}`}>
              <h4 className="ropt__subhead">Choose a time</h4>
              <div className="ropt__times">
                {visibleTimes.map((option) => (
                  <button
                    type="button"
                    className={option.combinationId === o.combinationId ? 'ropt__time ropt__time--selected' : 'ropt__time'}
                    aria-pressed={option.combinationId === o.combinationId}
                    disabled={interactionDisabled}
                    key={option.combinationId}
                    onClick={() => onSelectOption(option.combinationId)}
                  >
                    {formatTimeRange(option.start, option.end, timeZone)}
                  </button>
                ))}
              </div>
              {visibleTimes.length < options.length || showAllTimes ? (
                <button
                  type="button"
                  className="ropt__show-times"
                  disabled={interactionDisabled}
                  onClick={() => setShowAllTimes((visible) => !visible)}
                >
                  {showAllTimes ? 'Show fewer times' : `Show all ${options.length} times`}
                </button>
              ) : null}
            </section>
          )}

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
            <span>
              <strong>{venueCategoryLabel(o.venue.category)}</strong>
              {o.venue.meetingPoint && <> · Meet at {o.venue.meetingPoint}</>}
              <br />
              {o.venue.address}
            </span>
            <a href={mapsLink(o.venue.latitude, o.venue.longitude)} target="_blank" rel="noopener noreferrer">
              Open in Google Maps
            </a>
          </div>
          <p className="ropt__source">
            Venue data: {o.venue.dataSource}
            {venueUpdated && ` · updated ${venueUpdated}`}. {venueAvailabilityGuidance(o.venue.category)}
          </p>
          <p className="ropt__breakdown">
            Attendance score {o.attendanceScore} · travel score {o.travelScore}
            {o.totalTravelMinutes !== null && ` · ${o.totalTravelMinutes} min total travel, longest ${o.maxTravelMinutes} min`}
          </p>
        </div>
      )}
    </article>
  )
}
