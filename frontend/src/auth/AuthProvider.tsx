import { useMemo, type ReactNode } from 'react'
import { isApiError } from '../api/client'
import { useMe } from '../api/hooks/me'
import { AuthContext, type AuthState } from './useAuth'

/**
 * Who is signed in, derived from GET /api/me (UC-00). The session itself is an
 * httpOnly cookie the frontend never sees; a 401 from /api/me means signed out.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const { isError, error, data, refetch } = useMe()

  const state = useMemo<AuthState>(() => {
    if (isError) {
      if (isApiError(error) && error.status === 401) return { status: 'signedOut', user: null }
      return { status: 'error', user: null, retry: () => void refetch() }
    }
    if (data) return { status: 'signedIn', user: data }
    return { status: 'loading', user: null }
  }, [isError, error, data, refetch])

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
}
