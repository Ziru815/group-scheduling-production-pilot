/**
 * Grouping rules for "Your sessions" (SRS §3.1). The SRS names three groups;
 * "Waiting" and "Cancelled" are added so every Session has a home
 * (api-contract.md, open question 6).
 */
import type { SessionListItem } from '../api/types'

export type SessionGroup = 'needsResponse' | 'organising' | 'waiting' | 'confirmed' | 'cancelled'

export const GROUP_ORDER: SessionGroup[] = ['needsResponse', 'organising', 'waiting', 'confirmed', 'cancelled']

export const GROUP_TITLES: Record<SessionGroup, string> = {
  needsResponse: 'Needs your response',
  organising: 'Organising',
  waiting: 'Waiting on others',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
}

export function deadlinePassed(s: SessionListItem, now = Date.now()): boolean {
  return now > new Date(s.responseDeadline).getTime()
}

export function groupOf(s: SessionListItem, now = Date.now()): SessionGroup {
  if (s.status === 'CANCELLED') return 'cancelled'
  if (s.status === 'CONFIRMED') return 'confirmed'
  if (s.myRole === 'ORGANISER') return 'organising'
  if (!deadlinePassed(s, now) && s.myResponseStatus !== 'SUBMITTED') return 'needsResponse'
  return 'waiting'
}

/** Where tapping a card goes. */
export function destinationOf(s: SessionListItem, now = Date.now()): string {
  switch (groupOf(s, now)) {
    case 'confirmed':
      return `/sessions/${s.id}/confirmed`
    case 'organising':
      return `/sessions/${s.id}/status`
    default:
      return `/sessions/${s.id}/availability`
  }
}

export function groupSessions(list: SessionListItem[], now = Date.now()) {
  const groups = new Map<SessionGroup, SessionListItem[]>()
  for (const s of list) {
    const g = groupOf(s, now)
    groups.set(g, [...(groups.get(g) ?? []), s])
  }
  for (const [g, items] of groups) {
    items.sort((a, b) =>
      g === 'confirmed' && a.confirmed && b.confirmed
        ? a.confirmed.start.localeCompare(b.confirmed.start)
        : a.responseDeadline.localeCompare(b.responseDeadline),
    )
  }
  return GROUP_ORDER.filter((g) => groups.has(g)).map((g) => ({ group: g, items: groups.get(g)! }))
}
