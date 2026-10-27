/**
 * API types shared by the client, the hooks and the MSW mocks.
 *
 * Enums come from SRS Appendix B.3 / Appendix D. Shapes are the wire format
 * agreed in docs/api-contract.md: JSON with camelCase keys, IDs as opaque
 * strings (UUIDs), and date-times as ISO 8601 strings WITH an offset
 * (e.g. "2026-11-07T09:00:00+08:00"). Always display times in the Session's
 * `timezone`, never the browser's.
 *
 * Privacy (NFR-13, §5.5): types describing OTHER participants deliberately
 * have no address, coordinates or email fields. Only `MyResponse` carries the
 * caller's own starting location.
 */

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** UUID or other opaque identifier issued by the backend. */
export type Id = string
/** ISO 8601 date-time with offset, e.g. "2026-11-07T09:00:00+08:00". */
export type IsoDateTime = string
/** Calendar date in the Session's timezone, "YYYY-MM-DD". */
export type IsoDate = string
/** Wall-clock time in the Session's timezone, "HH:mm" (24h). */
export type LocalTime = string
/** IANA timezone name, e.g. "Asia/Singapore". */
export type TimeZone = string

// ---------------------------------------------------------------------------
// Enums (SRS Appendix B.3 / D)
// ---------------------------------------------------------------------------

export const SESSION_STATUSES = ['ACTIVE', 'CONFIRMED', 'CANCELLED'] as const
export type SessionStatus = (typeof SESSION_STATUSES)[number]

export const PARTICIPANT_ROLES = ['ORGANISER', 'PARTICIPANT'] as const
export type ParticipantRole = (typeof PARTICIPANT_ROLES)[number]

export const RESPONSE_STATUSES = ['NOT_SUBMITTED', 'SUBMITTED', 'WITHDRAWN'] as const
export type ResponseStatus = (typeof RESPONSE_STATUSES)[number]

export const TRANSPORT_MODES = ['WALK', 'DRIVE', 'PUBLIC_TRANSPORT'] as const
export type TransportMode = (typeof TRANSPORT_MODES)[number]

export const LOCATION_INPUT_TYPES = ['ADDRESS', 'POSTAL_CODE'] as const
export type LocationInputType = (typeof LOCATION_INPUT_TYPES)[number]

export const GEOCODE_STATUSES = ['PENDING', 'VALID', 'INVALID', 'UNAVAILABLE'] as const
export type GeocodeStatus = (typeof GEOCODE_STATUSES)[number]

export const SUBMISSION_SOURCES = ['MANUAL', 'CALENDAR_ASSISTED'] as const
export type SubmissionSource = (typeof SUBMISSION_SOURCES)[number]

export const RECORD_STATUSES = ['ACTIVE', 'WITHDRAWN'] as const
export type RecordStatus = (typeof RECORD_STATUSES)[number]

export const INTERVAL_TYPES = ['AVAILABLE', 'BUSY'] as const
export type IntervalType = (typeof INTERVAL_TYPES)[number]

export const INTERVAL_SOURCES = ['MANUAL', 'GOOGLE_CALENDAR'] as const
export type IntervalSource = (typeof INTERVAL_SOURCES)[number]

export const VENUE_CATEGORIES = ['SPORTS_FACILITY', 'PARK', 'MALL'] as const
export type VenueCategory = (typeof VENUE_CATEGORIES)[number]

export const TRAVEL_OBJECTIVES = ['MIN_TOTAL', 'MIN_MAX_INDIVIDUAL'] as const
export type TravelObjective = (typeof TRAVEL_OBJECTIVES)[number]

export const FEASIBILITY_STATUSES = ['PENDING', 'FEASIBLE', 'EXCLUDED', 'DATA_UNAVAILABLE'] as const
export type FeasibilityStatus = (typeof FEASIBILITY_STATUSES)[number]

export const EXCLUSION_REASONS = [
  'BELOW_THRESHOLD',
  'JOURNEY_LIMIT',
  'GROUP_SIZE',
  'BOOKING_LEAD_TIME',
] as const
export type ExclusionReason = (typeof EXCLUSION_REASONS)[number]

