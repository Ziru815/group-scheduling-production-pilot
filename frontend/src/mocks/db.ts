/**
 * In-memory mock database for MSW. Dev only: never imported by production code.
 * State resets on every page reload.
 *
 * Shapes here are the BACKEND's internal view (they include private fields such
 * as other people's addresses and invitation tokens). Handlers must convert to
 * the public DTOs in src/api/types.ts before responding.
 */
import type {
  ActivityCategory,
  AvailabilityInterval,
  CalendarConnectionStatus,
  ConfirmedPlan,
  Id,
  IsoDate,
  IsoDateTime,
  LocalTime,
  MyLocation,
  ParticipantRole,
  RecordStatus,
  ResponseStatus,
  SessionStatus,
  SubmissionSource,
  TimeZone,
  TransportMode,
  TravelObjective,
  VenueSummary,
} from '../api/types'
import { localTimeToMinutes, zonedToIso } from '../lib/time'
import type { MockRecommendationSet } from './recommend'

export interface MockUser {
  id: Id
  displayName: string
  email: string
  calendar: CalendarConnectionStatus
}

export interface MockRecord {
  /** Geocoded home. Backend-internal: never returned by the API, not even to the owner. */
  coords: { lat: number; lng: number }
  recordStatus: RecordStatus
  submissionSource: SubmissionSource
  transportMode: TransportMode
  location: MyLocation
  intervals: AvailabilityInterval[]
  submittedAt: IsoDateTime
  withdrawnAt: IsoDateTime | null
}

export interface MockParticipant {
  id: Id
  sessionId: Id
  userId: Id
  role: ParticipantRole
  responseStatus: ResponseStatus
  record: MockRecord | null
  updatedAt: IsoDateTime | null
}

export interface MockSession {
  id: Id
  name: string
  activityTypeId: Id
  organiserUserId: Id
  startDate: IsoDate
  endDate: IsoDate
  dailyStartTime: LocalTime
  dailyEndTime: LocalTime
  timezone: TimeZone
  durationMinutes: number
  responseDeadline: IsoDateTime
  minimumAttendees: number
  travelObjective: TravelObjective
  attendanceWeightPercent: number
  status: SessionStatus
  /** Access Data. Only ever leaves the mock inside invitationUrl for the Organiser. */
  invitationToken: string
  recommendations: MockRecommendationSet | null
  recommendationsStale: boolean
  /** Snapshot of the confirmed option (FR-E4), so it survives later re-ranking. */
  confirmed: ConfirmedPlan | null
}

export interface MockLocationCandidate {
  label: string
  postalCode: string | null
  lat: number
  lng: number
}

/** Fake geocoded homes used by the seed data and by mock location search. */
export const FAKE_HOMES = {
  jw41: { label: 'Blk 123 Jurong West Street 41, Singapore 640123', postalCode: '640123', lat: 1.3501, lng: 103.7202 },
  jw91: { label: 'Blk 950 Jurong West Street 91, Singapore 640950', postalCode: '640950', lat: 1.3405, lng: 103.689 },
  clementi: { label: 'Blk 352 Clementi Avenue 2, Singapore 120352', postalCode: '120352', lat: 1.3156, lng: 103.7686 },
  bbwest: { label: 'Blk 920 Bukit Batok West Avenue 2, Singapore 659920', postalCode: '659920', lat: 1.3534, lng: 103.7442 },
  bukitpanjang: { label: 'Blk 210 Bukit Panjang Ring Road, Singapore 670210', postalCode: '670210', lat: 1.3816, lng: 103.7691 },
  jurongeast: { label: 'Blk 531 Jurong East Street 51, Singapore 608531', postalCode: '608531', lat: 1.3504, lng: 103.7347 },
  boonlay: { label: 'Blk 190 Boon Lay Drive, Singapore 640190', postalCode: '640190', lat: 1.3436, lng: 103.7105 },
  ntu: { label: 'Nanyang Technological University, 50 Nanyang Avenue, Singapore 639798', postalCode: '639798', lat: 1.3483, lng: 103.6831 },
  jemrt: { label: 'Jurong East MRT Station, 10 Jurong East Street 12, Singapore 609690', postalCode: '609690', lat: 1.3331, lng: 103.7423 },
} satisfies Record<string, MockLocationCandidate>

