import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useSessions } from '../api/hooks/sessions'
import type { SessionListItem } from '../api/types'
import { PlusIcon } from '../components/icons'
import { StatusMessage } from '../components/StatusMessage'
import { formatDateTime } from '../lib/time'
import { deadlinePassed, destinationOf, GROUP_TITLES, groupOf, groupSessions } from '../sessions/groupSessions'
import './SessionsPage.css'

/**
 * Your sessions: the entry screen (SRS §3.1). Sessions grouped by state; each
 * shows its name, organiser, and either the response deadline or the confirmed
 * venue and time. The + button opens New session.
 */
export function SessionsPage() {
  const sessions = useSessions()

  return (
    <div className="sessions">
      <JoinByLink />

      {sessions.isPending && <StatusMessage busy title="Loading your sessions…" />}

      {sessions.isError && (
        <StatusMessage
          title="Couldn't load your sessions"
          action={
            <button type="button" className="btn-primary" onClick={() => void sessions.refetch()}>
              Try again
            </button>
          }
        >
          {sessions.error.message}
        </StatusMessage>
      )}

      {sessions.data?.length === 0 && (
        <StatusMessage
          title="No sessions yet"
          action={
            <Link className="btn-primary" to="/sessions/new">
              Create a session
            </Link>
          }
        >
          Create one to start planning, or open an invitation link someone sent you.
        </StatusMessage>
      )}

      {sessions.data &&
        groupSessions(sessions.data).map(({ group, items }) => (
          <section key={group} className="sessions__group" aria-labelledby={`group-${group}`}>
            <h2 className="sessions__heading" id={`group-${group}`}>
              {GROUP_TITLES[group]}
            </h2>
            <ul className="sessions__list">
              {items.map((s) => (
                <li key={s.id}>
                  <SessionCard session={s} />
                </li>
              ))}
            </ul>
          </section>
        ))}

      <Link className="sessions__fab" to="/sessions/new" aria-label="Create session">
        <PlusIcon />
      </Link>
    </div>
  )
}

/**
 * Invitation links are normally opened directly from a chat. The local demo
 * also needs an obvious hand-off between personas, so accept either the full
 * link copied by the organiser or the token at its end.
 */
function JoinByLink() {
  const navigate = useNavigate()
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  function openInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const token = invitationToken(value)
    if (!token) {
      setError('Paste the complete invitation link, or the invitation code after /join/.')
      return
    }
    setError(null)
    navigate(`/join/${encodeURIComponent(token)}`)
  }

  return (
    <section className="sessions__join" aria-labelledby="join-by-link-title">
      <div>
        <h2 id="join-by-link-title">Join a session</h2>
        <p>Paste the invitation link sent by the organiser.</p>
      </div>
      <form className="sessions__join-form" onSubmit={openInvitation}>
        <label className="sr-only" htmlFor="invitation-link-entry">
          Invitation link or code
        </label>
        <input
          id="invitation-link-entry"
          type="text"
          inputMode="url"
          autoComplete="off"
          placeholder="Paste invite link or code"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? 'invitation-link-error' : undefined}
        />
        <button className="btn-primary" type="submit">
          Open invitation
        </button>
      </form>
      {error && (
        <p className="sessions__join-error" id="invitation-link-error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}

function invitationToken(rawValue: string): string | null {
  const value = rawValue.trim()
  if (!value) return null

  try {
    const url = new URL(value, window.location.origin)
    const match = url.pathname.match(/^\/join\/([^/]+)\/?$/)
    if (match) return decodeURIComponent(match[1])
  } catch {
    return null
  }

  // A copied code contains no path separators. Keep the same upper bound as
  // the backend request model and reject free-form text early.
  return /^[A-Za-z0-9_-]{1,256}$/.test(value) ? value : null
}

function SessionCard({ session: s }: { session: SessionListItem }) {
  const group = groupOf(s)
  const closed = deadlinePassed(s)

  const detail = s.confirmed
    ? `${s.confirmed.venueName} · ${formatDateTime(s.confirmed.start, s.timezone)}`
    : `${closed ? 'Responses closed' : 'Responses close'} ${formatDateTime(s.responseDeadline, s.timezone)}`

  const badge =
    group === 'needsResponse'
      ? { text: 'Respond', tone: 'warn' }
      : group === 'organising'
        ? { text: `${s.submittedCount} of ${s.participantCount} responded`, tone: 'info' }
        : group === 'confirmed'
          ? { text: 'Confirmed', tone: 'ok' }
          : group === 'cancelled'
            ? { text: 'Cancelled', tone: 'muted' }
            : s.myResponseStatus === 'SUBMITTED'
              ? { text: 'Submitted', tone: 'muted' }
              : { text: 'Closed', tone: 'muted' }

  return (
    <Link className={`scard${group === 'cancelled' ? ' scard--muted' : ''}`} to={destinationOf(s)}>
      <div className="scard__main">
        <span className="scard__name">{s.name}</span>
        <span className="scard__meta">
          {s.myRole === 'ORGANISER' ? `${s.activityTypeName} · you're organising` : `Organised by ${s.organiserName}`}
        </span>
        <span className="scard__meta">{detail}</span>
        {group === 'organising' && s.myResponseStatus === 'NOT_SUBMITTED' && (
          <span className="scard__nudge">You haven't added your own times yet</span>
        )}
      </div>
      <span className={`scard__badge scard__badge--${badge.tone}`}>{badge.text}</span>
    </Link>
  )
}
