import type { RankedCombination } from '../api/types'

export interface RankedOptionGroup {
  key: string
  displayRank: number
  options: RankedCombination[]
}

const INITIAL_TIME_LIMIT = 6

function groupingKey(option: RankedCombination): string {
  const attendees = option.attendees
    .map((attendee) => [
      attendee.participantId,
      attendee.transportMode,
      attendee.routingStatus,
      attendee.travelMinutes,
    ])
    .sort(([left], [right]) => String(left).localeCompare(String(right)))
  const absentees = option.absentees
    .map((absentee) => [absentee.participantId, absentee.attendanceStatus])
    .sort(([left], [right]) => String(left).localeCompare(String(right)))

  return JSON.stringify({
    venueId: option.venue.id,
    officialUrl: option.venue.officialUrl,
    feasibilityStatus: option.feasibilityStatus,
    combinedScore: option.combinedScore,
    attendanceScore: option.attendanceScore,
    travelScore: option.travelScore,
    totalTravelMinutes: option.totalTravelMinutes,
    averageTravelMinutes: option.averageTravelMinutes,
    maxTravelMinutes: option.maxTravelMinutes,
    attendees,
    absentees,
  })
}

export function groupRankedCombinations(options: readonly RankedCombination[]): RankedOptionGroup[] {
  const grouped = new Map<string, RankedCombination[]>()

  for (const option of options) {
    const key = groupingKey(option)
    const group = grouped.get(key)
    if (group) group.push(option)
    else grouped.set(key, [option])
  }

  return [...grouped.entries()].map(([key, candidates], index) => ({
    key,
    displayRank: index + 1,
    options: candidates.sort(
      (left, right) =>
        Date.parse(left.start) - Date.parse(right.start) ||
        left.rank - right.rank ||
        left.combinationId.localeCompare(right.combinationId),
    ),
  }))
}

export function selectedOptionForGroup(
  group: RankedOptionGroup,
  preferredCombinationId?: string,
  confirmedCombinationId?: string,
): RankedCombination {
  if (group.options.length === 0) throw new Error('A ranked option group must contain at least one option')

  return (
    group.options.find((option) => option.combinationId === preferredCombinationId) ??
    group.options.find((option) => option.combinationId === confirmedCombinationId) ??
    group.options[0]
  )
}

export function visibleTimeOptions(
  options: readonly RankedCombination[],
  showAllTimes: boolean,
): readonly RankedCombination[] {
  return showAllTimes ? options : options.slice(0, INITIAL_TIME_LIMIT)
}

export function chooseRecommendationTime(
  current: Readonly<Record<string, string>>,
  groupKey: string,
  combinationId: string,
  confirmationPending: boolean,
): Record<string, string> {
  return confirmationPending ? current : { ...current, [groupKey]: combinationId }
}