type HomeKey = keyof typeof FAKE_HOMES

export interface MockDb {
  /** Signed-in user, or null when signed out. Change it with setCurrentUser(). */
  currentUserId: Id | null
  users: MockUser[]
  activityCategories: ActivityCategory[]
  venues: (VenueSummary & { activityTypeIds: Id[] })[]
  sessions: MockSession[]
  participants: MockParticipant[]
  /** candidateId → geocoded match, as the backend would cache OneMap results. */
  locationCandidates: Map<Id, MockLocationCandidate>
}

const TZ = 'Asia/Singapore'

/** "2026-11-07", "09:00" → ISO with +08:00 offset. */
function at(date: IsoDate, time: LocalTime): IsoDateTime {
  return zonedToIso(date, localTimeToMinutes(time), TZ)
}

function avail(date: IsoDate, from: LocalTime, to: LocalTime): AvailabilityInterval {
  return { start: at(date, from), end: at(date, to), type: 'AVAILABLE', source: 'MANUAL' }
}

function record(
  transportMode: TransportMode,
  homeKey: HomeKey,
  input: Pick<MyLocation, 'inputType' | 'input'>,
  intervals: AvailabilityInterval[],
  submittedAt: IsoDateTime,
): MockRecord {
  const home = FAKE_HOMES[homeKey]
  return {
    coords: { lat: home.lat, lng: home.lng },
    recordStatus: 'ACTIVE',
    submissionSource: 'MANUAL',
    transportMode,
    location: { ...input, label: home.label, geocodeStatus: 'VALID' },
    intervals,
    submittedAt,
    withdrawnAt: null,
  }
}

function participant(
  id: Id,
  sessionId: Id,
  userId: Id,
  role: ParticipantRole,
  responseStatus: ResponseStatus,
  rec: MockRecord | null = null,
): MockParticipant {
  return {
    id,
    sessionId,
    userId,
    role,
    responseStatus,
    record: rec,
    updatedAt: rec ? (rec.withdrawnAt ?? rec.submittedAt) : null,
  }
}

function sessionDefaults(): Pick<
  MockSession,
  'timezone' | 'travelObjective' | 'attendanceWeightPercent' | 'recommendations' | 'recommendationsStale' | 'confirmed'
> {
  return {
    timezone: TZ,
    travelObjective: 'MIN_TOTAL',
    attendanceWeightPercent: 50,
    recommendations: null,
    recommendationsStale: false,
    confirmed: null,
  }
}

