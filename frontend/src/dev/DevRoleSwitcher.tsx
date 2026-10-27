import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useMockPersonas, useSwitchPersona } from '../api/hooks/devMock'
import { useSignOut } from '../api/hooks/me'
import { useAuth } from '../auth/useAuth'
import './DevRoleSwitcher.css'

/**
 * DEV ONLY (mock backend). Switch between mock personas to see a session from
 * the organiser's or a participant's side. E.g. on "Weekend badminton", Wei Jie
 * is the organiser and Amirah is a participant. Loaded lazily behind
 * __MOCKS_ENABLED__, so it isn't in production builds.
 */
export default function DevRoleSwitcher() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const personas = useMockPersonas()
  const switchPersona = useSwitchPersona()
  const signOut = useSignOut()

  return (
    <div className="devswitch">
      <button
        type="button"
        className="devswitch__toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {__DEMO__ ? 'DEMO' : 'DEV'} · {auth.user?.displayName ?? '…'}
      </button>
      {open && (
        <div className="devswitch__panel" role="dialog" aria-label="Dev persona switcher">
          <p className="devswitch__heading">{__DEMO__ ? 'Demo: view as' : 'Dev mock: view as'}</p>
          <ul className="devswitch__list">
            {personas.data?.users.map((p) => {
              const current = p.id === personas.data.currentUserId
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    className={current ? 'devswitch__item devswitch__item--current' : 'devswitch__item'}
                    disabled={current || switchPersona.isPending}
                    onClick={() =>
                      switchPersona.mutate(p.id, {
                        onSuccess: () => {
                          setOpen(false)
                          // A participant cannot remain on an organiser-only
                          // status route. Land on the entry page, where they
                          // can paste the invitation link immediately.
                          navigate('/sessions')
                        },
                      })
                    }
                  >
                    <span className="devswitch__name">
                      {p.displayName}
                      {current ? ' (you)' : ''}
                    </span>
                    <span className="devswitch__summary">{p.summary}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          <button type="button" className="devswitch__signout" onClick={() => signOut.mutate()}>
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
