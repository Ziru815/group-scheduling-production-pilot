import { createContext, useContext } from 'react'
import type { Me } from '../api/types'

export type AuthState =
  | { status: 'loading'; user: null }
  | { status: 'signedIn'; user: Me }
  | { status: 'signedOut'; user: null }
  /** Couldn't tell (network or server error). Offer a retry. */
  | { status: 'error'; user: null; retry: () => void }

export const AuthContext = createContext<AuthState | null>(null)

/** Current sign-in state. Must be used inside <AuthProvider>. */
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
