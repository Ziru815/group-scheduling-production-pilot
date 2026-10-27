import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { queryKeys } from '../queryKeys'
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  Id,
  InvitationLink,
  SessionDetail,
  SessionListItem,
  UpdateSessionRequest,
} from '../types'

/** Your sessions (§3.1). Grouping by state is done in the page. */
export function useSessions() {
  return useQuery({
    queryKey: queryKeys.sessions,
    queryFn: () => api.get<SessionListItem[]>('/api/sessions'),
  })
}

export function useSession(id: Id | undefined) {
  return useQuery({
    queryKey: queryKeys.session(id ?? ''),
    queryFn: () => api.get<SessionDetail>(`/api/sessions/${id}`),
    enabled: Boolean(id),
  })
}

/** UC-01. */
export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateSessionRequest) =>
      api.post<CreateSessionResponse>('/api/sessions', body),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.session(data.session.id), data.session)
      queryClient.setQueryData(queryKeys.invitationLink(data.session.id), {
        invitationUrl: data.invitationUrl,
      })
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions, exact: true })
    },
  })
}

/** UC-02, plus the Organiser's travel objective and weighting (FR-D6, FR-D9). */
export function useUpdateSession(id: Id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateSessionRequest) =>
      api.patch<SessionDetail>(`/api/sessions/${id}`, body),
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.session(id), session)
      void queryClient.invalidateQueries({ queryKey: queryKeys.recommendations(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions, exact: true })
    },
  })
}

/** UC-04. */
export function useCancelSession(id: Id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<SessionDetail>(`/api/sessions/${id}/cancel`),
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.session(id), session)
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions, exact: true })
    },
  })
}

/** Organiser only: the shareable link (FR-A2). Access Data: never log it. */
export function useInvitationLink(id: Id | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.invitationLink(id ?? ''),
    queryFn: () => api.get<InvitationLink>(`/api/sessions/${id}/invitation`),
    enabled: Boolean(id) && enabled,
    staleTime: Infinity,
  })
}
