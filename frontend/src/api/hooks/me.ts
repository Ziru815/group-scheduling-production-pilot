import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { api, redirectToBackend } from '../client'
import { queryKeys } from '../queryKeys'
import type { Me } from '../types'

export const IDENTITY_CHANGE_STORAGE_KEY = 'group-scheduler.identity-change'

/** Notify other tabs because the httpOnly identity cookie is shared by them. */
export function broadcastIdentityChange() {
  try {
    window.localStorage.setItem(IDENTITY_CHANGE_STORAGE_KEY, `${Date.now()}-${Math.random()}`)
  } catch {
    // Storage may be unavailable in an embedded demo. The active tab still
    // resets its own queries below, and focus refetch remains a fallback.
  }
}

/** UC-00. Resolves to the signed-in user, or fails with ApiError 401 when signed out. */
export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => api.get<Me>('/api/me'),
    staleTime: 5 * 60_000,
  })
}

/**
 * Drops every cached query except `me`, then resets `me` so it refetches.
 * While it refetches, the auth guard shows a spinner, so pages remount with
 * fresh data for whoever is now signed in (or redirect to sign-in).
 */
export async function resetForNewIdentity(queryClient: QueryClient) {
  await queryClient.cancelQueries()
  queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== queryKeys.me[0] })
  await queryClient.resetQueries({ queryKey: queryKeys.me })
}

/**
 * Starts Google sign-in (UC-00).
 * Real backend: a full-page redirect through Google that comes back to /signin
 * with an httpOnly session cookie. The page is navigating away, so the
 * mutation never settles.
 * Mock backend (dev): signs in instantly as `mockUserId` (default: Wei Jie).
 */
export function useSignIn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (options: { mockUserId?: string } = {}) => {
      if (__MOCKS_ENABLED__ || import.meta.env.VITE_DEMO_AUTH === 'true') {
        await api.post<void>('/api/dev/sign-in', { userId: options.mockUserId })
        return
      }
      // `next` is always /signin: it never carries an invitation token. The
      // page to return to is kept client-side (see src/auth/returnTo.ts).
      redirectToBackend('/api/auth/google/login', '/signin')
      await new Promise<never>(() => {})
    },
    onSuccess: () => {
      broadcastIdentityChange()
      return resetForNewIdentity(queryClient)
    },
  })
}

export function useSignOut() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<void>('/api/auth/logout'),
    onSuccess: () => {
      broadcastIdentityChange()
      return resetForNewIdentity(queryClient)
    },
  })
}
