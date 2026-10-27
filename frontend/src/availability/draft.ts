/**
 * Keeps unsaved grid selections across the Google Calendar consent redirect
 * (a full-page round trip). Only times and transport mode are stored, never
 * the address, and only in this tab's sessionStorage.
 */
import type { TransportMode } from '../api/types'

const key = (sessionId: string) => `availability-draft.${sessionId}`

export interface AvailabilityDraft {
  slots: string[]
  transportMode: TransportMode | ''
}

export function saveDraft(sessionId: string, draft: AvailabilityDraft) {
  try {
    sessionStorage.setItem(key(sessionId), JSON.stringify(draft))
  } catch {
    // Storage blocked: selections are lost on redirect, nothing worse.
  }
}

/** Reads without removing (safe inside React state initialisers). */
export function peekDraft(sessionId: string): AvailabilityDraft | null {
  try {
    const raw = sessionStorage.getItem(key(sessionId))
    return raw ? (JSON.parse(raw) as AvailabilityDraft) : null
  } catch {
    return null
  }
}

export function clearDraft(sessionId: string) {
  try {
    sessionStorage.removeItem(key(sessionId))
  } catch {
    // ignore
  }
}
