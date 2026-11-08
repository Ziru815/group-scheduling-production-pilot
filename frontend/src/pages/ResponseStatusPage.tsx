import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { useGenerateRecommendations } from '../api/hooks/recommendations'
import { useCancelSession, useInvitationLink, useSession } from '../api/hooks/sessions'
import type { SessionDetail } from '../api/types'
import { CopyLinkField } from '../components/CopyLinkField'
import { InlineConfirm } from '../components/InlineConfirm'
import { formatDateTime, formatIsoDate } from '../lib/time'
import { GenerateError } from '../sessions/GenerateError'
import { ParticipantList } from '../sessions/ParticipantList'
import { ScoringControls } from '../sessions/ScoringControls'
import { SessionSettings } from '../sessions/SessionSettings'
import { buildInvitationMessage } from '../sessions/invitationSharing'
import './ResponseStatusPage.css'

/**
 * Response status: Organiser only (SRS §3.1; wrapped in RequireOrganiser).
 * UC-03 who has responded; FR-D6/FR-D9 ranking controls; UC-09 generate and
 * open ranked options; UC-02 edit details; UC-04 cancel. RequireOrganiser has
 * already loaded the Session, so it's in the query cache here.
 */
export function ResponseStatusPage() {
  const { id } = useParams()
  const session = useSession(id)
  if (!session.data) return null
  return <StatusView session={session.data} />
}

function StatusView({ session }: { session: SessionDetail }) {
  const navigate = useNavigate()
  const active = session.status === 'ACTIVE'
  const invitation = useInvitationLink(session.id, active)
  const generate = useGenerateRecommendations(session.id)
  const cancel = useCancelSession(session.id)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const resultsPath = `/sessions/${session.id}/results`
  const resultsCurrent = session.hasRecommendations && !session.recommendationsStale

  function openRankedOptions() {
    if (resultsCurrent) return navigate(resultsPath)
    generate.mutate(undefined, { onSuccess: () => navigate(resultsPath) })
  }

  const dates =
    session.startDate === session.endDate
      ? formatIsoDate(session.startDate)
      : `${formatIsoDate(session.startDate)} – ${formatIsoDate(session.endDate)}`
  const invitationMessage = invitation.data
    ? buildInvitationMessage({
        name: session.name,
        activityName: session.activityType.name,
        startDate: session.startDate,
        endDate: session.endDate,
        responseDeadline: session.responseDeadline,
        timezone: session.timezone,
        invitationUrl: invitation.data.invitationUrl,
      })
    : undefined

  return (
    <div className="rstatus">
      <header className="rstatus__head">
        <h2 className="rstatus__name">{session.name}</h2>
        <p className="rstatus__meta">
          {session.activityType.name} · {dates}
        </p>
        <p className="rstatus__meta">
          {session.isClosed && active ? 'Responses closed' : 'Responses close'}{' '}
          {formatDateTime(session.responseDeadline, session.timezone)}
        </p>
      </header>

      {session.status === 'CANCELLED' && (
        // FR-A5.1
        <p className="rstatus__banner rstatus__banner--muted">You cancelled this session. Everyone who opens it sees it's cancelled.</p>
      )}
      {session.status === 'CONFIRMED' && (
        <p className="rstatus__banner rstatus__banner--ok">
          Confirmed. <Link to={`/sessions/${session.id}/confirmed`}>See the final plan</Link>
        </p>
      )}
      {notice && (
        <p className="rstatus__banner rstatus__banner--ok" role="status">
          {notice}
        </p>
      )}

      {active && session.myResponseStatus !== 'SUBMITTED' && !session.isClosed && (
        // The Organiser responds too (SRS §5.5).
        <Link className="rstatus__nudge" to={`/sessions/${session.id}/availability`}>
          <span>You haven't added your own times yet.</span>
          <span className="rstatus__nudge-cta">Add them →</span>
        </Link>
      )}

      <ParticipantList sessionId={session.id} timeZone={session.timezone} />

      {active && invitation.data && (
        <section className="rstatus__section">
          <CopyLinkField
            id="status-invite-link"
            label="Invite more people"
            url={invitation.data.invitationUrl}
            shareTitle={session.name}
            shareText={`Mark when you're free for ${session.name}`}
            message={invitationMessage}
            showQr
          />
        </section>
      )}

      {active && (
        <section className="rstatus__section rstatus__ranking" aria-label="Ranking">
          <ScoringControls session={session} />

          {session.hasRecommendations && session.recommendationsStale && (
            <p className="rstatus__stale">Responses or details changed since the options were ranked.</p>
          )}
          <GenerateError error={generate.error} onRetry={openRankedOptions} />
          <button type="button" className="btn-primary" onClick={openRankedOptions} disabled={generate.isPending}>
            {generate.isPending
              ? 'Finding the best options…'
              : session.hasRecommendations && session.recommendationsStale
                ? 'Update ranked options'
                : 'View ranked options'}
          </button>
        </section>
      )}

      {!active && session.hasRecommendations && (
        <Link className="rstatus__secondary" to={resultsPath}>
          View ranked options
        </Link>
      )}

      <SessionSettings session={session} onSaved={setNotice} />

      {active && (
        <section className="rstatus__section">
          {confirmCancel ? (
            // UC-04 steps 2–3 (and UC-04.AC.1 when they back out).
            <InlineConfirm
              text="Cancel this session? Everyone who opens it will see it's cancelled, and no more responses will be accepted. This can't be undone."
              confirmLabel="Cancel session"
              cancelLabel="Keep session"
              busy={cancel.isPending}
              busyLabel="Cancelling…"
              danger
              onConfirm={() =>
                cancel.mutate(undefined, {
                  onSuccess: () => {
                    setConfirmCancel(false)
                    setNotice(null)
                    window.scrollTo({ top: 0 })
                  },
                })
              }
              onCancel={() => setConfirmCancel(false)}
            />
          ) : (
            <button type="button" className="rstatus__cancel" onClick={() => setConfirmCancel(true)}>
              Cancel session
            </button>
          )}
          {cancel.isError && (
            <p className="rstatus__error" role="alert">
              {cancel.error.message}
            </p>
          )}
        </section>
      )}
    </div>
  )
}
