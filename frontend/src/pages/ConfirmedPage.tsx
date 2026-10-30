import { Link, useParams } from 'react-router'
import { isApiError } from '../api/client'
import { useRetryCalendarSync } from '../api/hooks/calendar'
import { useMyResponse } from '../api/hooks/myResponse'
import { useSession } from '../api/hooks/sessions'
import type { SessionDetail } from '../api/types'
import { StatusMessage } from '../components/StatusMessage'
import { formatDateTime, formatTimeRange } from '../lib/time'
import { mapsLink } from '../results/maps'
import { venueAvailabilityGuidance, venueCategoryLabel } from '../results/venueGuidance'
import './ConfirmedPage.css'

/**
 * Confirmed: terminal screen (SRS §3.1, FR-E5). Shows the confirmed Venue,
 * date and time, who's attending, and that booking is the group's job.
 * Visible to every member; no notification is sent (C4), people find it here.
 */
export function ConfirmedPage() {
  const { id } = useParams()
  const session = useSession(id)
  const mine = useMyResponse(id)

  if (session.isPending) return <StatusMessage busy title="Loading…" />
  if (session.isError) {
    const missing = isApiError(session.error) && session.error.status === 404
    return (
      <StatusMessage
        title={missing ? "We couldn't find that session" : "Couldn't load this session"}
        action={
          missing ? (
            <Link className="btn-primary" to="/sessions">
              Back to your sessions
            </Link>
          ) : (
            <button type="button" className="btn-primary" onClick={() => void session.refetch()}>
              Try again
            </button>
          )
        }
      >
        {missing ? "It may have been removed, or you haven't joined it." : session.error.message}
      </StatusMessage>
    )
  }

  return <ConfirmedView session={session.data} myParticipantId={mine.data?.participantId ?? null} />
}

function ConfirmedView({ session, myParticipantId }: { session: SessionDetail; myParticipantId: string | null }) {
  const plan = session.confirmed
  const retryCalendar = useRetryCalendarSync(session.id)

  if (session.status === 'CANCELLED') {
    return (
      <StatusMessage
        title="This session was cancelled"
        action={
          <Link className="btn-primary" to="/sessions">
            Back to your sessions
          </Link>
        }
      >
        {session.organiserName} cancelled {session.name}, so there's no plan.
      </StatusMessage>
    )
  }

  if (!plan) {
    const isOrganiser = session.myRole === 'ORGANISER'
    return (
      <StatusMessage
        title="No plan confirmed yet"
        action={
          session.hasRecommendations ? (
            <Link className="btn-primary" to={`/sessions/${session.id}/results`}>
              See the ranked options
            </Link>
          ) : (
            <Link className="btn-primary" to={`/sessions/${session.id}/availability`}>
              Your availability
            </Link>
          )
        }
      >
        {isOrganiser
          ? 'Pick one of the ranked options to confirm the final plan.'
          : `${session.organiserName} hasn't confirmed a time and place yet.`}
      </StatusMessage>
    )
  }

  const going = myParticipantId !== null && plan.attendees.some((a) => a.participantId === myParticipantId)
  const calendarSync = retryCalendar.data ?? plan.calendarSync

  return (
    <div className="confirmed">
      <section className="confirmed__hero">
        <span className="confirmed__tick" aria-hidden="true">
          ✓
        </span>
        <h2 className="confirmed__title">It's confirmed</h2>
        <p className="confirmed__session">{session.name}</p>
        <p className="confirmed__venue">{plan.venue.name}</p>
        <p className="confirmed__when">{formatTimeRange(plan.start, plan.end, session.timezone)}</p>
        <p className={going ? 'confirmed__you confirmed__you--going' : 'confirmed__you'}>
          {going ? "You're going" : "You're not on the attending list for this time"}
        </p>
      </section>

      <section className="confirmed__section" aria-labelledby="confirmed-where">
        <h3 className="confirmed__subhead" id="confirmed-where">
          Where
        </h3>
        <p className="confirmed__address">{plan.venue.address}</p>
        <p className="confirmed__address">
          <strong>{venueCategoryLabel(plan.venue.category)}</strong>
          {plan.venue.meetingPoint && <> · Meet at {plan.venue.meetingPoint}</>}
        </p>
        <a
          className="confirmed__map"
          href={mapsLink(plan.venue.latitude, plan.venue.longitude)}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open in Google Maps
        </a>
      </section>

      <section className="confirmed__section" aria-labelledby="confirmed-who">
        <h3 className="confirmed__subhead" id="confirmed-who">
          Who's in · {plan.attendees.length}
        </h3>
        <ul className="confirmed__people">
          {plan.attendees.map((a) => (
            <li key={a.participantId}>
              <span>
                {a.displayName}
                {a.participantId === myParticipantId && <span className="confirmed__me"> (you)</span>}
              </span>
              <span className="confirmed__attending">Attending</span>
            </li>
          ))}
        </ul>
      </section>

      {/* FR-E5 / UC-12 step 3: the System must not imply the venue is booked (§5.2). */}
      <p className="confirmed__booking">
        <strong>The venue isn't booked or reserved by this app.</strong> {venueAvailabilityGuidance(plan.venue.category)}
        {' '}Venue data: {plan.venue.dataSource}
        {plan.venue.lastUpdated && ` · updated ${new Intl.DateTimeFormat('en-SG', { dateStyle: 'medium' }).format(new Date(plan.venue.lastUpdated))}`}.
      </p>

      <section className="confirmed__calendar" aria-labelledby="confirmed-calendar">
        <h3 className="confirmed__subhead" id="confirmed-calendar">
          Google Calendar
        </h3>
        <p>
          {calendarSync.failed > 0
            ? `The plan is confirmed, but ${calendarSync.failed} calendar ${calendarSync.failed === 1 ? 'sync needs' : 'syncs need'} another try.`
            : calendarSync.succeeded > 0
              ? `${calendarSync.succeeded} ${calendarSync.succeeded === 1 ? 'calendar is' : 'calendars are'} up to date.`
              : 'The plan is confirmed. No Calendar changes were needed.'}
          {calendarSync.notConnected > 0 &&
            ` ${calendarSync.notConnected} ${calendarSync.notConnected === 1 ? 'person does' : 'people do'} not have Google Calendar connected.`}
        </p>
        {retryCalendar.isError && (
          <p className="confirmed__calendar-error" role="alert">
            {retryCalendar.error.message}
          </p>
        )}
        {calendarSync.canRetry && session.activitySupported && (
          <button
            type="button"
            className="confirmed__calendar-retry"
            disabled={retryCalendar.isPending}
            onClick={() => retryCalendar.mutate()}
          >
            {retryCalendar.isPending ? 'Retrying…' : 'Retry calendar sync'}
          </button>
        )}
      </section>

      <p className="confirmed__meta">
        Confirmed by {session.myRole === 'ORGANISER' ? 'you' : session.organiserName} on{' '}
        {formatDateTime(plan.confirmedAt, session.timezone)}. People with Google Calendar connected get the event added.
      </p>

      <Link className="confirmed__secondary" to="/sessions">
        Back to your sessions
      </Link>
    </div>
  )
}
