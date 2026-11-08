import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, redirectToBackend } from '../client'
import { queryKeys } from '../queryKeys'
import type { CalendarBusyResponse, CalendarConnection, CalendarSyncSummary, Id } from '../types'

export function useCalendarConnection() {
  return useQuery({
    queryKey: queryKeys.calendarConnection,
    queryFn: () => api.get<CalendarConnection>('/api/calendar/connection'),
  })
}

/**
 * FR-B8: connect Google Calendar (a separate grant from sign-in).
 * Real backend: full-page redirect through Google's consent screen, returning
 * to `returnPath` (+ `?calendar=declined` if refused). The mutation never
 * settles because the page navigates away. `returnPath` must never contain an
 * invitation token. Mock backend (dev): connects instantly.
 */
export function useConnectCalendar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (returnPath: string) => {
      if (__MOCKS_ENABLED__) {
        await api.post<void>('/api/dev/calendar/connect')
        return
      }
      redirectToBackend('/api/calendar/google/connect', returnPath)
      await new Promise<never>(() => {})
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.calendarConnection }),
  })
}

export function useDisconnectCalendar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.delete('/api/calendar/connection'),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.calendarConnection })
    },
  })
}

/** FR-B8: busy blocks inside this Session's date range, to prefill the grid. */
export function useImportCalendarBusy(sessionId: Id) {
  return useMutation({
    mutationFn: () => api.post<CalendarBusyResponse>(`/api/sessions/${sessionId}/calendar-busy`),
  })
}

/** Retry only the caller's permitted scope: all members for an organiser, self otherwise. */
export function useRetryCalendarSync(sessionId: Id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: queryKeys.calendarSync(sessionId),
    mutationFn: () => api.post<CalendarSyncSummary>(`/api/sessions/${sessionId}/calendar-sync`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId) })
    },
  })
}
