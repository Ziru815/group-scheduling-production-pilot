/**
 * New session form model (UC-01, FR-A1 to FR-A4). Field names match
 * CreateSessionRequest so server 422 `fields` map straight onto the inputs.
 * These checks mirror the backend's; the backend stays the authority.
 */
import type { CreateSessionRequest, SessionDetail, UpdateSessionRequest } from '../api/types'
import { DURATION_MAX_MINUTES, DURATION_MIN_MINUTES } from '../config'
import { isoToLocalDateTime, localDateTimeToIso, localTimeToMinutes, todayInZone, zonedToIso } from '../lib/time'

export interface NewSessionForm {
  name: string
  /** UI only: which category's types are shown. Not sent. */
  category: string
  activityTypeId: string
  startDate: string
  endDate: string
  /** PROPOSED field (api-contract.md, open question 9). */
  dailyStartTime: string
  dailyEndTime: string
  /** Strings so partially typed input isn't coerced. */
  durationMinutes: string
  /** "YYYY-MM-DDTHH:mm" wall-clock in the Session timezone. */
  responseDeadline: string
  minimumAttendees: string
}

export type NewSessionField = Exclude<keyof NewSessionForm, 'category'>
export type NewSessionErrors = Partial<Record<NewSessionField, string>>

/** Order of fields on screen, used to focus the first error. */
export const FIELD_ORDER: NewSessionField[] = [
  'name',
  'activityTypeId',
  'startDate',
  'endDate',
  'dailyStartTime',
  'dailyEndTime',
  'durationMinutes',
  'responseDeadline',
  'minimumAttendees',
]

export const EMPTY_FORM: NewSessionForm = {
  name: '',
  category: '',
  activityTypeId: '',
  startDate: '',
  endDate: '',
  dailyStartTime: '09:00',
  dailyEndTime: '21:00',
  durationMinutes: '',
  responseDeadline: '',
  minimumAttendees: '',
}

const WHOLE_NUMBER = /^\d+$/

/**
 * @param original For UC-02 edits: the saved values. Unchanged fields skip the
 *   "today or later" / "in the future" checks, so an organiser can still edit
 *   other details after, say, the deadline has passed.
 */
export function validateNewSession(form: NewSessionForm, timeZone: string, original?: NewSessionForm): NewSessionErrors {
  const e: NewSessionErrors = {}
  const changed = (f: NewSessionField) => !original || form[f] !== original[f]

  const name = form.name.trim()
  if (!name) e.name = 'Give the session a name.'
  else if (name.length > 80) e.name = 'Keep the name under 80 characters.'

  if (!form.activityTypeId) e.activityTypeId = 'Choose an activity.'

  if (!form.startDate) e.startDate = 'Choose a start date.'
  else if (changed('startDate') && form.startDate < todayInZone(timeZone)) e.startDate = 'Start date must be today or later.'

  if (!form.endDate) e.endDate = 'Choose an end date.'
  else if (form.startDate && form.endDate < form.startDate) e.endDate = 'Must be on or after the start date.'

  if (!form.dailyStartTime) e.dailyStartTime = 'Choose the earliest start time.'
  if (!form.dailyEndTime) e.dailyEndTime = 'Choose the latest end time.'
  else if (form.dailyStartTime && form.dailyEndTime <= form.dailyStartTime) {
    e.dailyEndTime = 'Must be later than the earliest time.'
  }

  // FR-A1.1
  const duration = Number(form.durationMinutes)
  if (!form.durationMinutes.trim()) e.durationMinutes = 'Enter a duration in minutes.'
  else if (!WHOLE_NUMBER.test(form.durationMinutes.trim()) || duration < DURATION_MIN_MINUTES || duration > DURATION_MAX_MINUTES) {
    e.durationMinutes = `Duration must be a whole number from ${DURATION_MIN_MINUTES} to ${DURATION_MAX_MINUTES} minutes.`
  } else if (!e.dailyEndTime && form.dailyStartTime && form.dailyEndTime) {
    const window = localTimeToMinutes(form.dailyEndTime) - localTimeToMinutes(form.dailyStartTime)
    if (duration > window) e.durationMinutes = 'Longer than the daily time window above.'
  }

  // FR-A3, FR-A3.1
  const deadline = localDateTimeToIso(form.responseDeadline, timeZone)
  if (!deadline) e.responseDeadline = 'Choose a response deadline.'
  else if (changed('responseDeadline') && new Date(deadline).getTime() <= Date.now()) e.responseDeadline = 'Deadline must be in the future.'
  else if (form.startDate && form.dailyStartTime) {
    const rangeStart = zonedToIso(form.startDate, localTimeToMinutes(form.dailyStartTime), timeZone)
    if (new Date(deadline).getTime() >= new Date(rangeStart).getTime()) {
      e.responseDeadline = 'Deadline must be before the session date range starts.'
    }
  }

  // FR-A4 (no default yet: TBD-2)
  const min = form.minimumAttendees.trim()
  if (!min) e.minimumAttendees = 'Enter how many people you need.'
  else if (!WHOLE_NUMBER.test(min) || Number(min) < 1) e.minimumAttendees = 'Enter a whole number, at least 1.'

  return e
}

