import type { Absentee, TransportMode, TravelObjective } from '../api/types'

export const TRANSPORT_LABELS: Record<TransportMode, string> = {
  WALK: 'Walk',
  DRIVE: 'Drive',
  PUBLIC_TRANSPORT: 'Public transport',
}

export const OBJECTIVE_LABELS: Record<TravelObjective, string> = {
  MIN_TOTAL: 'Minimise total travel',
  MIN_MAX_INDIVIDUAL: 'Minimise longest trip',
}

/** NO_RESPONSE and WITHDRAWN stay distinct from UNAVAILABLE (§5.5). */
export const ABSENCE_LABELS: Record<Absentee['attendanceStatus'], string> = {
  UNAVAILABLE: "Can't make it",
  NO_RESPONSE: "Hasn't responded",
  WITHDRAWN: 'Withdrew',
}
