import { useSignOut } from '../api/hooks/me'
import { useAuth } from '../auth/useAuth'
import { CalendarSection } from '../profile/CalendarSection'
import './ProfilePage.css'

/** Profile: not specified in SRS §3.1; contents are a proposed default (api-contract.md, open question 4). */
export function ProfilePage() {
  const auth = useAuth()
  const signOut = useSignOut()

  return (
    <div className="profile">
      {auth.user && (
        <section className="profile__card">
          <p className="profile__name">{auth.user.displayName}</p>
          {/* The user's own email: never shown to anyone else (NFR-13). */}
          <p className="profile__email">{auth.user.email}</p>
        </section>
      )}

      <CalendarSection />

      {signOut.isError && (
        <p className="profile__error" role="alert">
          {signOut.error.message}
        </p>
      )}
      <button
        type="button"
        className="profile__signout"
        onClick={() => signOut.mutate()}
        disabled={signOut.isPending}
      >
        {signOut.isPending ? 'Signing out…' : 'Sign out'}
      </button>
    </div>
  )
}
