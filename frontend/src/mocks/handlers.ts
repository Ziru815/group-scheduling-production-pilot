/**
 * MSW request handlers: a mock of the FastAPI backend described in
 * docs/api-contract.md. Dev only.
 *
 * Rules the real backend must also follow, mirrored here:
 * - Every endpoint except the catch-all requires a signed-in user (401 otherwise).
 * - Organiser-only endpoints return 403 for other members.
 * - Non-members get 404 for a Session (its existence isn't leaked).
 * - Other participants' addresses and emails are never included (NFR-13).
 * - Invitation tokens only arrive in POST bodies and are never logged.
 */
import { delay, http, HttpResponse, type HttpResponseResolver, type PathParams } from 'msw'
import type {
  ActivityCategory,
  ApiErrorBody,
  ApiErrorCode,
  CalendarBusyResponse,
  CalendarConnection,
  ConfirmPlanRequest,
  CreateSessionRequest,
  CreateSessionResponse,
  InvitationLink,
  InvitationPreview,
  JoinSessionResponse,
  LocationInputType,
  LocationSearchRequest,
  LocationSearchResponse,
  Me,
  MyResponse,
  ResponseStatus,
  ResponseStatusList,
  SaveResponseRequest,
  SessionDetail,
  SessionListItem,
  UpdateSessionRequest,
} from '../api/types'
import { pageOrigin } from '../api/client'
import { TRANSPORT_MODES, TRAVEL_OBJECTIVES } from '../api/types'
import {
  DEFAULT_TIMEZONE,
  DURATION_MAX_MINUTES,
  DURATION_MIN_MINUTES,
  WEIGHT_STEP_PERCENT,
} from '../config'
import { datesInRange, isoDateInZone, localTimeToMinutes, toZonedIso, zonedToIso } from '../lib/time'
import { db, FAKE_HOMES, setCurrentUser, type MockParticipant, type MockSession, type MockUser } from './db'
import { generate, rank } from './recommend'

/** Artificial latency so loading states are visible. */
const MOCK_LATENCY_MS = 300

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fail(status: number, code: ApiErrorCode, message: string, fields?: Record<string, string>) {
  const body: ApiErrorBody = { error: { code, message, ...(fields ? { fields } : {}) } }
  return HttpResponse.json(body, { status })
}

const unauthenticated = () => fail(401, 'UNAUTHENTICATED', 'Please sign in to continue.')
const notFound = () => fail(404, 'NOT_FOUND', "We couldn't find that session.")
const forbidden = () => fail(403, 'FORBIDDEN', 'Only the organiser can do that.')
const validation = (fields: Record<string, string>) =>
  fail(422, 'VALIDATION_FAILED', 'Please fix the highlighted fields.', fields)

type Ctx = { user: MockUser; params: PathParams; request: Request }

/** Wraps a resolver with latency and the sign-in check. */
function authed(fn: (ctx: Ctx) => Response | Promise<Response>): HttpResponseResolver {
  return async ({ request, params }) => {
    await delay(MOCK_LATENCY_MS)
    const user = db.users.find((u) => u.id === db.currentUserId)
    if (!user) return unauthenticated()
    return fn({ user, params, request })
  }
}

async function readJson<T>(request: Request): Promise<Partial<T>> {
  try {
    return (await request.json()) as Partial<T>
  } catch {
    return {}
  }
}

const nowIso = (tz = DEFAULT_TIMEZONE) => toZonedIso(Date.now(), tz)
const displayName = (userId: string) => db.users.find((u) => u.id === userId)?.displayName ?? 'Unknown'
const activityType = (id: string) => {
  for (const c of db.activityCategories) {
    const t = c.types.find((type) => type.id === id)
    if (t) return { ...t, category: c.category }
  }
  return undefined
}

function membersOf(sessionId: string) {
  return db.participants.filter((p) => p.sessionId === sessionId)
}

function membership(sessionId: string, userId: string): MockParticipant | undefined {
  return db.participants.find((p) => p.sessionId === sessionId && p.userId === userId)
}

