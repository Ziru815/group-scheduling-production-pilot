import type { Id } from './types'

/**
 * Central React Query keys. Session-scoped keys share the ['sessions', id]
 * prefix so `invalidateQueries({ queryKey: queryKeys.session(id) })` refreshes
 * everything about one Session at once.
 */
export const queryKeys = {
  me: ['me'] as const,
  activityTypes: ['activity-types'] as const,
  sessions: ['sessions'] as const,
  session: (id: Id) => ['sessions', id] as const,
  invitationLink: (id: Id) => ['sessions', id, 'invitation'] as const,
  myResponse: (id: Id) => ['sessions', id, 'my-response'] as const,
  responseStatus: (id: Id) => ['sessions', id, 'responses'] as const,
  recommendations: (id: Id) => ['sessions', id, 'recommendations'] as const,
  // The token is Access Data; it lives only in this in-memory cache key.
  invitation: (token: string) => ['invitation', token] as const,
  calendarConnection: ['calendar', 'connection'] as const,
  calendarSync: (id: Id) => ['sessions', id, 'calendar-sync'] as const,
}
