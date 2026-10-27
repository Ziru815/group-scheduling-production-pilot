import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, isApiError } from '../client'
import { queryKeys } from '../queryKeys'
import type { ConfirmPlanRequest, Id, RecommendationSet, SessionDetail } from '../types'

/**
 * UC-11. Resolves to null when nothing has been generated yet (404), so pages
 * can show "Generate" instead of an error.
 */
export function useRecommendations(sessionId: Id | undefined) {
  return useQuery({
    queryKey: queryKeys.recommendations(sessionId ?? ''),
    queryFn: async () => {
      try {
        return await api.get<RecommendationSet>(`/api/sessions/${sessionId}/recommendations`)
      } catch (error) {
        if (isApiError(error) && error.status === 404) return null
        throw error
      }
    },
    enabled: Boolean(sessionId),
  })
}

/** UC-09 (and UC-10 on the backend). Organiser only. */
export function useGenerateRecommendations(sessionId: Id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<RecommendationSet>(`/api/sessions/${sessionId}/recommendations`),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.recommendations(sessionId), data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId), exact: true })
    },
  })
}

/** UC-12 (FR-E4). Organiser only. */
export function useConfirmPlan(sessionId: Id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ConfirmPlanRequest) =>
      api.post<SessionDetail>(`/api/sessions/${sessionId}/confirm`, body),
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.session(sessionId), session)
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions, exact: true })
    },
  })
}
