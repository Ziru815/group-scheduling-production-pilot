import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { queryKeys } from '../queryKeys'
import type {
  Id,
  LocationSearchRequest,
  LocationSearchResponse,
  MyResponse,
  SaveResponseRequest,
} from '../types'

/** The caller's own response, including their private starting location. */
export function useMyResponse(sessionId: Id | undefined) {
  return useQuery({
    queryKey: queryKeys.myResponse(sessionId ?? ''),
    queryFn: () => api.get<MyResponse>(`/api/sessions/${sessionId}/my-response`),
    enabled: Boolean(sessionId),
  })
}

/** UC-06 submit and UC-07 edit (FR-B1, FR-B2, FR-B4, FR-B5). */
export function useSaveResponse(sessionId: Id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: SaveResponseRequest) =>
      api.put<MyResponse>(`/api/sessions/${sessionId}/my-response`, body),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.myResponse(sessionId), data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions, exact: true })
    },
  })
}

/** UC-07.AC.1 (FR-B6). */
export function useWithdrawResponse(sessionId: Id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<MyResponse>(`/api/sessions/${sessionId}/my-response/withdraw`),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.myResponse(sessionId), data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions, exact: true })
    },
  })
}

/**
 * UC-08 steps 1–3: the backend geocodes via OneMap and returns matches to
 * pick from. POST, so the address never appears in a URL or access log.
 */
export function useLocationSearch() {
  return useMutation({
    mutationFn: (body: LocationSearchRequest) =>
      api.post<LocationSearchResponse>('/api/locations/search', body),
  })
}
