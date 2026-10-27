/**
 * Availability grid model. Rows are SLOT_MINUTES-long cells between the
 * Session's daily start and end time; columns are the dates in its range.
 * Everything is computed in the Session's timezone, never the browser's.
 */
import type { IsoDate, SessionDetail, TimeInterval, TimeZone } from '../api/types'
import { SLOT_MINUTES } from '../config'
import { datesInRange, localTimeToMinutes, zonedToIso } from '../lib/time'

export interface GridModel {
  timeZone: TimeZone
  dates: IsoDate[]
  /** Minutes after midnight (Session timezone) at which each row starts. */
  rowMinutes: number[]
  /** bounds[day][row] = [startMs, endMs] for that cell. */
  bounds: [number, number][][]
}

/** Cell key: "day:row". */
export type SlotKey = string
export const slotKey = (day: number, row: number): SlotKey => `${day}:${row}`
export function parseSlotKey(key: SlotKey): [number, number] {
  const [d, r] = key.split(':').map(Number)
  return [d, r]
}

export function buildGrid(
  s: Pick<SessionDetail, 'startDate' | 'endDate' | 'dailyStartTime' | 'dailyEndTime' | 'timezone'>,
): GridModel {
  const dates = datesInRange(s.startDate, s.endDate)
  const start = localTimeToMinutes(s.dailyStartTime)
  const end = localTimeToMinutes(s.dailyEndTime)
  const rowMinutes: number[] = []
  for (let m = start; m + SLOT_MINUTES <= end; m += SLOT_MINUTES) rowMinutes.push(m)

  const bounds = dates.map((date) =>
    rowMinutes.map((m): [number, number] => [
      new Date(zonedToIso(date, m, s.timezone)).getTime(),
      new Date(zonedToIso(date, m + SLOT_MINUTES, s.timezone)).getTime(),
    ]),
  )
  return { timeZone: s.timezone, dates, rowMinutes, bounds }
}

function toMs(intervals: TimeInterval[]): [number, number][] {
  return intervals.map((i) => [new Date(i.start).getTime(), new Date(i.end).getTime()])
}

/** Cells fully covered by an interval: used for saved AVAILABLE intervals. */
export function coveredSlots(grid: GridModel, intervals: TimeInterval[]): Set<SlotKey> {
  const ms = toMs(intervals)
  const out = new Set<SlotKey>()
  grid.bounds.forEach((day, d) =>
    day.forEach(([s, e], r) => {
      if (ms.some(([is, ie]) => is <= s && ie >= e)) out.add(slotKey(d, r))
    }),
  )
  return out
}

/** Cells touched by any interval: used for calendar BUSY blocks. */
export function overlappedSlots(grid: GridModel, intervals: TimeInterval[]): Set<SlotKey> {
  const ms = toMs(intervals)
  const out = new Set<SlotKey>()
  grid.bounds.forEach((day, d) =>
    day.forEach(([s, e], r) => {
      if (ms.some(([is, ie]) => is < e && ie > s)) out.add(slotKey(d, r))
    }),
  )
  return out
}

/** Selected cells → AVAILABLE intervals for the API, merging runs of adjacent cells per day. */
export function slotsToIntervals(grid: GridModel, selected: Set<SlotKey>): TimeInterval[] {
  const out: TimeInterval[] = []
  const rows = grid.rowMinutes.length
  grid.dates.forEach((date, d) => {
    let runStart: number | null = null
    // r === rows is a sentinel "off" cell that closes a run reaching the last row.
    for (let r = 0; r <= rows; r++) {
      const on = r < rows && selected.has(slotKey(d, r))
      if (on && runStart === null) runStart = r
      if (!on && runStart !== null) {
        out.push({
          start: zonedToIso(date, grid.rowMinutes[runStart], grid.timeZone),
          end: zonedToIso(date, grid.rowMinutes[r - 1] + SLOT_MINUTES, grid.timeZone),
        })
        runStart = null
      }
    }
  })
  return out
}

/** All cells in the rectangle between two corners (When2Meet-style drag). */
export function rectangle(a: [number, number], b: [number, number]): SlotKey[] {
  const keys: SlotKey[] = []
  for (let d = Math.min(a[0], b[0]); d <= Math.max(a[0], b[0]); d++) {
    for (let r = Math.min(a[1], b[1]); r <= Math.max(a[1], b[1]); r++) keys.push(slotKey(d, r))
  }
  return keys
}

/** "9 am", "9:30 am": wall-clock label for a row (already in the Session timezone). */
export function rowLabel(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  const suffix = h < 12 ? 'am' : 'pm'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return m === 0 ? `${h12} ${suffix}` : `${h12}:${String(m).padStart(2, '0')} ${suffix}`
}

/** "4 hours", "1.5 hours", "30 min" */
export function formatSelectedDuration(count: number): string {
  return formatDurationMinutes(count * SLOT_MINUTES)
}

export function formatDurationMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = minutes / 60
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hour${hours === 1 ? '' : 's'}`
}
