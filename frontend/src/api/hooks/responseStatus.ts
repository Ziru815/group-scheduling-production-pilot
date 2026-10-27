import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import { queryKeys } from '../queryKeys'
import type { Id, ResponseStatusList } from '../types'

/** UC-03 (FR-B7). Organiser only. `refetch()` backs the Refresh control. */
export function useResponseStatus(sessionId: Id | undefined) {
  return useQuery({
    queryKey: queryKeys.responseStatus(sessionId ?? ''),
    queryFn: () => api.get<ResponseStatusList>(`/api/sessions/${sessionId}/responses`),
    enabled: Boolean(sessionId),
  })
}