/** Loads a Session the user belongs to, or returns the error response to send. */
type Loaded =
  | { ok: false; error: Response }
  | { ok: true; session: MockSession; me: MockParticipant }

function loadForMember(id: unknown, user: MockUser): Loaded {
  const session = db.sessions.find((s) => s.id === String(id))
  const me = session && membership(session.id, user.id)
  if (!session || !me) return { ok: false, error: notFound() }
  return { ok: true, session, me }
}

function deadlinePassed(s: MockSession) {
  return Date.now() > new Date(s.responseDeadline).getTime()
}

/** Closed for responses: UC-05.AC.1, UC-07.EX.1. */
function isClosed(s: MockSession) {
  return s.status !== 'ACTIVE' || deadlinePassed(s)
}

function rangeStartIso(s: Pick<MockSession, 'startDate' | 'dailyStartTime' | 'timezone'>) {
  return zonedToIso(s.startDate, localTimeToMinutes(s.dailyStartTime), s.timezone)
}

function invitationUrl(s: MockSession) {
  return `${pageOrigin()}/join/${s.invitationToken}`
}

function newToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(18))
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

// ---------------------------------------------------------------------------
// DTO mappers (internal → public). Never spread internal objects into responses.
// ---------------------------------------------------------------------------

function toListItem(s: MockSession, me: MockParticipant): SessionListItem {
  const members = membersOf(s.id)
  return {
    id: s.id,
    name: s.name,
    activityTypeName: activityType(s.activityTypeId)?.name ?? '',
    organiserName: displayName(s.organiserUserId),
    status: s.status,
    myRole: me.role,
    myResponseStatus: me.responseStatus,
    responseDeadline: s.responseDeadline,
    timezone: s.timezone,
    submittedCount: members.filter((p) => p.responseStatus === 'SUBMITTED').length,
    participantCount: members.length,
    confirmed: s.confirmed
      ? { venueName: s.confirmed.venue.name, start: s.confirmed.start, end: s.confirmed.end }
      : null,
  }
}

function toDetail(s: MockSession, me: MockParticipant): SessionDetail {
  return {
    id: s.id,
    name: s.name,
    activityType: activityType(s.activityTypeId) ?? { id: s.activityTypeId, name: '', category: '' },
    organiserName: displayName(s.organiserUserId),
    status: s.status,
    myRole: me.role,
    myResponseStatus: me.responseStatus,
    startDate: s.startDate,
    endDate: s.endDate,
    dailyStartTime: s.dailyStartTime,
    dailyEndTime: s.dailyEndTime,
    timezone: s.timezone,
    durationMinutes: s.durationMinutes,
    responseDeadline: s.responseDeadline,
    minimumAttendees: s.minimumAttendees,
    travelObjective: s.travelObjective,
    attendanceWeightPercent: s.attendanceWeightPercent,
    isClosed: isClosed(s),
    recommendationsStale: s.recommendationsStale,
    hasRecommendations: s.recommendations !== null,
    confirmed: s.confirmed,
  }
}

function toMyResponse(p: MockParticipant): MyResponse {
  if (!p.record) return { participantId: p.id, responseStatus: p.responseStatus, record: null }
  // Explicit field list: coordinates stay on the server (data minimisation).
  const { recordStatus, submissionSource, transportMode, location, intervals, submittedAt, withdrawnAt } = p.record
  return {
    participantId: p.id,
    responseStatus: p.responseStatus,
    record: structuredClone({ recordStatus, submissionSource, transportMode, location, intervals, submittedAt, withdrawnAt }),
  }
}

function markStale(s: MockSession) {
  if (s.recommendations) s.recommendationsStale = true
}

// ---------------------------------------------------------------------------
// Validation (FR-A1.1, FR-A3.1 and the proposed daily window)
// ---------------------------------------------------------------------------

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/

