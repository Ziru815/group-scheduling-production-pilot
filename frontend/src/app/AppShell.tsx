import { lazy, Suspense } from 'react'
import { NavLink, Outlet, useLocation, useMatches, useNavigate } from 'react-router'
import { ChevronLeftIcon, HomeIcon, PlusIcon, UserIcon } from '../components/icons'
import { isRouteHandle } from './routeHandle'
import './AppShell.css'

// Persona switcher for the mock backend; dropped from production builds.
const DevRoleSwitcher =
  __MOCKS_ENABLED__ || import.meta.env.VITE_DEMO_AUTH === 'true'
    ? lazy(() => import('../dev/DevRoleSwitcher'))
    : null

/**
 * Persistent layout for every signed-in screen (SRS §3.1 "Standard elements"):
 * a header with a back control (except on the entry screen) and a bottom
 * navigation bar with Sessions, Create and Profile.
 */
export function AppShell() {
  const matches = useMatches()
  const handle = [...matches].reverse().map((m) => m.handle).find(isRouteHandle)
  const title = handle?.title ?? ''
  const showBack = !handle?.hideBack

  return (
    <div className="shell">
      <header className="shell__header">
        <div className="shell__header-inner">
          {showBack ? <BackButton /> : <span className="shell__back-spacer" />}
          <h1 className="shell__title">{title}</h1>
          <span className="shell__back-spacer" />
        </div>
      </header>

      {(__DEMO__ || import.meta.env.VITE_DEMO_AUTH === 'true') && (
        <p className="shell__demo">
          Demo with labelled test data. Use the DEV button to switch people.
        </p>
      )}

      <main className="shell__main">
        <Outlet />
      </main>

      <BottomNav />

      {DevRoleSwitcher && (
        <Suspense fallback={null}>
          <DevRoleSwitcher />
        </Suspense>
      )}
    </div>
  )
}

function BackButton() {
  const navigate = useNavigate()
  const location = useLocation()

  function goBack() {
    // The first location React Router sees has the key "default". If we're
    // still on it (e.g. the user arrived from a shared link), there's nothing
    // to go back to inside the app, so fall back to the entry screen.
    if (location.key !== 'default') navigate(-1)
    else navigate('/sessions', { replace: true })
  }

  return (
    <button type="button" className="shell__back" onClick={goBack} aria-label="Back">
      <ChevronLeftIcon />
    </button>
  )
}

function BottomNav() {
  const { pathname } = useLocation()
  const isCreate = pathname === '/sessions/new'
  // Session sub-pages and invitation links belong to the Sessions tab.
  const isSessions =
    !isCreate && (pathname.startsWith('/sessions') || pathname.startsWith('/join/'))

  return (
    <nav className="shell__nav" aria-label="Primary">
      <div className="shell__nav-inner">
        <NavLink
          to="/sessions"
          className={() => navClass(isSessions)}
          aria-current={isSessions ? 'page' : undefined}
        >
          <HomeIcon />
          <span>Sessions</span>
        </NavLink>
        <NavLink to="/sessions/new" className={() => navClass(isCreate)}>
          <PlusIcon />
          <span>Create</span>
        </NavLink>
        <NavLink to="/profile" className={({ isActive }) => navClass(isActive)}>
          <UserIcon />
          <span>Profile</span>
        </NavLink>
      </div>
    </nav>
  )
}

function navClass(active: boolean) {
  return active ? 'shell__nav-link shell__nav-link--active' : 'shell__nav-link'
}
