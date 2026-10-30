/**
 * A toy stand-in for the backend's Candidate Generation + Feasibility and
 * Scoring engine (SRS §4.3–4.4), so the results screens have believable data.
 * NOT the real algorithm: thresholds and formulas here are placeholders for
 * TBD-1, TBD-2, TBD-9 and TBD-15.
 */
import type {
  Absentee,
  AttendanceStatus,
  ExclusionReason,
  Id,
  IsoDateTime,
  RankedCombination,
  RecommendationSet,
  RoutingStatus,
  TransportMode,
} from '../api/types'
import { SLOT_MINUTES } from '../config'
import { datesInRange, localTimeToMinutes, toZonedIso, zonedToIso } from '../lib/time'
import type { MockDb, MockParticipant, MockSession } from './db'

/** Mock value for TBD-1 (maximum individual journey time). */
const MOCK_MAX_JOURNEY_MINUTES = 60
/** Mock value for TBD-2 (shortlist size N). */
const MOCK_SHORTLIST_N = 5
/** How many ranked options the results screen gets. */
const TOP_K = 10

interface MockTravel {
  participantId: Id
  transportMode: TransportMode
  minutes: number | null
  routingStatus: RoutingStatus
}

export interface MockCombination {
  combinationId: Id
  venueId: Id
  start: IsoDateTime
  end: IsoDateTime
  attendeeIds: Id[]
  travel: MockTravel[]
  dataUnavailable: boolean
}

export interface MockRecommendationSet {
  generatedAt: IsoDateTime
  combinations: MockCombination[]
  excludedCounts: Partial<Record<ExclusionReason, number>>
}

export type GenerateResult =
  | { ok: true; set: MockRecommendationSet }
  | { ok: false; code: 'NO_RESPONSES' | 'NO_FEASIBLE_TIMESLOT' }

/** Straight-line distance in km (haversine). */
function km(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLng = (b.lng - a.lng) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(h))
}

/** Fake "routing" result: distance-based minutes per mode. The real one comes from OneMap (UC-10). */
function mockTravel(p: MockParticipant, venue: { id: Id; latitude: number; longitude: number }): MockTravel {
  const mode = p.record!.transportMode
  // Simulate one routing failure so the "unavailable" state (NFR-3) can be seen.
  if (mode === 'PUBLIC_TRANSPORT' && venue.id === 'v-gombak-hall') {
    return { participantId: p.id, transportMode: mode, minutes: null, routingStatus: 'UNAVAILABLE' }
  }
  const d = km(p.record!.coords, { lat: venue.latitude, lng: venue.longitude }) * 1.3 // road factor
  const minutes = mode === 'WALK' ? d * 12 : mode === 'DRIVE' ? 5 + d * 1.8 : 10 + d * 3.5
  return { participantId: p.id, transportMode: mode, minutes: Math.max(3, Math.round(minutes)), routingStatus: 'AVAILABLE' }
}

function covers(p: MockParticipant, startMs: number, endMs: number): boolean {
  const intervals = (p.record?.intervals ?? [])
    .filter((i) => i.type === 'AVAILABLE')
    .map((i) => [new Date(i.start).getTime(), new Date(i.end).getTime()] as const)
    .sort((a, b) => a[0] - b[0])
  let reached = startMs
  for (const [s, e] of intervals) {
    if (s > reached) break
    reached = Math.max(reached, e)
    if (reached >= endMs) return true
  }
  return false
}

function activeRespondents(db: MockDb, session: MockSession): MockParticipant[] {
  return db.participants.filter(
    (p) => p.sessionId === session.id && p.responseStatus === 'SUBMITTED' && p.record?.recordStatus === 'ACTIVE',
  )
}

/** UC-09 steps 2–4 and UC-10. */
export function generate(db: MockDb, session: MockSession): GenerateResult {
  const respondents = activeRespondents(db, session)
  if (respondents.length === 0) return { ok: false, code: 'NO_RESPONSES' }

  const venues = db.venues
    .filter((v) => v.activityTypeIds.includes(session.activityTypeId))
    .slice(0, MOCK_SHORTLIST_N)

  const excludedCounts: Partial<Record<ExclusionReason, number>> = {}
  const bump = (r: ExclusionReason, n = 1) => (excludedCounts[r] = (excludedCounts[r] ?? 0) + n)

  const dayStart = localTimeToMinutes(session.dailyStartTime)
  const dayEnd = localTimeToMinutes(session.dailyEndTime)
  const combinations: MockCombination[] = []
  let anyTimeslotQualifies = false
  // Mock-only: consecutive starts with the same venue, day and attendees are
  // near-duplicates, so keep the earliest to keep the results list readable.
  const seen = new Set<string>()

  for (const date of datesInRange(session.startDate, session.endDate)) {
    for (let m = dayStart; m + session.durationMinutes <= dayEnd; m += SLOT_MINUTES) {
      const start = zonedToIso(date, m, session.timezone)
      const startMs = new Date(start).getTime()
      const endMs = startMs + session.durationMinutes * 60_000
      const attendees = respondents.filter((p) => covers(p, startMs, endMs))

      if (attendees.length < session.minimumAttendees) {
        bump('BELOW_THRESHOLD', venues.length)
        continue
      }
      anyTimeslotQualifies = true
      const groupKey = `${date}|${attendees.map((p) => p.id).sort().join(',')}`

      for (const venue of venues) {
        const key = `${venue.id}|${groupKey}`
        if (seen.has(key)) continue
        const travel = attendees.map((p) => mockTravel(p, venue))
        if (travel.some((t) => t.minutes !== null && t.minutes > MOCK_MAX_JOURNEY_MINUTES)) {
          bump('JOURNEY_LIMIT')
          continue
        }
        seen.add(key)
        combinations.push({
          combinationId: `c-${session.id}-${venue.id}-${startMs}`,
          venueId: venue.id,
          start,
          end: toZonedIso(endMs, session.timezone),
          attendeeIds: attendees.map((p) => p.id),
          travel,
          dataUnavailable: travel.some((t) => t.routingStatus !== 'AVAILABLE'),
        })
      }
    }
  }

  if (!anyTimeslotQualifies) return { ok: false, code: 'NO_FEASIBLE_TIMESLOT' }

  return {
    ok: true,
    set: { generatedAt: toZonedIso(Date.now(), session.timezone), combinations, excludedCounts },
  }
}

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)))

