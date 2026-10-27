import type { IsoDate, IsoDateTime, LocalTime, TimeZone } from '../api/types'

/**
 * Time helpers. Every function takes the Session's timezone explicitly:
 * times are always shown in the Session's timezone, never the browser's
 * (SRS §6). Built on Intl only, no date library.
 */

const LOCALE = 'en-SG'

const formatterCache = new Map<string, Intl.DateTimeFormat>()

function formatter(timeZone: TimeZone, options: Intl.DateTimeFormatOptions) {
  const key = timeZone + JSON.stringify(options)
  let f = formatterCache.get(key)
  if (!f) {
    f = new Intl.DateTimeFormat(LOCALE, { timeZone, ...options })
    formatterCache.set(key, f)
  }
  return f
}

/** "Sat 7 Nov" */
export function formatDate(iso: IsoDateTime, timeZone: TimeZone): string {
  return formatter(timeZone, { weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(iso))
}

/** "4:00 pm" */
export function formatTime(iso: IsoDateTime, timeZone: TimeZone): string {
  return formatter(timeZone, { hour: 'numeric', minute: '2-digit', hour12: true }).format(new Date(iso))
}

/** "Sat 7 Nov, 4:00 pm" */
export function formatDateTime(iso: IsoDateTime, timeZone: TimeZone): string {
  return `${formatDate(iso, timeZone)}, ${formatTime(iso, timeZone)}`
}

/** "Sat 7 Nov, 4:00 pm – 5:30 pm" (assumes same day, as Session durations are ≤ 8h). */
export function formatTimeRange(start: IsoDateTime, end: IsoDateTime, timeZone: TimeZone): string {
  return `${formatDate(start, timeZone)}, ${formatTime(start, timeZone)} – ${formatTime(end, timeZone)}`
}

/** Label for a plain calendar date ("YYYY-MM-DD"), which has no timezone of its own: "Sat 7 Nov". */
export function formatIsoDate(date: IsoDate): string {
  return formatter('UTC', { weekday: 'short', day: 'numeric', month: 'short' }).format(
    new Date(`${date}T12:00:00Z`),
  )
}

/** Inclusive list of calendar dates from start to end. */
export function datesInRange(start: IsoDate, end: IsoDate): IsoDate[] {
  const out: IsoDate[] = []
  const cursor = new Date(`${start}T00:00:00Z`)
  const last = new Date(`${end}T00:00:00Z`)
  while (cursor <= last) {
    out.push(cursor.toISOString().slice(0, 10))
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  }
  return out
}

/** "HH:mm" → minutes after midnight. */
export function localTimeToMinutes(time: LocalTime): number {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

/** Offset of `timeZone` from UTC at instant `utcMs`, in minutes (e.g. +480 for Singapore). */
function offsetMinutes(timeZone: TimeZone, utcMs: number): number {
  const parts = formatter(timeZone, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(utcMs))
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value)
  const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  return Math.round((asUtc - utcMs) / 60_000)
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

/** Formats an instant as ISO 8601 with the zone's offset: "2026-11-07T09:00:00+08:00". */
export function toZonedIso(utcMs: number, timeZone: TimeZone): IsoDateTime {
  const offset = offsetMinutes(timeZone, utcMs)
  const local = new Date(utcMs + offset * 60_000)
  const sign = offset >= 0 ? '+' : '-'
  const abs = Math.abs(offset)
  return (
    `${local.getUTCFullYear()}-${pad(local.getUTCMonth() + 1)}-${pad(local.getUTCDate())}` +
    `T${pad(local.getUTCHours())}:${pad(local.getUTCMinutes())}:${pad(local.getUTCSeconds())}` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  )
}

/**
 * Wall-clock date + minutes-after-midnight in `timeZone` → ISO with offset.
 * Used by the availability grid to turn a cell into an interval boundary.
 */
export function zonedToIso(date: IsoDate, minutes: number, timeZone: TimeZone): IsoDateTime {
  const [y, mo, d] = date.split('-').map(Number)
  const wallAsUtc = Date.UTC(y, mo - 1, d, 0, minutes)
  // Two passes handle DST edges in zones that have them (Singapore doesn't).
  let utc = wallAsUtc - offsetMinutes(timeZone, wallAsUtc) * 60_000
  utc = wallAsUtc - offsetMinutes(timeZone, utc) * 60_000
  return toZonedIso(utc, timeZone)
}

/** The calendar date of an instant, in `timeZone`. */
export function isoDateInZone(iso: IsoDateTime, timeZone: TimeZone): IsoDate {
  return toZonedIso(new Date(iso).getTime(), timeZone).slice(0, 10)
}

/** Today's date in `timeZone`. */
export function todayInZone(timeZone: TimeZone): IsoDate {
  return toZonedIso(Date.now(), timeZone).slice(0, 10)
}

/** Now as "YYYY-MM-DDTHH:mm" in `timeZone`, the format <input type="datetime-local"> uses. */
export function nowLocalDateTime(timeZone: TimeZone): string {
  return toZonedIso(Date.now(), timeZone).slice(0, 16)
}

/**
 * Value from <input type="datetime-local"> ("YYYY-MM-DDTHH:mm"), read as wall-clock
 * time in `timeZone` (not the browser's) → ISO with offset. Null if malformed.
 */
export function localDateTimeToIso(value: string, timeZone: TimeZone): IsoDateTime | null {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})$/.exec(value)
  if (!m) return null
  return zonedToIso(m[1], Number(m[2]) * 60 + Number(m[3]), timeZone)
}

/** Human name for a timezone, e.g. "Singapore time". */
export function timeZoneLabel(timeZone: TimeZone): string {
  if (timeZone === 'Asia/Singapore') return 'Singapore time'
  return timeZone.replace(/_/g, ' ')
}

/** ISO instant → "YYYY-MM-DDTHH:mm" wall-clock in `timeZone`, for <input type="datetime-local">. */
export function isoToLocalDateTime(iso: IsoDateTime, timeZone: TimeZone): string {
  return toZonedIso(new Date(iso).getTime(), timeZone).slice(0, 16)
}