function validateSession(s: Partial<CreateSessionRequest>, isCreate: boolean): Record<string, string> {
  const f: Record<string, string> = {}
  const tz = s.timezone ?? DEFAULT_TIMEZONE

  if (!s.name?.trim()) f.name = 'Give the session a name.'
  else if (s.name.trim().length > 80) f.name = 'Keep the name under 80 characters.'

  if (!s.activityTypeId || !activityType(s.activityTypeId)) f.activityTypeId = 'Choose an activity.'

  const validStart = !!s.startDate && DATE_RE.test(s.startDate)
  const validEnd = !!s.endDate && DATE_RE.test(s.endDate)
  if (!validStart) f.startDate = 'Choose a start date.'
  else if (isCreate && s.startDate! < isoDateInZone(nowIso(tz), tz)) f.startDate = 'Start date must be today or later.'
  if (!validEnd) f.endDate = 'Choose an end date.'
  else if (validStart && s.endDate! < s.startDate!) f.endDate = 'End date must be on or after the start date.'

  const validDayStart = !!s.dailyStartTime && TIME_RE.test(s.dailyStartTime)
  const validDayEnd = !!s.dailyEndTime && TIME_RE.test(s.dailyEndTime)
  if (!validDayStart) f.dailyStartTime = 'Choose the earliest start time.'
  if (!validDayEnd) f.dailyEndTime = 'Choose the latest end time.'
  else if (validDayStart && s.dailyEndTime! <= s.dailyStartTime!) f.dailyEndTime = 'Must be later than the earliest time.'

  const d = s.durationMinutes
  if (typeof d !== 'number' || !Number.isInteger(d) || d < DURATION_MIN_MINUTES || d > DURATION_MAX_MINUTES) {
    f.durationMinutes = `Duration must be a whole number from ${DURATION_MIN_MINUTES} to ${DURATION_MAX_MINUTES} minutes.`
  } else if (validDayStart && validDayEnd && !f.dailyEndTime) {
    const window = localTimeToMinutes(s.dailyEndTime!) - localTimeToMinutes(s.dailyStartTime!)
    if (d > window) f.durationMinutes = 'Duration is longer than the daily time window.'
  }

  const deadlineMs = s.responseDeadline ? new Date(s.responseDeadline).getTime() : NaN
  if (Number.isNaN(deadlineMs)) f.responseDeadline = 'Choose a response deadline.'
  else if (isCreate && deadlineMs <= Date.now()) f.responseDeadline = 'Deadline must be in the future.'
  else if (validStart && validDayStart) {
    const startMs = new Date(rangeStartIso({ startDate: s.startDate!, dailyStartTime: s.dailyStartTime!, timezone: tz })).getTime()
    if (deadlineMs >= startMs) f.responseDeadline = 'Deadline must be before the session date range starts.'
  }

  const m = s.minimumAttendees
  if (typeof m !== 'number' || !Number.isInteger(m) || m < 1) f.minimumAttendees = 'Enter at least 1.'

  return f
}

// ---------------------------------------------------------------------------
// Location search (mock OneMap via the backend)
// ---------------------------------------------------------------------------

function searchLocations(query: string): LocationSearchResponse {
  const q = query.trim().toLowerCase()
  const inputType: LocationInputType = /^\d{6}$/.test(q) ? 'POSTAL_CODE' : 'ADDRESS'

  // Dev triggers: "offline" simulates OneMap being down; "zzz" finds nothing.
  if (q.includes('offline')) return { status: 'UNAVAILABLE', inputType, candidates: [] }
  if (q.includes('zzz')) return { status: 'RECEIVED', inputType, candidates: [] }

  let matches =
    inputType === 'POSTAL_CODE'
      ? Object.values(FAKE_HOMES).filter((a) => a.postalCode === q)
      : Object.values(FAKE_HOMES).filter((a) => a.label.toLowerCase().includes(q))
  if (matches.length === 0) {
    // Unknown input: invent plausible matches placed around Jurong.
    matches =
      inputType === 'POSTAL_CODE'
        ? [{ label: `Blk ${q.slice(3)} Example Road, Singapore ${q}`, postalCode: q, lat: 1.345, lng: 103.72 }]
        : [
            { label: `${titleCase(query.trim())}, Singapore 640001`, postalCode: '640001', lat: 1.343, lng: 103.705 },
            { label: `${titleCase(query.trim())} (East), Singapore 609001`, postalCode: '609001', lat: 1.335, lng: 103.745 },
          ]
  }

  const candidates = matches.slice(0, 5).map((m) => {
    const candidateId = crypto.randomUUID()
    db.locationCandidates.set(candidateId, m)
    return { candidateId, label: m.label, postalCode: m.postalCode }
  })
  return { status: 'RECEIVED', inputType, candidates }
}

