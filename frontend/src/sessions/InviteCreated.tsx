import { Link } from 'react-router'
import type { CreateSessionResponse } from '../api/types'
import { CopyLinkField } from '../components/CopyLinkField'
import { formatDateTime, formatIsoDate } from '../lib/time'
import './InviteCreated.css'

type Props = {
  result: CreateSessionResponse
  onCreateAnother: () => void
}

/**
 * Shown after UC-01 succeeds (step 5): the invitation link to share, plus
 * next steps. The link is Access Data (§5.5): shown to the Organiser who
 * owns it, never logged.
 */
export function InviteCreated({ result, onCreateAnother }: Props) {
  const { session, invitationUrl } = result
  const joinPath = new URL(invitationUrl).pathname

  const dates =
    session.startDate === session.endDate
      ? formatIsoDate(session.startDate)
      : `${formatIsoDate(session.startDate)} – ${formatIsoDate(session.endDate)}`

  return (
    <div className="created">
      <section className="created__card">
        <span className="created__tick" aria-hidden="true">
          ✓
        </span>
        <h2 className="created__title">Session created</h2>
        <p className="created__name">{session.name}</p>
        <p className="created__meta">
          {session.activityType.name} · {dates} · {session.durationMinutes} min
        </p>
        <p className="created__meta">Responses close {formatDateTime(session.responseDeadline, session.timezone)}</p>
      </section>

      <section className="created__share">
        <CopyLinkField
          id="invite-link"
          label="Invite link"
          url={invitationUrl}
          shareTitle={session.name}
          shareText={`Mark when you're free for ${session.name}`}
        />
        <p className="field__hint">
          Share it with your group chat. Anyone with the link can join after signing in with Google.
        </p>
      </section>

      <div className="created__actions">
        {/* The Organiser responds too (SRS §5.5). */}
        <Link className="btn-primary" to={joinPath}>
          Add your availability
        </Link>
        <Link className="created__secondary" to={`/sessions/${session.id}/status`}>
          View responses
        </Link>
        <button type="button" className="created__textbtn" onClick={onCreateAnother}>
          Create another session
        </button>
      </div>
    </div>
  )
}