function seed(): MockDb {
  const users: MockUser[] = [
    { id: 'u-weijie', displayName: 'Wei Jie', email: 'weijie@example.com', calendar: 'CONNECTED' },
    { id: 'u-amirah', displayName: 'Amirah', email: 'amirah@example.com', calendar: 'DISCONNECTED' },
    { id: 'u-kaiming', displayName: 'Kai Ming', email: 'kaiming@example.com', calendar: 'DISCONNECTED' },
    { id: 'u-priya', displayName: 'Priya', email: 'priya@example.com', calendar: 'DISCONNECTED' },
    { id: 'u-farhan', displayName: 'Farhan', email: 'farhan@example.com', calendar: 'DISCONNECTED' },
    { id: 'u-siti', displayName: 'Siti', email: 'siti@example.com', calendar: 'DISCONNECTED' },
    { id: 'u-daniel', displayName: 'Daniel', email: 'daniel@example.com', calendar: 'DISCONNECTED' },
    { id: 'u-mei', displayName: 'Mei Ling', email: 'meiling@example.com', calendar: 'DISCONNECTED' },
  ]

  const activityCategories: ActivityCategory[] = [
    {
      category: 'Sports',
      types: [
        { id: 'at-football', name: 'Football' },
        { id: 'at-badminton', name: 'Badminton' },
        { id: 'at-basketball', name: 'Basketball' },
        { id: 'at-futsal', name: 'Futsal' },
      ],
    },
    {
      category: 'Social',
      types: [
        { id: 'at-karaoke', name: 'Karaoke' },
        { id: 'at-dinner', name: 'Dinner' },
        { id: 'at-boardgames', name: 'Board games' },
      ],
    },
    {
      category: 'Outdoors',
      types: [
        { id: 'at-picnic', name: 'Picnic' },
        { id: 'at-cycling', name: 'Cycling' },
        { id: 'at-hiking', name: 'Hiking' },
      ],
    },
  ]

  // Public Venue data (§5.5). Addresses and coordinates are approximate mock values.
  const demoVenueProvenance = { dataSource: 'Demo catalogue', lastUpdated: null } as const
  const venues: MockDb['venues'] = [
    {
      ...demoVenueProvenance,
      id: 'v-jw-hall',
      name: 'Jurong West Sports Hall',
      category: 'SPORTS_FACILITY',
      address: '20 Jurong West Street 93, Singapore 648965',
      latitude: 1.3389,
      longitude: 103.6943,
      activityTypeIds: ['at-badminton', 'at-basketball', 'at-futsal'],
    },
    {
      ...demoVenueProvenance,
      id: 'v-clementi-hall',
      name: 'Clementi Sports Hall',
      category: 'SPORTS_FACILITY',
      address: '518 Clementi Avenue 3, Singapore 129907',
      latitude: 1.3127,
      longitude: 103.7647,
      activityTypeIds: ['at-badminton', 'at-basketball'],
    },
    {
      ...demoVenueProvenance,
      id: 'v-gombak-hall',
      name: 'Bukit Gombak Sports Hall',
      category: 'SPORTS_FACILITY',
      address: '800 Bukit Batok West Avenue 5, Singapore 659081',
      latitude: 1.3587,
      longitude: 103.7516,
      activityTypeIds: ['at-badminton', 'at-futsal'],
    },
    {
      ...demoVenueProvenance,
      id: 'v-cck-stadium',
      name: 'Choa Chu Kang Stadium',
      category: 'SPORTS_FACILITY',
      address: '1 Choa Chu Kang Street 53, Singapore 689236',
      latitude: 1.3912,
      longitude: 103.7473,
      activityTypeIds: ['at-football', 'at-futsal'],
    },
    {
      ...demoVenueProvenance,
      id: 'v-westcoast-park',
      name: 'West Coast Park',
      category: 'PARK',
      address: 'West Coast Ferry Road, Singapore 126978',
      latitude: 1.295,
      longitude: 103.7631,
      activityTypeIds: ['at-football', 'at-picnic', 'at-cycling'],
    },
    {
      ...demoVenueProvenance,
      id: 'v-jl-gardens',
      name: 'Jurong Lake Gardens',
      category: 'PARK',
      address: 'Yuan Ching Road, Singapore 618661',
      latitude: 1.3381,
      longitude: 103.7255,
      activityTypeIds: ['at-picnic', 'at-cycling', 'at-hiking'],
    },
    {
      ...demoVenueProvenance,
      id: 'v-jurong-point',
      name: 'Jurong Point',
      category: 'MALL',
      address: '1 Jurong West Central 2, Singapore 648886',
      latitude: 1.3397,
      longitude: 103.7067,
      activityTypeIds: ['at-karaoke', 'at-dinner', 'at-boardgames'],
    },
    {
      ...demoVenueProvenance,
      id: 'v-jem',
      name: 'JEM',
      category: 'MALL',
      address: '50 Jurong Gateway Road, Singapore 608549',
      latitude: 1.3331,
      longitude: 103.7435,
      activityTypeIds: ['at-karaoke', 'at-dinner', 'at-boardgames'],
    },
  ]

  // Starting locations below are private: only their owner may ever see them (NFR-13).
  const sessions: MockSession[] = [
    {
      ...sessionDefaults(),
      id: 's-badminton',
      name: 'Weekend badminton',
      activityTypeId: 'at-badminton',
      organiserUserId: 'u-weijie',
      startDate: '2026-11-07',
      endDate: '2026-11-08',
      dailyStartTime: '08:00',
      dailyEndTime: '18:00',
      durationMinutes: 90,
      responseDeadline: at('2026-11-02', '18:00'),
      minimumAttendees: 4,
      attendanceWeightPercent: 80,
      status: 'ACTIVE',
      invitationToken: 'mock-badminton-invite',
    },
    {
      ...sessionDefaults(),
      id: 's-fiveaside',
      name: 'Wednesday five-a-side',
      activityTypeId: 'at-football',
      organiserUserId: 'u-kaiming',
      startDate: '2026-11-04',
      endDate: '2026-11-06',
      dailyStartTime: '18:00',
      dailyEndTime: '22:00',
      durationMinutes: 90,
      responseDeadline: at('2026-10-30', '20:00'),
      minimumAttendees: 3,
      status: 'ACTIVE',
      invitationToken: 'mock-fiveaside-invite',
    },
    {
      ...sessionDefaults(),
      id: 's-football',
      name: 'Sunday football',
      activityTypeId: 'at-football',
      organiserUserId: 'u-amirah',
      startDate: '2026-10-24',
      endDate: '2026-10-25',
      dailyStartTime: '08:00',
      dailyEndTime: '20:00',
      durationMinutes: 90,
      responseDeadline: at('2026-10-14', '20:00'),
      minimumAttendees: 3,
      status: 'CONFIRMED',
      invitationToken: 'mock-football-invite',
    },
    {
      ...sessionDefaults(),
      id: 's-picnic',
      name: 'Botanic picnic',
      activityTypeId: 'at-picnic',
      organiserUserId: 'u-priya',
      startDate: '2026-11-14',
      endDate: '2026-11-15',
      dailyStartTime: '09:00',
      dailyEndTime: '18:00',
      durationMinutes: 180,
      responseDeadline: at('2026-11-10', '12:00'),
      minimumAttendees: 4,
      status: 'CANCELLED',
      invitationToken: 'mock-picnic-invite',
    },
    {
      // Wei Jie is not a member yet: open /join/mock-karaoke-invite to test UC-05.
      ...sessionDefaults(),
      id: 's-karaoke',
      name: 'Friday karaoke',
      activityTypeId: 'at-karaoke',
      organiserUserId: 'u-farhan',
      startDate: '2026-11-13',
      endDate: '2026-11-14',
      dailyStartTime: '17:00',
      dailyEndTime: '23:00',
      durationMinutes: 120,
      responseDeadline: at('2026-11-10', '12:00'),
      minimumAttendees: 3,
      status: 'ACTIVE',
      invitationToken: 'mock-karaoke-invite',
    },
  ]

  const submitted = at('2026-10-15', '21:00')
  const participants: MockParticipant[] = [
    // Weekend badminton: 5 of 8 responded, 1 withdrawn (matches the storyboard).
    participant('p-bad-weijie', 's-badminton', 'u-weijie', 'ORGANISER', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'jw41', { inputType: 'POSTAL_CODE', input: '640123' },
        [avail('2026-11-07', '09:00', '13:00'), avail('2026-11-08', '10:00', '12:00')], submitted)),
    participant('p-bad-amirah', 's-badminton', 'u-amirah', 'PARTICIPANT', 'SUBMITTED',
      record('DRIVE', 'bbwest', { inputType: 'POSTAL_CODE', input: '659920' },
        [avail('2026-11-07', '09:00', '12:00'), avail('2026-11-08', '09:00', '14:00')], submitted)),
    participant('p-bad-kaiming', 's-badminton', 'u-kaiming', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'clementi', { inputType: 'ADDRESS', input: 'Clementi Ave 2' },
        [avail('2026-11-07', '10:00', '13:00'), avail('2026-11-08', '13:00', '16:00')], submitted)),
    participant('p-bad-siti', 's-badminton', 'u-siti', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'jw91', { inputType: 'POSTAL_CODE', input: '640950' },
        [avail('2026-11-07', '08:00', '12:00'), avail('2026-11-08', '10:00', '13:00')], submitted)),
    participant('p-bad-daniel', 's-badminton', 'u-daniel', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'bukitpanjang', { inputType: 'ADDRESS', input: 'Bukit Panjang Ring Road' },
        [avail('2026-11-07', '09:00', '11:00'), avail('2026-11-08', '10:00', '14:00')], submitted)),
    participant('p-bad-farhan', 's-badminton', 'u-farhan', 'PARTICIPANT', 'WITHDRAWN', {
      ...record('DRIVE', 'jurongeast', { inputType: 'POSTAL_CODE', input: '608531' },
        [avail('2026-11-07', '09:00', '12:00')], submitted),
      recordStatus: 'WITHDRAWN',
      withdrawnAt: at('2026-10-16', '08:30'),
    }),
    participant('p-bad-priya', 's-badminton', 'u-priya', 'PARTICIPANT', 'NOT_SUBMITTED'),
    participant('p-bad-mei', 's-badminton', 'u-mei', 'PARTICIPANT', 'NOT_SUBMITTED'),

    // Wednesday five-a-side: Wei Jie still needs to respond.
    participant('p-five-kaiming', 's-fiveaside', 'u-kaiming', 'ORGANISER', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'clementi', { inputType: 'ADDRESS', input: 'Clementi Ave 2' },
        [avail('2026-11-04', '18:00', '22:00'), avail('2026-11-05', '19:00', '22:00')], submitted)),
    participant('p-five-daniel', 's-fiveaside', 'u-daniel', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'bukitpanjang', { inputType: 'ADDRESS', input: 'Bukit Panjang Ring Road' },
        [avail('2026-11-04', '19:00', '22:00')], submitted)),
    participant('p-five-farhan', 's-fiveaside', 'u-farhan', 'PARTICIPANT', 'SUBMITTED',
      record('DRIVE', 'jurongeast', { inputType: 'POSTAL_CODE', input: '608531' },
        [avail('2026-11-04', '18:00', '21:00'), avail('2026-11-06', '18:00', '22:00')], submitted)),
    participant('p-five-weijie', 's-fiveaside', 'u-weijie', 'PARTICIPANT', 'NOT_SUBMITTED'),

    // Sunday football: confirmed.
    participant('p-foot-amirah', 's-football', 'u-amirah', 'ORGANISER', 'SUBMITTED',
      record('DRIVE', 'bbwest', { inputType: 'POSTAL_CODE', input: '659920' },
        [avail('2026-10-25', '14:00', '19:00')], submitted)),
    participant('p-foot-weijie', 's-football', 'u-weijie', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'jw41', { inputType: 'POSTAL_CODE', input: '640123' },
        [avail('2026-10-25', '15:00', '18:00')], submitted)),
    participant('p-foot-kaiming', 's-football', 'u-kaiming', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'clementi', { inputType: 'ADDRESS', input: 'Clementi Ave 2' },
        [avail('2026-10-25', '16:00', '18:00')], submitted)),
    participant('p-foot-siti', 's-football', 'u-siti', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'jw91', { inputType: 'POSTAL_CODE', input: '640950' },
        [avail('2026-10-25', '15:00', '19:00')], submitted)),

    // Botanic picnic: cancelled.
    participant('p-pic-priya', 's-picnic', 'u-priya', 'ORGANISER', 'NOT_SUBMITTED'),
    participant('p-pic-weijie', 's-picnic', 'u-weijie', 'PARTICIPANT', 'NOT_SUBMITTED'),

    // Friday karaoke: Wei Jie has not joined.
    participant('p-kar-farhan', 's-karaoke', 'u-farhan', 'ORGANISER', 'SUBMITTED',
      record('DRIVE', 'jurongeast', { inputType: 'POSTAL_CODE', input: '608531' },
        [avail('2026-11-13', '19:00', '23:00')], submitted)),
    participant('p-kar-mei', 's-karaoke', 'u-mei', 'PARTICIPANT', 'SUBMITTED',
      record('PUBLIC_TRANSPORT', 'boonlay', { inputType: 'ADDRESS', input: 'Boon Lay Drive' },
        [avail('2026-11-13', '18:00', '22:00')], submitted)),
  ]

  return {
    currentUserId: loadCurrentUser(),
    users,
    activityCategories,
    venues,
    sessions,
    participants,
    locationCandidates: new Map(),
  }
}

// The signed-in mock user is the only mock state kept across reloads (in this
// tab's sessionStorage), so sign-out and persona switches survive a refresh.
const CURRENT_USER_KEY = 'mock-api.current-user'
const DEFAULT_USER_ID = 'u-weijie'

function loadCurrentUser(): Id | null {
  try {
    const stored = sessionStorage.getItem(CURRENT_USER_KEY)
    if (stored === null) return DEFAULT_USER_ID
    return stored === '' ? null : stored
  } catch {
    return DEFAULT_USER_ID
  }
}

export function setCurrentUser(id: Id | null) {
  db.currentUserId = id
  try {
    sessionStorage.setItem(CURRENT_USER_KEY, id ?? '')
  } catch {
    // Storage unavailable (private mode etc.): state lasts until reload.
  }
}

export const db: MockDb = seed()
