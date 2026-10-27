import { createBrowserRouter, createMemoryRouter, Navigate, type RouteObject } from 'react-router'
import { AppShell } from './AppShell'
import { RequireAuth } from '../auth/RequireAuth'
import { RequireOrganiser } from '../auth/RequireOrganiser'
import type { RouteHandle } from './routeHandle'
import { SignInPage } from '../pages/SignInPage'
import { SessionsPage } from '../pages/SessionsPage'
import { NewSessionPage } from '../pages/NewSessionPage'
import { JoinPage } from '../pages/JoinPage'
import { AvailabilityPage } from '../pages/AvailabilityPage'
import { ResponseStatusPage } from '../pages/ResponseStatusPage'
import { ResultsPage } from '../pages/ResultsPage'
import { ConfirmedPage } from '../pages/ConfirmedPage'
import { ProfilePage } from '../pages/ProfilePage'
import { NotFoundPage } from '../pages/NotFoundPage'

const handle = (h: RouteHandle) => h

/** The 7 screens of SRS §3.1, plus Profile. Everything except /signin requires sign-in. */
const routes: RouteObject[] = [
  // Sign-in sits outside the shell: nothing else is reachable before it (SRS §3.1).
  { path: '/signin', element: <SignInPage /> },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/sessions" replace /> },
      {
        path: 'sessions',
        element: <SessionsPage />,
        handle: handle({ title: 'Your sessions', hideBack: true }),
      },
      {
        path: 'sessions/new',
        element: <NewSessionPage />,
        handle: handle({ title: 'New session' }),
      },
      {
        path: 'join/:token',
        element: <JoinPage />,
        handle: handle({ title: 'Join session' }),
      },
      {
        // Not in the original screen list: after joining, /join/:token replaces
        // itself with this id-based route so the token leaves the address bar.
        // Also how participants return to edit (UC-07) without the invite link.
        path: 'sessions/:id/availability',
        element: <AvailabilityPage />,
        handle: handle({ title: 'Your availability' }),
      },
      {
        path: 'sessions/:id/status',
        element: (
          <RequireOrganiser>
            <ResponseStatusPage />
          </RequireOrganiser>
        ),
        handle: handle({ title: 'Responses' }),
      },
      {
        path: 'sessions/:id/results',
        element: <ResultsPage />,
        handle: handle({ title: 'Best matches' }),
      },
      {
        path: 'sessions/:id/confirmed',
        element: <ConfirmedPage />,
        handle: handle({ title: 'Confirmed' }),
      },
      {
        path: 'profile',
        element: <ProfilePage />,
        handle: handle({ title: 'Profile' }),
      },
      { path: '*', element: <NotFoundPage />, handle: handle({ title: 'Not found' }) },
    ],
  },
]

/**
 * Normal builds use the address bar. The hosted demo runs in a sandboxed frame
 * that doesn't own the URL, so it keeps navigation in memory and starts at
 * Your sessions.
 */
export const router = __DEMO__
  ? createMemoryRouter(routes, { initialEntries: ['/sessions'] })
  : createBrowserRouter(routes)
