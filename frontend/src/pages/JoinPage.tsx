import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { isApiError } from '../api/client'
import { useInvitation, useJoinSession } from '../api/hooks/invitations'
import type { InvitationPreview } from '../api/types'
import { StatusMessage } from '../components/StatusMessage'
import { formatDateTime, formatIsoDate } from '../lib/time'
import './JoinPage.css'

const availabilityPath = (sessionId: string) => `/sessions/${sessionId}/availability`

/**
 * Join via invitation link (UC-05). The user is already signed in (RequireAuth).
 *
 * The :token is Access Data (SRS §5.5): it's sent only in POST bodies, never
 * rendered or logged. Once joined, we `replace` to the id-based route so the
 * token also leaves the address bar and history.
 */
export function JoinPage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const invitation = useInvitation(token)
  const join = useJoinSession()

  const preview = invitation.data
  useEffect(() => {
    if (preview?.alreadyJoined) navigate(availabilityPath(preview.sessionId), { replace: true })
  }, [preview, navigate])

  if (invitation.isPending || preview?.alreadyJoined) {
    return <StatusMessage busy title="Opening invitation…" />
  }

  if (invitation.isError) {
    const invalid = isApiError(invitation.error) && invitation.error.code === 'INVITATION_INVALID'
    return (
      <StatusMessage
        title={invalid ? "This invitation link isn't valid" : "Couldn't open this invitation"}
        action={
          invalid ? (
            <Link className="btn-primary" to="/sessions">
              Go to your sessions
            </Link>
          ) : (
            <button type="button" className="btn-primary" onClick={() => void invitation.refetch()}>
              Try again
            </button>
          )
        }
      >
        {invalid
          ? 'Check you copied the whole link, or ask the organiser to send it again.'
          : invitation.error.message}
      </StatusMessage>
    )
  }

  if (!preview) return null

  if (!preview.activitySupported) {
    return (
      <StatusMessage
        title="This activity is currently unavailable"
        action={<Link className="btn-primary" to="/sessions">Go to your sessions</Link>}
      >
        This is an older invitation. The activity no longer has a verified venue catalogue, so the session is read-only and cannot accept new members.
      </StatusMessage>
    )
  }

  // UC-05.AC.1: closed sessions show their status instead of the entry flow.
  if (preview.isClosed) return <ClosedInvitation preview={preview} />

  const joinError = join.isError
    ? isApiError(join.error) && join.error.code === 'SESSION_CLOSED'
      ? 'This session has just stopped accepting responses.'
      : join.error.message
    : null

  return (
    <div className="join">
      <SessionSummary preview={preview} />
      {joinError && (
        <p className="join__error" role="alert">
          {joinError}
        </p>
      )}
      <button
        type="button"
        className="btn-primary"
        disabled={join.isPending}
        onClick={() =>
          join.mutate(token!, {
            onSuccess: (res) => navigate(availabilityPath(res.sessionId), { replace: true }),
          })
        }
      >
        {join.isPending ? 'Joining…' : 'Join and add your availability'}
      </button>
      <p className="join__note">
        You'll mark when you're free, where you'd travel from and how. Your address is never shown to
        anyone else.
      </p>
    </div>
  )
}

function SessionSummary({ preview }: { preview: InvitationPreview }) {
  const dates =
    preview.startDate === preview.endDate
      ? formatIsoDate(preview.startDate)
      : `${formatIsoDate(preview.startDate)} – ${formatIsoDate(preview.endDate)}`
  return (
    <section className="join__card">
      <p className="join__eyebrow">{preview.organiserName} invited you to</p>
      <h2 className="join__name">{preview.name}</h2>
      <dl className="join__facts">
        <div>
          <dt>Activity</dt>
          <dd>{preview.activityTypeName}</dd>
        </div>
        <div>
          <dt>Dates</dt>
          <dd>{dates}</dd>
        </div>
        <div>
          <dt>Respond by</dt>
          <dd>{formatDateTime(preview.responseDeadline, preview.timezone)}</dd>
        </div>
      </dl>
    </section>
  )
}

function ClosedInvitation({ preview }: { preview: InvitationPreview }) {
  const reason =
    preview.status === 'CANCELLED'
      ? { title: 'This session was cancelled', body: `${preview.organiserName} cancelled ${preview.name}.` }
      : preview.status === 'CONFIRMED'
        ? { title: 'This session is already confirmed', body: `${preview.name} has a final plan, and it's no longer taking new people.` }
        : {
            title: 'Responses are closed',
            body: `${preview.name} stopped taking responses on ${formatDateTime(preview.responseDeadline, preview.timezone)}.`,
          }
  return (
    <StatusMessage
      title={reason.title}
      action={
        <Link className="btn-primary" to="/sessions">
          Go to your sessions
        </Link>
      }
    >
      {reason.body}
    </StatusMessage>
  )
}