export const ROUTING_STATUSES = ['AVAILABLE', 'UNAVAILABLE', 'ERROR'] as const
export type RoutingStatus = (typeof ROUTING_STATUSES)[number]

export const ATTENDANCE_STATUSES = ['AVAILABLE', 'UNAVAILABLE', 'NO_RESPONSE', 'WITHDRAWN'] as const
export type AttendanceStatus = (typeof ATTENDANCE_STATUSES)[number]

export const CALENDAR_CONNECTION_STATUSES = [
  'CONNECTED',
  'DISCONNECTED',
  'DECLINED',
  'EXPIRED',
  'ERROR',
] as const
export type CalendarConnectionStatus = (typeof CALENDAR_CONNECTION_STATUSES)[number]

/** Outcome of a call the backend made to an external provider (NFR-3). */
export const EXTERNAL_SERVICE_STATUSES = ['RECEIVED', 'UNAVAILABLE', 'ERROR'] as const
export type ExternalServiceStatus = (typeof EXTERNAL_SERVICE_STATUSES)[number]

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/** Machine-readable error codes the backend returns in `error.code`. */
export type ApiErrorCode =
  | 'UNAUTHENTICATED' // 401: no valid session cookie
  | 'FORBIDDEN' // 403: signed in but not allowed (e.g. not the Organiser)
  | 'NOT_FOUND' // 404
  | 'INVITATION_INVALID' // 404: unknown or revoked invitation token (UC-05.EX.1)
  | 'VALIDATION_FAILED' // 422: see `fields`
  | 'SESSION_CLOSED' // 409: deadline passed, cancelled or confirmed
  | 'NO_RESPONSES' // 409: UC-09 precondition, no valid response yet
  | 'NO_FEASIBLE_TIMESLOT' // 409: UC-09.AC.1
  | 'RECOMMENDATIONS_STALE' // 409: confirm attempted on outdated results
  | 'COMBINATION_NOT_FEASIBLE' // 409
  | 'CALENDAR_NOT_CONNECTED' // 409
  | 'EXTERNAL_SERVICE_UNAVAILABLE' // 503: provider down; client may retry (NFR-3)
  | 'NOT_MOCKED' // 501: only returned by the MSW catch-all
  | 'NETWORK_ERROR' // client-side: request never reached the server
  | 'UNKNOWN'

/** Error body for every non-2xx JSON response. */
export interface ApiErrorBody {
  error: {
    code: ApiErrorCode
    message: string
    /** Field-level messages for inline validation, keyed by request field name. */
    fields?: Record<string, string>
  }
}

// ---------------------------------------------------------------------------
// UC-00: identity
// ---------------------------------------------------------------------------

/** The signed-in User Account (B.3.3). Only ever returned to its owner. */
export interface Me {
  id: Id
  displayName: string
  /** Shown only to the owner (e.g. on Profile); never to other users. */
  email: string
}

// ---------------------------------------------------------------------------
// Activity catalogue (FR-A1)
// ---------------------------------------------------------------------------

export interface ActivityType {
  id: Id
  name: string
}

export interface ActivityCategory {
  category: string
  types: ActivityType[]
}

// ---------------------------------------------------------------------------
// Sessions (UC-01 to UC-04)
// ---------------------------------------------------------------------------

/** Public Venue information (§5.5 "Public / External Data"). */
export interface VenueSummary {
  id: Id
  name: string
  category: VenueCategory
  address: string
  latitude: number
  longitude: number
}

/** The Organiser's final choice (FR-E4, FR-E5). */
export interface ConfirmedPlan {
  combinationId: Id
  venue: VenueSummary
  start: IsoDateTime
  end: IsoDateTime
  /** Display names only (FR-E3, NFR-13). */
  attendees: { participantId: Id; displayName: string }[]
  confirmedAt: IsoDateTime
}

/** One row on "Your sessions" (§3.1). */
export interface SessionListItem {
  id: Id
  name: string
  activityTypeName: string
  organiserName: string
  status: SessionStatus
  myRole: ParticipantRole
  myResponseStatus: ResponseStatus
  responseDeadline: IsoDateTime
  timezone: TimeZone
  /** Counts for the Organiser's "5 of 8 responded" badge. */
  submittedCount: number
  participantCount: number
  /** Present only when status is CONFIRMED. */
  confirmed: { venueName: string; start: IsoDateTime; end: IsoDateTime } | null
}

