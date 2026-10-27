import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { StatusMessage } from '../components/StatusMessage'
import { useAuth } from './useAuth'

/**
 * Every screen except sign-in needs a signed-in Google account (SRS §3.1, C5).
 * Signed-out users go to /signin; the page they wanted travels in router
 * state (in memory, never in the URL) so they come back to it afterwards.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const location = useLocation()

  if (auth.status === 'loading') return <StatusMessage busy fullPage title="Loading…" />

  if (auth.status === 'error') {
    return (
      <StatusMessage
        fullPage
        title="We couldn't check your sign-in"
        action={
          <button type="button" className="btn-primary" onClick={auth.retry}>
            Try again
          </button>
        }
      >
        Check your connection and try again.
      </StatusMessage>
    )
  }

  if (auth.status === 'signedOut') {
    return <Navigate to="/signin" replace state={{ from: location.pathname + location.search }} />
  }

  return children
}
