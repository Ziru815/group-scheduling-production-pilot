import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { queryKeys } from '../queryKeys'
import type { InvitationPreview, JoinSessionResponse } from '../types'

/*
 * The invitation token is sent in a POST body, never in an API URL, so it
 * stays out of server access logs (SRS §3.4, §5.5). Never log it client-side.
 */

/** UC-05 steps 2–3: check the link and show the Session before joining. */
export function useInvitation(token: string | undefined) {
  return useQuery({
    queryKey: queryKeys.invitation(token ?? ''),
    queryFn: () => api.post<InvitationPreview>('/api/invitations/resolve', { token }),
    enabled: Boolean(token),
    retry: false,
  })
}

/** UC-05 step 5. Idempotent: joining twice returns the same participant. */
export function useJoinSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (token: string) =>
      api.post<JoinSessionResponse>('/api/invitations/join', { token }),
    onSuccess: (_data, token) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions })
      // The cached preview still says alreadyJoined: false.
      void queryClient.invalidateQueries({ queryKey: queryKeys.invitation(token) })
    },
  })
}