/** A Session as seen by one of its members (B.3.2). */
export interface SessionDetail {
  id: Id
  name: string
  activityType: ActivityType & { category: string }
  organiserName: string
  status: SessionStatus
  myRole: ParticipantRole
  myResponseStatus: ResponseStatus
  /** First and last day of the date range, in `timezone`. */
  startDate: IsoDate
  endDate: IsoDate
  /**
   * PROPOSED (not in SRS): daily window the availability grid covers, in
   * `timezone`. Keeps the grid usable at 375px. See api-contract.md, open question 9.
   */
  dailyStartTime: LocalTime
  dailyEndTime: LocalTime
  timezone: TimeZone
  durationMinutes: number
  responseDeadline: IsoDateTime
  minimumAttendees: number
  travelObjective: TravelObjective
  /** 0–100 in steps of 10; travel weight is 100 minus this (FR-D9.1). */
  attendanceWeightPercent: number
  /** True once the deadline passed or the Session left ACTIVE. */
  isClosed: boolean
  /** True when results exist but inputs changed since (UC-02, UC-07, UC-11.AC.1). */
  recommendationsStale: boolean
  hasRecommendations: boolean
  confirmed: ConfirmedPlan | null
}

export interface CreateSessionRequest {
  name: string
  activityTypeId: Id
  startDate: IsoDate
  endDate: IsoDate
  dailyStartTime: LocalTime
  dailyEndTime: LocalTime
  /** Optional; the backend defaults to Asia/Singapore. */
  timezone?: TimeZone
  durationMinutes: number
  responseDeadline: IsoDateTime
  minimumAttendees: number
}

export interface CreateSessionResponse {
  session: SessionDetail
  /** Full invitation URL for the Organiser to share. Access Data: never log it. */
  invitationUrl: string
}

/** UC-02 edits plus the Organiser's scoring controls (FR-D6, FR-D9). All optional. */
export type UpdateSessionRequest = Partial<
  Pick<
    CreateSessionRequest,
    | 'name'
    | 'startDate'
    | 'endDate'
    | 'dailyStartTime'
    | 'dailyEndTime'
    | 'durationMinutes'
    | 'responseDeadline'
    | 'minimumAttendees'
  > & {
    travelObjective: TravelObjective
    attendanceWeightPercent: number
  }
>

export interface InvitationLink {
  invitationUrl: string
}

// ---------------------------------------------------------------------------
// Invitations (UC-05)
// ---------------------------------------------------------------------------

/** What a signed-in invitee sees before joining. */
export interface InvitationPreview {
  sessionId: Id
  name: string
  activityTypeName: string
  organiserName: string
  status: SessionStatus
  startDate: IsoDate
  endDate: IsoDate
  timezone: TimeZone
  responseDeadline: IsoDateTime
  isClosed: boolean
  alreadyJoined: boolean
}

export interface JoinSessionResponse {
  sessionId: Id
  participantId: Id
}

// ---------------------------------------------------------------------------
// My response (UC-06 to UC-08)
// ---------------------------------------------------------------------------

export interface TimeInterval {
  start: IsoDateTime
  end: IsoDateTime
}

export interface AvailabilityInterval extends TimeInterval {
  type: IntervalType
  source: IntervalSource
}

/** The caller's own starting location. Never returned for anyone else (NFR-13). */
export interface MyLocation {
  inputType: LocationInputType
  /** What the participant typed. */
  input: string
  /** The match they picked, e.g. "Blk 123 Jurong West St 41, Singapore 640123". */
  label: string | null
  geocodeStatus: GeocodeStatus
}

export interface MyResponse {
  participantId: Id
  responseStatus: ResponseStatus
  /** Null until the first submission. */
  record: {
    recordStatus: RecordStatus
    submissionSource: SubmissionSource
    transportMode: TransportMode
    location: MyLocation
    intervals: AvailabilityInterval[]
    submittedAt: IsoDateTime
    withdrawnAt: IsoDateTime | null
  } | null
}

