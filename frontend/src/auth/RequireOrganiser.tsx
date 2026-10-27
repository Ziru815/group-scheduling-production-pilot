import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { isApiError } from '../api/client'
import { useSession } from '../api/hooks/sessions'
import { StatusMessage } from '../components/StatusMessage'

/**
 * Organiser-only screens (SRS §3.1 Response status). This only hides UI: the
 * backend enforces the same rule with 403s (§5.3).
 */
export function RequireOrganiser({ children }: { children: ReactNode }) {
  const { id } = useParams()
  const session = useSession(id)

  if (session.isPending) return <StatusMessage busy title="Loading session…" />

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

  if (session.data.myRole !== 'ORGANISER') {
    return (
      <StatusMessage
        title="Only the organiser can see this"
        action={
          <Link className="btn-primary" to="/sessions">
            Back to your sessions
          </Link>
        }
      >
        {session.data.organiserName} is organising {session.data.name}.
      </StatusMessage>
    )
  }

  return children
}
