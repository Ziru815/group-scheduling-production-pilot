import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import { queryKeys } from '../queryKeys'
import type { ActivityCategory } from '../types'

/** Activity categories and types for the New session chips (FR-A1). */
export function useActivityTypes() {
  return useQuery({
    queryKey: queryKeys.activityTypes,
    queryFn: () => api.get<ActivityCategory[]>('/api/activity-types'),
    staleTime: Infinity,
  })
}