/** Only call after validateNewSession returned no errors. */
export function toCreateRequest(form: NewSessionForm, timeZone: string): CreateSessionRequest {
  return {
    name: form.name.trim(),
    activityTypeId: form.activityTypeId,
    startDate: form.startDate,
    endDate: form.endDate,
    dailyStartTime: form.dailyStartTime,
    dailyEndTime: form.dailyEndTime,
    timezone: timeZone,
    durationMinutes: Number(form.durationMinutes),
    responseDeadline: localDateTimeToIso(form.responseDeadline, timeZone)!,
    minimumAttendees: Number(form.minimumAttendees),
  }
}

/** UC-02: an existing Session as form values (times in the Session's timezone). */
export function formFromSession(s: SessionDetail): NewSessionForm {
  return {
    name: s.name,
    category: s.activityType.category,
    activityTypeId: s.activityType.id,
    startDate: s.startDate,
    endDate: s.endDate,
    dailyStartTime: s.dailyStartTime,
    dailyEndTime: s.dailyEndTime,
    durationMinutes: String(s.durationMinutes),
    responseDeadline: isoToLocalDateTime(s.responseDeadline, s.timezone),
    minimumAttendees: String(s.minimumAttendees),
  }
}

/** UC-02: only the fields that changed (activity type isn't editable). */
export function toUpdateRequest(form: NewSessionForm, original: NewSessionForm, timeZone: string): UpdateSessionRequest {
  const full = toCreateRequest(form, timeZone)
  const out: UpdateSessionRequest = {}
  if (form.name.trim() !== original.name) out.name = full.name
  if (form.startDate !== original.startDate) out.startDate = full.startDate
  if (form.endDate !== original.endDate) out.endDate = full.endDate
  if (form.dailyStartTime !== original.dailyStartTime) out.dailyStartTime = full.dailyStartTime
  if (form.dailyEndTime !== original.dailyEndTime) out.dailyEndTime = full.dailyEndTime
  if (form.durationMinutes.trim() !== original.durationMinutes) out.durationMinutes = full.durationMinutes
  if (form.responseDeadline !== original.responseDeadline) out.responseDeadline = full.responseDeadline
  if (form.minimumAttendees.trim() !== original.minimumAttendees) out.minimumAttendees = full.minimumAttendees
  return out
}

/** Keeps only server field errors that belong to a field on this form. */
export function pickFieldErrors(fields: Record<string, string>): NewSessionErrors {
  const out: NewSessionErrors = {}
  for (const f of FIELD_ORDER) if (fields[f]) out[f] = fields[f]
  return out
}