export interface SaveResponseRequest {
  /** AVAILABLE intervals the participant marked (MANUAL source). */
  intervals: TimeInterval[]
  /** True when the grid was prefilled from Google Calendar (FR-B8). */
  calendarAssisted: boolean
  transportMode: TransportMode
  /**
   * Required on the first submission. On an edit, omit it to keep the saved
   * location (the participant didn't change it).
   */
  location?: {
    inputType: LocationInputType
    input: string
    /** `candidateId` from POST /api/locations/search. */
    candidateId: Id
  }
  /** UC-06.AC.1: must be true to submit with no intervals selected. */
  confirmUnavailable?: boolean
}

export interface LocationSearchRequest {
  query: string
}

export interface LocationCandidate {
  /** Opaque, short-lived handle the backend uses to look up the geocoded point. */
  candidateId: Id
  label: string
  postalCode: string | null
}

export interface LocationSearchResponse {
  /** UNAVAILABLE when OneMap could not be reached (UC-08.EX.1). */
  status: ExternalServiceStatus
  inputType: LocationInputType
  candidates: LocationCandidate[]
}

// ---------------------------------------------------------------------------
// Response status (UC-03, FR-B7)
// ---------------------------------------------------------------------------

/** Another participant as the Organiser sees them. No address, no email. */
export interface ParticipantSummary {
  participantId: Id
  displayName: string
  role: ParticipantRole
  responseStatus: ResponseStatus
  updatedAt: IsoDateTime | null
}

export interface ResponseStatusList {
  participants: ParticipantSummary[]
  counts: Record<ResponseStatus, number>
  refreshedAt: IsoDateTime
}

// ---------------------------------------------------------------------------
// Recommendations (UC-09 to UC-12)
// ---------------------------------------------------------------------------

export interface AttendeeTravel {
  participantId: Id
  displayName: string
  transportMode: TransportMode
  /** Null when routing failed; show "unavailable" in place (NFR-3). */
  travelMinutes: number | null
  routingStatus: RoutingStatus
}

export interface Absentee {
  participantId: Id
  displayName: string
  attendanceStatus: Exclude<AttendanceStatus, 'AVAILABLE'>
}

export interface RankedCombination {
  combinationId: Id
  rank: number
  venue: VenueSummary
  start: IsoDateTime
  end: IsoDateTime
  feasibilityStatus: Extract<FeasibilityStatus, 'FEASIBLE' | 'DATA_UNAVAILABLE'>
  attendeeCount: number
  /** False for a labelled best-available option below the requested minimum. */
  meetsRequestedMinimum: boolean
  /** 0–100. */
  combinedScore: number
  attendanceScore: number
  travelScore: number
  /** Null when any attendee's travel time is unavailable. */
  totalTravelMinutes: number | null
  averageTravelMinutes: number | null
  maxTravelMinutes: number | null
  /** Short plain-language reason for the score (UC-11 step 4). */
  explanation: string
  attendees: AttendeeTravel[]
  absentees: Absentee[]
}

export interface RecommendationSet {
  sessionId: Id
  generatedAt: IsoDateTime
  /** True when Session inputs changed after generation (UC-11.AC.1). */
  stale: boolean
  travelObjective: TravelObjective
  attendanceWeightPercent: number
  /** The organiser's requested attendance threshold. */
  minimumAttendees: number
  /** True when no slot reached the threshold and best-available options are shown. */
  isNearMatch: boolean
  /** Feasible (or data-unavailable) combinations, best first. */
  combinations: RankedCombination[]
  /** How many were excluded, by reason; for an explanatory note only. */
  excludedCounts: Partial<Record<ExclusionReason, number>>
}

export interface ConfirmPlanRequest {
  combinationId: Id
}

// ---------------------------------------------------------------------------
// Google Calendar (FR-B8, FR-B8.1)
// ---------------------------------------------------------------------------

export interface CalendarConnection {
  status: CalendarConnectionStatus
}

export interface CalendarBusyResponse {
  status: ExternalServiceStatus
  /** Free/busy only: no titles, descriptions or attendees (NFR-14). */
  busy: TimeInterval[]
}
