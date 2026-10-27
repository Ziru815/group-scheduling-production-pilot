/**
 * Hooks for the MOCK-ONLY /api/dev endpoints behind the dev persona switcher.
 * Not part of the backend contract. Only call these when __MOCKS_ENABLED__.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import type { Id } from '../types'
import { broadcastIdentityChange, resetForNewIdentity } from './me'

export interface MockPersona {
  id: Id
  displayName: string
  /** e.g. "Organises Weekend badminton · 2 other sessions" */
  summary: string
}

export function useMockPersonas() {
  return useQuery({
    queryKey: ['dev', 'personas'],
    queryFn: () => api.get<{ currentUserId: Id | null; users: MockPersona[] }>('/api/dev/users'),
    enabled: __MOCKS_ENABLED__ || import.meta.env.VITE_DEMO_AUTH === 'true',
  })
}

/** Signs in as another mock user and refetches everything as them. */
export function useSwitchPersona() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: Id) => api.post<void>('/api/dev/sign-in', { userId }),
    onSuccess: () => {
      broadcastIdentityChange()
      return resetForNewIdentity(queryClient)
    },
  })
}
