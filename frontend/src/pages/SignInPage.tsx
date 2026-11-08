import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router'
import { useSignIn } from '../api/hooks/me'
import { useMockPersonas } from '../api/hooks/devMock'
import { useAuth } from '../auth/useAuth'
import { consumeReturnTo, isSafeInAppPath, saveReturnTo } from '../auth/returnTo'
import { StatusMessage } from '../components/StatusMessage'
import './SignInPage.css'

/** Errors the backend can send back after Google (see api-contract.md #2). */
const CALLBACK_ERRORS: Record<string, string> = {
  declined: 'Sign-in was cancelled. You need to sign in with Google to create or join a session.',
  unavailable:
    "Google sign-in couldn't be completed. Please try again, or ask your organiser if it keeps happening.",
}

/**
 * Sign in (SRS §3.1, UC-00). Outside the app shell: nothing else is reachable
 * before sign-in. Once signed in, returns the user to the page they wanted.
 */
export function SignInPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const signIn = useSignIn()

  const from = (location.state as { from?: unknown } | null)?.from
  const callbackError = CALLBACK_ERRORS[params.get('error') ?? '']

  useEffect(() => {
    if (auth.status !== 'signedIn') return
    const target = consumeReturnTo() ?? (isSafeInAppPath(from) ? from : '/sessions')
    navigate(target, { replace: true })
  }, [auth.status, from, navigate])

  if (auth.status === 'loading' || auth.status === 'signedIn') {
    return <StatusMessage busy fullPage title="Loading…" />
  }

  function handleSignIn(mockUserId?: string) {
    // Kept client-side across the Google round trip; never sent to the backend.
    if (isSafeInAppPath(from)) saveReturnTo(from)
    signIn.mutate({ mockUserId })
  }

  const errorMessage = signIn.isError ? signIn.error.message : callbackError

  return (
    <main className="signin">
      <div className="signin__card">
        <h1 className="signin__title">Group Scheduler</h1>
        <p className="signin__lead">
          Find a time and place that works for everyone. Sign in with your Google Account to
          create or join a session.
        </p>

        {auth.status === 'error' && (
          <p className="signin__error" role="alert">
            We couldn't reach the server. Check your connection and try again.
          </p>
        )}
        {errorMessage && (
          <p className="signin__error" role="alert">
            {errorMessage}
          </p>
        )}

        {__MOCKS_ENABLED__ || import.meta.env.VITE_DEMO_AUTH === 'true' ? (
          <MockSignIn onSignIn={handleSignIn} pending={signIn.isPending} />
        ) : (
          <button
            type="button"
            className="btn-primary"
            onClick={() => handleSignIn()}
            disabled={signIn.isPending}
          >
            {signIn.isPending ? 'Redirecting to Google…' : 'Sign in with Google'}
          </button>
        )}

        <p className="signin__note">
          We only request your Google name and verified email to sign you in. We don't request
          Google Calendar access, and your home address is never shown to other participants.
        </p>
      </div>
    </main>
  )
}

/** Dev only: pick which mock persona the "Google" sign-in signs in as. */
function MockSignIn({ onSignIn, pending }: { onSignIn: (userId: string) => void; pending: boolean }) {
  const personas = useMockPersonas()
  const [selectedUserId, setSelectedUserId] = useState(
    __MOCKS_ENABLED__ ? 'u-weijie' : 'demo-organiser',
  )
  const users = personas.data?.users ?? [{ id: selectedUserId, displayName: 'Loading…', summary: '' }]
  // The in-page mock and real backend deliberately use different persona IDs.
  // Derive a valid value when the async list replaces the fallback instead of
  // posting a stale ID or synchronously setting state from an effect.
  const userId = users.some((persona) => persona.id === selectedUserId)
    ? selectedUserId
    : users[0]?.id ?? selectedUserId

  return (
    <div className="signin__mock">
      <label className="signin__mock-label" htmlFor="mock-persona">
        {__DEMO__ ? 'Demo: sign in as' : 'Dev mock: sign in as'}
      </label>
      <select
        id="mock-persona"
        className="signin__mock-select"
        value={userId}
        onChange={(e) => setSelectedUserId(e.target.value)}
      >
        {users.map((p) => (
          <option key={p.id} value={p.id}>
            {p.displayName}
            {p.summary ? `: ${p.summary}` : ''}
          </option>
        ))}
      </select>
      <button type="button" className="btn-primary" onClick={() => onSignIn(userId)} disabled={pending}>
        {pending ? 'Signing in…' : 'Sign in with Google'}
      </button>
    </div>
  )
}
