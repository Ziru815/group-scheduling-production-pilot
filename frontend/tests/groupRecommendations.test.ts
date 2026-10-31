import assert from 'node:assert/strict'
import test from 'node:test'

import type { RankedCombination } from '../src/api/types.ts'
import {
  chooseRecommendationTime,
  groupRankedCombinations,
  selectedOptionForGroup,
  type RankedOptionGroup,
  visibleTimeOptions,
} from '../src/results/groupRecommendations.ts'

const MINUTE_MS = 60_000

function option(
  id: string,
  rank: number,
  startMinute: number,
  overrides: Partial<RankedCombination> = {},
): RankedCombination {
  const start = Date.parse('2026-11-01T09:00:00+08:00') + startMinute * MINUTE_MS
  return {
    combinationId: id,
    rank,
    venue: {
      id: 'jurong-central-park',
      name: 'Jurong Central Park',
      category: 'PARK',
      address: 'Jalan Boon Lay, Singapore',
      meetingPoint: 'Jalan Boon Lay entrance',
      latitude: 1.338,
      longitude: 103.708,
      dataSource: 'NParks via data.gov.sg',
      lastUpdated: '2026-10-31T00:00:00+08:00',
    },
    start: new Date(start).toISOString(),
    end: new Date(start + 8 * 60 * MINUTE_MS).toISOString(),
    feasibilityStatus: 'FEASIBLE',
    attendeeCount: 2,
    meetsRequestedMinimum: true,
    combinedScore: 78,
    attendanceScore: 100,
    travelScore: 45,
    totalTravelMinutes: 62,
    averageTravelMinutes: 31,
    maxTravelMinutes: 33,
    explanation: '2 attending; longest journey 33 min; attendance weighted 60%',
    attendees: [
      {
        participantId: 'participant-yunyi',
        displayName: 'Yunyi',
        transportMode: 'PUBLIC_TRANSPORT',
        travelMinutes: 29,
        routingStatus: 'AVAILABLE',
      },
      {
        participantId: 'participant-ziru',
        displayName: 'Ziru',
        transportMode: 'PUBLIC_TRANSPORT',
        travelMinutes: 33,
        routingStatus: 'AVAILABLE',
      },
    ],
    absentees: [],
    ...overrides,
  }
}

test('groups only equivalent outcomes at one venue', () => {
  const options = Array.from({ length: 11 }, (_, index) => option(`jurong-${index}`, index + 1, index * 15))

  const groups = groupRankedCombinations(options)

  assert.equal(groups.length, 1)
  assert.equal(groups[0].displayRank, 1)
  assert.equal(groups[0].options.length, 11)
  assert.equal(groups[0].options[0].combinationId, 'jurong-0')
  assert.equal(groups[0].options[10].combinationId, 'jurong-10')
})

test('keeps different attendance and routing outcomes separate', () => {
  const original = option('original', 1, 0)
  const differentAttendee = option('different-attendee', 2, 15, {
    attendees: [
      original.attendees[0],
      { ...original.attendees[1], participantId: 'participant-roommate', displayName: 'Roommate' },
    ],
  })
  const differentDuration = option('different-duration', 3, 30, {
    attendees: [original.attendees[0], { ...original.attendees[1], travelMinutes: 34 }],
  })
  const differentRoutingStatus = option('different-routing', 4, 45, {
    attendees: [original.attendees[0], { ...original.attendees[1], routingStatus: 'ERROR' }],
  })

  const groups = groupRankedCombinations([
    original,
    differentAttendee,
    differentDuration,
    differentRoutingStatus,
  ])

  assert.equal(groups.length, 4)
  assert.deepEqual(
    groups.map((group) => group.options[0].combinationId),
    ['original', 'different-attendee', 'different-duration', 'different-routing'],
  )
})

test('keeps group order while sorting times chronologically', () => {
  const firstVenueLate = option('first-late', 1, 30)
  const secondVenue = option('second-venue', 2, 0, {
    venue: { ...firstVenueLate.venue, id: 'chinese-garden', name: 'Chinese Garden' },
    combinedScore: 75.3,
  })
  const firstVenueEarly = option('first-early', 3, 0)

  const groups = groupRankedCombinations([firstVenueLate, secondVenue, firstVenueEarly])

  assert.equal(groups.length, 2)
  assert.deepEqual(
    groups.map((group) => [group.displayRank, group.options[0].venue.id]),
    [
      [1, 'jurong-central-park'],
      [2, 'chinese-garden'],
    ],
  )
  assert.deepEqual(
    groups[0].options.map((candidate) => candidate.combinationId),
    ['first-early', 'first-late'],
  )
})

test('selects an explicit valid time', () => {
  const [group] = groupRankedCombinations([option('early', 1, 0), option('later', 2, 15)])

  const selected = selectedOptionForGroup(group, 'later', 'early')

  assert.equal(selected.combinationId, 'later')
})

test('prefers a confirmed time when the explicit selection is stale', () => {
  const [group] = groupRankedCombinations([option('early', 1, 0), option('confirmed', 2, 15)])

  const selected = selectedOptionForGroup(group, 'removed-by-regeneration', 'confirmed')

  assert.equal(selected.combinationId, 'confirmed')
})

test('falls back to the first ranked time', () => {
  const [group] = groupRankedCombinations([option('later-ranked-first', 1, 15), option('earlier', 2, 0)])

  const selected = selectedOptionForGroup(group, 'missing', 'also-missing')

  assert.equal(selected.combinationId, 'earlier')
})

test('rejects an empty recommendation group', () => {
  const empty: RankedOptionGroup = { key: 'empty', displayRank: 1, options: [] }

  assert.throws(() => selectedOptionForGroup(empty), /at least one option/i)
})

test('shows six time choices before the user reveals the rest', () => {
  const options = Array.from({ length: 11 }, (_, index) => option(`time-${index}`, index + 1, index * 15))

  assert.deepEqual(
    visibleTimeOptions(options, false).map((candidate) => candidate.combinationId),
    ['time-0', 'time-1', 'time-2', 'time-3', 'time-4', 'time-5'],
  )
  assert.equal(visibleTimeOptions(options, true).length, 11)
})

test('keeps the submitted time selected while confirmation is pending', () => {
  const current = { 'jurong-group': 'early-combination' }

  const next = chooseRecommendationTime(current, 'jurong-group', 'later-combination', true)

  assert.strictEqual(next, current)
  assert.equal(next['jurong-group'], 'early-combination')
})

test('allows choosing another time before confirmation starts', () => {
  const current = { 'jurong-group': 'early-combination' }

  const next = chooseRecommendationTime(current, 'jurong-group', 'later-combination', false)

  assert.notStrictEqual(next, current)
  assert.equal(next['jurong-group'], 'later-combination')
})