/**
 * FR-D7 to FR-D10: score and rank under the Session's current objective and
 * weighting. Re-run on every read so a weighting change re-ranks instantly
 * without re-routing.
 */
export function rank(db: MockDb, session: MockSession, set: MockRecommendationSet): RecommendationSet {
  const respondents = activeRespondents(db, session).length || 1
  const members = db.participants.filter((p) => p.sessionId === session.id)
  const nameOf = (participantId: Id) => {
    const p = members.find((m) => m.id === participantId)
    return db.users.find((u) => u.id === p?.userId)?.displayName ?? 'Unknown'
  }
  const w = session.attendanceWeightPercent

  const scored: RankedCombination[] = set.combinations.map((c) => {
    const venue = db.venues.find((v) => v.id === c.venueId)!
    const minutes = c.travel.flatMap((t) => (t.minutes === null ? [] : [t.minutes]))
    const total = minutes.reduce((a, b) => a + b, 0)
    const avg = minutes.length ? total / minutes.length : 0
    const max = minutes.length ? Math.max(...minutes) : 0

    const attendanceScore = clamp((100 * c.attendeeIds.length) / respondents)
    const travelScore =
      session.travelObjective === 'MIN_TOTAL' ? clamp(100 - (avg - 5) * 2) : clamp(100 - (max - 5) * 1.6)
    const combinedScore = clamp((w * attendanceScore + (100 - w) * travelScore) / 100)

    const absentees: Absentee[] = members
      .filter((p) => !c.attendeeIds.includes(p.id))
      .map((p) => ({
        participantId: p.id,
        displayName: nameOf(p.id),
        attendanceStatus: absenceStatus(p),
      }))

    const travelPart =
      session.travelObjective === 'MIN_TOTAL'
        ? `average trip ${Math.round(avg)} min`
        : `longest trip ${max} min`

    return {
      combinationId: c.combinationId,
      rank: 0,
      venue: {
        id: venue.id,
        name: venue.name,
        category: venue.category,
        address: venue.address,
        meetingPoint: venue.meetingPoint,
        latitude: venue.latitude,
        longitude: venue.longitude,
        dataSource: venue.dataSource,
        lastUpdated: venue.lastUpdated,
      },
      start: c.start,
      end: c.end,
      feasibilityStatus: c.dataUnavailable ? 'DATA_UNAVAILABLE' : 'FEASIBLE',
      attendeeCount: c.attendeeIds.length,
      meetsRequestedMinimum: c.attendeeIds.length >= session.minimumAttendees,
      combinedScore,
      attendanceScore,
      travelScore,
      totalTravelMinutes: c.dataUnavailable ? null : total,
      averageTravelMinutes: c.dataUnavailable ? null : Math.round(avg),
      maxTravelMinutes: c.dataUnavailable ? null : max,
      explanation: `${c.attendeeIds.length} of ${respondents} respondents can make it; ${travelPart}${
        c.dataUnavailable ? ' (some travel times unavailable)' : ''
      }.`,
      attendees: c.travel.map((t) => ({
        participantId: t.participantId,
        displayName: nameOf(t.participantId),
        transportMode: t.transportMode,
        travelMinutes: t.minutes,
        routingStatus: t.routingStatus,
      })),
      absentees,
    }
  })

  // Feasible before data-unavailable; then score; then shorter longest trip and
  // earlier start as a MOCK tie-break (the real rule is TBD-9).
  scored.sort(
    (a, b) =>
      Number(a.feasibilityStatus === 'DATA_UNAVAILABLE') - Number(b.feasibilityStatus === 'DATA_UNAVAILABLE') ||
      b.combinedScore - a.combinedScore ||
      (a.maxTravelMinutes ?? Infinity) - (b.maxTravelMinutes ?? Infinity) ||
      a.start.localeCompare(b.start),
  )

  return {
    sessionId: session.id,
    generatedAt: set.generatedAt,
    stale: session.recommendationsStale,
    travelObjective: session.travelObjective,
    attendanceWeightPercent: w,
    minimumAttendees: session.minimumAttendees,
    isNearMatch: false,
    combinations: scored.slice(0, TOP_K).map((c, i) => ({ ...c, rank: i + 1 })),
    excludedCounts: set.excludedCounts,
  }
}

function absenceStatus(p: MockParticipant): Exclude<AttendanceStatus, 'AVAILABLE'> {
  if (p.responseStatus === 'WITHDRAWN') return 'WITHDRAWN'
  if (p.responseStatus === 'NOT_SUBMITTED') return 'NO_RESPONSE'
  return 'UNAVAILABLE'
}