function titleCase(s: string) {
  return s.replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

export const handlers = [
  // --- UC-00 identity -------------------------------------------------------
  http.get(
    '*/api/me',
    authed(({ user }) => HttpResponse.json<Me>({ id: user.id, displayName: user.displayName, email: user.email })),
  ),

  http.post('*/api/auth/logout', async () => {
    await delay(MOCK_LATENCY_MS)
    setCurrentUser(null)
    return new HttpResponse(null, { status: 204 })
  }),

  // --- Dev-only, NOT part of the contract ----------------------------------
  // Real sign-in is a full-page redirect through Google, which a service
  // worker can't fake. These stand in for it and power the dev persona switcher.
  http.get('*/api/dev/users', async () => {
    await delay(MOCK_LATENCY_MS)
    const users = db.users.map((u) => {
      const organising = db.sessions.filter((s) => s.organiserUserId === u.id).map((s) => s.name)
      const joined = db.participants.filter((p) => p.userId === u.id && p.role === 'PARTICIPANT').length
      return {
        id: u.id,
        displayName: u.displayName,
        summary: [
          organising.length ? `Organises ${organising.join(', ')}` : 'Organises nothing',
          `${joined} other session${joined === 1 ? '' : 's'}`,
        ].join(' · '),
      }
    })
    return HttpResponse.json({ currentUserId: db.currentUserId, users })
  }),

  // Stands in for the Google Calendar consent redirect (contract #22).
  http.post(
    '*/api/dev/calendar/connect',
    authed(({ user }) => {
      user.calendar = 'CONNECTED'
      return new HttpResponse(null, { status: 204 })
    }),
  ),

  http.post('*/api/dev/sign-in', async ({ request }) => {
    await delay(MOCK_LATENCY_MS)
    const { userId } = await readJson<{ userId?: string }>(request)
    const user = db.users.find((u) => u.id === (userId ?? 'u-weijie'))
    if (!user) return fail(404, 'NOT_FOUND', 'No such mock user.')
    setCurrentUser(user.id)
    return new HttpResponse(null, { status: 204 })
  }),

  // --- Activity catalogue ---------------------------------------------------
  http.get(
    '*/api/activity-types',
    authed(() => HttpResponse.json<ActivityCategory[]>(db.activityCategories)),
  ),

  // --- Sessions (UC-01 to UC-04) ---------------------------------------------
  http.get(
    '*/api/sessions',
    authed(({ user }) => {
      const items = db.participants
        .filter((p) => p.userId === user.id)
        .map((me) => toListItem(db.sessions.find((s) => s.id === me.sessionId)!, me))
        .sort((a, b) => a.responseDeadline.localeCompare(b.responseDeadline))
      return HttpResponse.json<SessionListItem[]>(items)
    }),
  ),

  http.post(
    '*/api/sessions',
    authed(async ({ user, request }) => {
      const body = await readJson<CreateSessionRequest>(request)
      const fields = validateSession(body, true)
      if (Object.keys(fields).length) return validation(fields)

      const session: MockSession = {
        id: crypto.randomUUID(),
        name: body.name!.trim(),
        activityTypeId: body.activityTypeId!,
        organiserUserId: user.id,
        startDate: body.startDate!,
        endDate: body.endDate!,
        dailyStartTime: body.dailyStartTime!,
        dailyEndTime: body.dailyEndTime!,
        timezone: body.timezone ?? DEFAULT_TIMEZONE,
        durationMinutes: body.durationMinutes!,
        responseDeadline: body.responseDeadline!,
        minimumAttendees: body.minimumAttendees!,
        travelObjective: 'MIN_TOTAL',
        attendanceWeightPercent: 50,
        status: 'ACTIVE',
        invitationToken: newToken(),
        recommendations: null,
        recommendationsStale: false,
        confirmed: null,
      }
      const me: MockParticipant = {
        id: crypto.randomUUID(),
        sessionId: session.id,
        userId: user.id,
        role: 'ORGANISER',
        responseStatus: 'NOT_SUBMITTED',
        record: null,
        updatedAt: null,
      }
      db.sessions.push(session)
      db.participants.push(me)
      return HttpResponse.json<CreateSessionResponse>(
        { session: toDetail(session, me), invitationUrl: invitationUrl(session) },
        { status: 201 },
      )
    }),
  ),

  http.get(
    '*/api/sessions/:id',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      return HttpResponse.json<SessionDetail>(toDetail(r.session, r.me))
    }),
  ),

  http.patch(
    '*/api/sessions/:id',
    authed(async ({ user, params, request }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      const { session, me } = r
      if (me.role !== 'ORGANISER') return forbidden()
      if (session.status !== 'ACTIVE') return fail(409, 'SESSION_CLOSED', 'This session can no longer be changed.')

      const body = await readJson<UpdateSessionRequest>(request)
      const fields: Record<string, string> = {}

      if (body.travelObjective !== undefined && !TRAVEL_OBJECTIVES.includes(body.travelObjective)) {
        fields.travelObjective = 'Choose a travel objective.'
      }
      if (body.attendanceWeightPercent !== undefined) {
        const w = body.attendanceWeightPercent
        if (typeof w !== 'number' || w < 0 || w > 100) fields.attendanceWeightPercent = 'Weighting must be 0–100%.'
      }

      const settingKeys = [
        'name', 'startDate', 'endDate', 'dailyStartTime', 'dailyEndTime',
        'durationMinutes', 'responseDeadline', 'minimumAttendees',
      ] as const
      const changesSettings = settingKeys.some((k) => body[k] !== undefined && body[k] !== session[k])
      if (changesSettings) {
        const merged: Partial<CreateSessionRequest> = { ...session, ...pick(body, settingKeys) }
        Object.assign(fields, validateSession(merged, false))
      }
      // UC-02.EX.1: invalid changes leave the Session untouched.
      if (Object.keys(fields).length) return validation(fields)

      Object.assign(session, pick(body, settingKeys))
      if (body.travelObjective) session.travelObjective = body.travelObjective
      if (body.attendanceWeightPercent !== undefined) {
        // FR-D9.1: snap to the nearest 10%.
        session.attendanceWeightPercent =
          Math.round(body.attendanceWeightPercent / WEIGHT_STEP_PERCENT) * WEIGHT_STEP_PERCENT
      }
      // UC-02 step 5. Objective/weighting changes only re-rank (FR-D9), so they don't outdate results.
      const affectsResults = (['startDate', 'endDate', 'dailyStartTime', 'dailyEndTime', 'durationMinutes', 'minimumAttendees'] as const)
        .some((k) => body[k] !== undefined)
      if (affectsResults) markStale(session)

      return HttpResponse.json<SessionDetail>(toDetail(session, me))
    }),
  ),

  http.post(
    '*/api/sessions/:id/cancel',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      if (r.me.role !== 'ORGANISER') return forbidden()
      if (r.session.status !== 'ACTIVE') {
        return fail(409, 'SESSION_CLOSED', 'Only an active session can be cancelled.')
      }
      r.session.status = 'CANCELLED'
      return HttpResponse.json<SessionDetail>(toDetail(r.session, r.me))
    }),
  ),

  http.get(
    '*/api/sessions/:id/invitation',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      if (r.me.role !== 'ORGANISER') return forbidden()
      return HttpResponse.json<InvitationLink>({ invitationUrl: invitationUrl(r.session) })
    }),
  ),

  // --- Invitations (UC-05) ----------------------------------------------------
  http.post(
    '*/api/invitations/resolve',
    authed(async ({ user, request }) => {
      const { token } = await readJson<{ token: string }>(request)
      const session = db.sessions.find((s) => s.invitationToken === token)
      if (!session) return fail(404, 'INVITATION_INVALID', "This invitation link isn't valid. Ask the organiser for a new one.")
      return HttpResponse.json<InvitationPreview>({
        sessionId: session.id,
        name: session.name,
        activityTypeName: activityType(session.activityTypeId)?.name ?? '',
        organiserName: displayName(session.organiserUserId),
        status: session.status,
        startDate: session.startDate,
        endDate: session.endDate,
        timezone: session.timezone,
        responseDeadline: session.responseDeadline,
        isClosed: isClosed(session),
        alreadyJoined: Boolean(membership(session.id, user.id)),
      })
    }),
  ),

  http.post(
    '*/api/invitations/join',
    authed(async ({ user, request }) => {
      const { token } = await readJson<{ token: string }>(request)
      const session = db.sessions.find((s) => s.invitationToken === token)
      if (!session) return fail(404, 'INVITATION_INVALID', "This invitation link isn't valid. Ask the organiser for a new one.")

      const existing = membership(session.id, user.id)
      if (existing) return HttpResponse.json<JoinSessionResponse>({ sessionId: session.id, participantId: existing.id })
      if (isClosed(session)) return fail(409, 'SESSION_CLOSED', 'This session is no longer accepting responses.')

      const p: MockParticipant = {
        id: crypto.randomUUID(),
        sessionId: session.id,
        userId: user.id,
        role: 'PARTICIPANT',
        responseStatus: 'NOT_SUBMITTED',
        record: null,
        updatedAt: null,
      }
      db.participants.push(p)
      return HttpResponse.json<JoinSessionResponse>({ sessionId: session.id, participantId: p.id })
    }),
  ),

  // --- My response (UC-06 to UC-08) -------------------------------------------
  http.get(
    '*/api/sessions/:id/my-response',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      return HttpResponse.json<MyResponse>(toMyResponse(r.me))
    }),
  ),

  http.put(
    '*/api/sessions/:id/my-response',
    authed(async ({ user, params, request }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      const { session, me } = r
      if (isClosed(session)) return fail(409, 'SESSION_CLOSED', 'Responses for this session are closed.')

      const body = await readJson<SaveResponseRequest>(request)
      const fields: Record<string, string> = {}

      const intervals = Array.isArray(body.intervals) ? body.intervals : []
      const dates = new Set(datesInRange(session.startDate, session.endDate))
      const dayStart = localTimeToMinutes(session.dailyStartTime)
      const dayEnd = localTimeToMinutes(session.dailyEndTime)
      // Each interval must sit inside one day's window within the date range.
      const outside = intervals.some((i) => {
        const s = new Date(i.start).getTime()
        const e = new Date(i.end).getTime()
        if (Number.isNaN(s) || Number.isNaN(e) || s >= e) return true
        const date = isoDateInZone(i.start, session.timezone)
        if (!dates.has(date)) return true
        const windowStart = new Date(zonedToIso(date, dayStart, session.timezone)).getTime()
        const windowEnd = new Date(zonedToIso(date, dayEnd, session.timezone)).getTime()
        return s < windowStart || e > windowEnd
      })
      if (outside) fields.intervals = "Some selected times are outside this session's dates and hours."
      else if (intervals.length === 0 && !body.confirmUnavailable) {
        fields.intervals = "Select the times you're free, or confirm that you're unavailable."
      }

      if (!body.transportMode || !TRANSPORT_MODES.includes(body.transportMode)) {
        fields.transportMode = 'Choose how you would travel.'
      }

      // `location` may be omitted on an edit to keep the saved one (contract #14).
      const keepLocation = !body.location && me.record !== null
      const candidate = body.location?.candidateId ? db.locationCandidates.get(body.location.candidateId) : undefined
      if (!keepLocation) {
        if (!body.location?.input?.trim()) fields.location = 'Enter your home address or postal code.'
        else if (!candidate) fields.location = 'Search for your address and pick a match from the list.'
      }

      if (Object.keys(fields).length) return validation(fields)

      const at = nowIso(session.timezone)
      const previous = me.record
      me.record = {
        coords: keepLocation ? previous!.coords : { lat: candidate!.lat, lng: candidate!.lng },
        recordStatus: 'ACTIVE',
        submissionSource: body.calendarAssisted ? 'CALENDAR_ASSISTED' : 'MANUAL',
        transportMode: body.transportMode!,
        location: keepLocation
          ? previous!.location
          : {
              inputType: body.location!.inputType ?? 'ADDRESS',
              input: body.location!.input!.trim(),
              label: candidate!.label,
              geocodeStatus: 'VALID',
            },
        intervals: intervals.map((i) => ({ start: i.start, end: i.end, type: 'AVAILABLE', source: 'MANUAL' })),
        submittedAt: at,
        withdrawnAt: null,
      }
      me.responseStatus = 'SUBMITTED'
      me.updatedAt = at
      markStale(session) // UC-07 step 5
      return HttpResponse.json<MyResponse>(toMyResponse(me))
    }),
  ),

  http.post(
    '*/api/sessions/:id/my-response/withdraw',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      const { session, me } = r
      if (isClosed(session)) return fail(409, 'SESSION_CLOSED', 'Responses for this session are closed.')
      if (!me.record || me.responseStatus !== 'SUBMITTED') {
        return fail(409, 'VALIDATION_FAILED', "You haven't submitted a response to withdraw.")
      }
      const at = nowIso(session.timezone)
      me.record.recordStatus = 'WITHDRAWN'
      me.record.withdrawnAt = at
      me.responseStatus = 'WITHDRAWN'
      me.updatedAt = at
      markStale(session)
      return HttpResponse.json<MyResponse>(toMyResponse(me))
    }),
  ),

  http.post(
    '*/api/locations/search',
    authed(async ({ request }) => {
      const { query } = await readJson<LocationSearchRequest>(request)
      if (!query?.trim()) return validation({ query: 'Enter an address or postal code.' })
      return HttpResponse.json<LocationSearchResponse>(searchLocations(query))
    }),
  ),

  // --- Response status (UC-03) ----------------------------------------------
  http.get(
    '*/api/sessions/:id/responses',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      if (r.me.role !== 'ORGANISER') return forbidden()
      const members = membersOf(r.session.id)
      const counts: Record<ResponseStatus, number> = { NOT_SUBMITTED: 0, SUBMITTED: 0, WITHDRAWN: 0 }
      members.forEach((p) => counts[p.responseStatus]++)
      return HttpResponse.json<ResponseStatusList>({
        participants: members.map((p) => ({
          participantId: p.id,
          displayName: displayName(p.userId),
          role: p.role,
          responseStatus: p.responseStatus,
          updatedAt: p.updatedAt,
        })),
        counts,
        refreshedAt: nowIso(r.session.timezone),
      })
    }),
  ),

  // --- Recommendations (UC-09 to UC-12) --------------------------------------
  http.get(
    '*/api/sessions/:id/recommendations',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      if (!r.session.recommendations) return fail(404, 'NOT_FOUND', 'No recommendations have been generated yet.')
      return HttpResponse.json(rank(db, r.session, r.session.recommendations))
    }),
  ),

  http.post(
    '*/api/sessions/:id/recommendations',
    authed(async ({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      if (r.me.role !== 'ORGANISER') return forbidden()
      if (r.session.status !== 'ACTIVE') return fail(409, 'SESSION_CLOSED', 'This session is no longer active.')
      await delay(700) // generation is slower than a normal read

      const result = generate(db, r.session)
      if (!result.ok) {
        return result.code === 'NO_RESPONSES'
          ? fail(409, 'NO_RESPONSES', 'No one has submitted their availability yet.')
          : fail(409, 'NO_FEASIBLE_TIMESLOT',
              'No time slot has enough people available. Lower the minimum attendees or wait for more responses.')
      }
      r.session.recommendations = result.set
      r.session.recommendationsStale = false
      return HttpResponse.json(rank(db, r.session, result.set))
    }),
  ),

  http.post(
    '*/api/sessions/:id/confirm',
    authed(async ({ user, params, request }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      const { session, me } = r
      if (me.role !== 'ORGANISER') return forbidden()
      if (session.status !== 'ACTIVE') return fail(409, 'SESSION_CLOSED', 'This session is no longer active.')
      if (!session.recommendations || session.recommendationsStale) {
        return fail(409, 'RECOMMENDATIONS_STALE', 'The options are out of date. Generate them again before confirming.')
      }

      const { combinationId } = await readJson<ConfirmPlanRequest>(request)
      const chosen = rank(db, session, session.recommendations).combinations.find((c) => c.combinationId === combinationId)
      if (!chosen || chosen.feasibilityStatus !== 'FEASIBLE') {
        return fail(409, 'COMBINATION_NOT_FEASIBLE', 'That option can no longer be confirmed.')
      }

      session.status = 'CONFIRMED'
      session.confirmed = {
        combinationId: chosen.combinationId,
        venue: chosen.venue,
        start: chosen.start,
        end: chosen.end,
        attendees: chosen.attendees.map((a) => ({ participantId: a.participantId, displayName: a.displayName })),
        confirmedAt: nowIso(session.timezone),
      }
      return HttpResponse.json<SessionDetail>(toDetail(session, me))
    }),
  ),

  // --- Google Calendar (FR-B8) ---------------------------------------------
  http.get(
    '*/api/calendar/connection',
    authed(({ user }) => HttpResponse.json<CalendarConnection>({ status: user.calendar })),
  ),

  http.delete(
    '*/api/calendar/connection',
    authed(({ user }) => {
      user.calendar = 'DISCONNECTED'
      return new HttpResponse(null, { status: 204 })
    }),
  ),

  http.post(
    '*/api/sessions/:id/calendar-busy',
    authed(({ user, params }) => {
      const r = loadForMember(params.id, user)
      if (!r.ok) return r.error
      if (user.calendar !== 'CONNECTED') {
        return fail(409, 'CALENDAR_NOT_CONNECTED', 'Connect Google Calendar first.')
      }
      const { session } = r
      const dayStart = localTimeToMinutes(session.dailyStartTime)
      // Free/busy only: start and end times, nothing else (NFR-14).
      const busy = datesInRange(session.startDate, session.endDate).map((date, i) => ({
        start: zonedToIso(date, dayStart + 60 + (i % 2) * 120, session.timezone),
        end: zonedToIso(date, dayStart + 150 + (i % 2) * 120, session.timezone),
      }))
      return HttpResponse.json<CalendarBusyResponse>({ status: 'RECEIVED', busy })
    }),
  ),

  // --- Catch-all: anything under /api not mocked yet -------------------------
  http.all('*/api/*', () =>
    fail(501, 'NOT_MOCKED', 'This endpoint has no mock yet. Add one in src/mocks/handlers.ts.'),
  ),
]

function pick<T extends object, K extends keyof T>(obj: T, keys: readonly K[]): Partial<Pick<T, K>> {
  const out: Partial<Pick<T, K>> = {}
  for (const k of keys) if (obj[k] !== undefined) out[k] = obj[k]
  return out
}

// ---------------------------------------------------------------------------
// Seed derived state: results for Weekend badminton, and the confirmed plan
// for Sunday football.
// ---------------------------------------------------------------------------

function bootstrap() {
  const badminton = db.sessions.find((s) => s.id === 's-badminton')!
  const bad = generate(db, badminton)
  if (bad.ok) badminton.recommendations = bad.set

  const football = db.sessions.find((s) => s.id === 's-football')!
  const foot = generate(db, football)
  if (foot.ok) {
    football.recommendations = foot.set
    const top = rank(db, football, foot.set).combinations.find((c) => c.feasibilityStatus === 'FEASIBLE')
    if (!top) console.warn('[mocks] Seed problem: Sunday football has no feasible option to confirm.')
    if (top) {
      football.confirmed = {
        combinationId: top.combinationId,
        venue: top.venue,
        start: top.start,
        end: top.end,
        attendees: top.attendees.map((a) => ({ participantId: a.participantId, displayName: a.displayName })),
        confirmedAt: zonedToIso('2026-10-15', 20 * 60, football.timezone),
      }
    }
  }
}

bootstrap()
