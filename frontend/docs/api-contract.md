# Group Scheduling Application: Frontend ↔ Backend API Contract

**Status:** Draft v0.1 (16 Oct 2026) from the frontend. Please review and push back.
**Sources:** SRS v2.0 (§3.1, §3.4, §4, §5.3, §5.5, App. B and D), Use Cases v2.0 (UC-00 to UC-12).
**Implemented by:** MSW mocks in `frontend/src/mocks/handlers.ts`. TypeScript types are in `frontend/src/api/types.ts`; if this document and the types disagree, raise it.

---

## 1. Conventions

| Topic | Rule |
|---|---|
| Base path | All endpoints are under `/api`. The browser calls the same origin; in dev, Vite proxies `/api` → `http://localhost:8000`. |
| Format | JSON request and response bodies, **camelCase** keys (with Pydantic: `alias_generator=to_camel`, `populate_by_name=True`). |
| IDs | Opaque strings (UUIDs). The frontend never parses them. |
| Date-times | ISO 8601 **with offset**, e.g. `"2026-11-07T09:00:00+08:00"`. |
| Dates / times of day | `"YYYY-MM-DD"` and `"HH:mm"` (24 h), always interpreted in the Session's `timezone`. |
| Timezone | Every Session has an IANA `timezone` (default `"Asia/Singapore"`). The frontend shows all Session times in it, never in the browser's zone (SRS §6). |
| Auth | Google sign-in uses `openid email profile` only and ends with an **httpOnly, Secure, SameSite=Lax session cookie** set by the backend. The frontend sends `credentials: 'include'` and never sees a token. Google Calendar permission is a separate future flow. |
| CSRF | Because auth is cookie-based, please require a JSON `Content-Type` on mutating requests, or add a CSRF header we can send. Tell us which. |
| Errors | Every non-2xx returns the error envelope in §1.1. |
| Not signed in | Any endpoint → `401 UNAUTHENTICATED`. The frontend then sends the user to `/signin`. |
| Not a member | A Session the caller isn't in → `404 NOT_FOUND` (don't reveal that it exists). |
| Organiser-only | A member who isn't the Organiser → `403 FORBIDDEN`. Authorise by matching the signed-in User Account to the Session's Organiser (SRS §5.3). |

### 1.1 Error envelope

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Please fix the highlighted fields.",
    "fields": { "durationMinutes": "Duration must be a whole number from 15 to 480 minutes." }
  }
}
```

`fields` keys are **request field names**. The frontend shows each message inline under that field (SRS §3.1: no modal errors). `message` is shown to the user, so write it for end users.

| `code` | HTTP | When |
|---|---|---|
| `UNAUTHENTICATED` | 401 | No or expired session cookie |
| `FORBIDDEN` | 403 | Signed in, but not allowed (e.g. not the Organiser) |
| `NOT_FOUND` | 404 | Unknown resource, or not a member |
| `INVITATION_INVALID` | 404 | Unknown or revoked invitation token (UC-05.EX.1) |
| `VALIDATION_FAILED` | 422 | Field errors in `fields` |
| `ACTIVITY_UNSUPPORTED` | 409 | A historical Session's activity no longer has active verified venue support, so it is read-only |
| `SESSION_CLOSED` | 409 | Deadline passed, or Session cancelled or confirmed |
| `NO_RESPONSES` | 409 | UC-09 precondition: no valid response yet |
| `NO_FEASIBLE_TIMESLOT` | 409 | UC-09.AC.1: no timeslot meets the minimum attendees |
| `RECOMMENDATIONS_STALE` | 409 | Confirm attempted on outdated or missing results |
| `COMBINATION_NOT_FEASIBLE` | 409 | Confirm attempted on an excluded or data-unavailable option |
| `CALENDAR_NOT_CONNECTED` | 409 | Busy import without a Calendar connection |
| `EXTERNAL_SERVICE_UNAVAILABLE` | 503 | OneMap or Google unreachable; the frontend offers Retry (NFR-3) |

### 1.2 Privacy rules the API must enforce

- **NFR-13:** a participant's address, postal code or coordinates are returned **only** to that participant (`GET /my-response`). No other response contains them, not even for the Organiser.
- **Emails** are returned only to their owner (`GET /me`).
- **Invitation token (Access Data, §3.4):** never put it in an API URL, since URLs end up in access logs. The frontend sends it **only in POST bodies**. Please also keep it out of application logs. The page URL `/join/<token>` is served by the static host: either exclude `/join/*` from its access logs, or tell us and we'll move the token into the URL fragment (`/join#<token>`), which browsers never send to servers.
- **Addresses in requests** are also sent only in POST bodies, never in query strings.
- **Calendar:** free/busy only; never titles, descriptions or attendees (NFR-14).

---

## 2. Endpoint summary

| # | Method & path | Who | Use case / FR |
|---|---|---|---|
| 1 | `GET /api/me` | signed in | UC-00 |
| 2 | `GET /api/auth/google/login?next=` | anyone (browser redirect) | UC-00 |
| 3 | `POST /api/auth/logout` | signed in | UC-00 |
| 4 | `GET /api/activity-types` | signed in | UC-01, FR-A1 |
| 5 | `GET /api/sessions` | signed in | "Your sessions" (§3.1) |
| 6 | `POST /api/sessions` | signed in | UC-01, FR-A1 to FR-A4 |
| 7 | `GET /api/sessions/{id}` | member | UC-02 step 2, FR-A5.1, FR-E5 |
| 8 | `PATCH /api/sessions/{id}` | Organiser | UC-02, FR-D6, FR-D9 |
| 9 | `POST /api/sessions/{id}/cancel` | Organiser | UC-04, FR-A5 |
| 10 | `GET /api/sessions/{id}/invitation` | Organiser | FR-A2 |
| 11 | `POST /api/invitations/resolve` | signed in | UC-05 steps 1 to 3 |
| 12 | `POST /api/invitations/join` | signed in | UC-05 step 5 |
| 13 | `GET /api/sessions/{id}/my-response` | member | UC-07 step 1 |
| 14 | `PUT /api/sessions/{id}/my-response` | member | UC-06, UC-07, UC-08, FR-B1 to FR-B5 |
| 15 | `POST /api/sessions/{id}/my-response/withdraw` | member | UC-07.AC.1, FR-B6 |
| 16 | `POST /api/locations/search` | signed in | UC-08 steps 1 to 3, FR-B3, FR-B3.1 |
| 17 | `GET /api/sessions/{id}/responses` | Organiser | UC-03, FR-B7 |
| 18 | `GET /api/sessions/{id}/recommendations` | member | UC-11, FR-E1 to FR-E3 |
| 19 | `POST /api/sessions/{id}/recommendations` | Organiser | UC-09, UC-10, FR-C1 to FR-D10 |
| 20 | `POST /api/sessions/{id}/confirm` | Organiser | UC-12, FR-E4, FR-E6 |
| 21 | `GET /api/calendar/connection` | signed in | FR-B8 |
| 22 | `GET /api/calendar/google/connect?next=` | signed in (browser redirect) | FR-B8 |
| 23 | `DELETE /api/calendar/connection` | signed in | FR-B8 |
| 24 | `POST /api/sessions/{id}/calendar-busy` | member | FR-B8, FR-B8.1 |

**Development-only:** `GET /api/dev/users`, `POST /api/dev/sign-in` and `POST /api/dev/calendar/connect` power the local persona/calendar demo. The production backend returns `404` for them, and production builds do not show the persona switcher.

**System-side, no endpoint:** FR-B9 and FR-B10 (tentative holds created and deleted) and FR-E6 (confirmed calendar event) are backend side-effects of #19 and #20. NFR-11 (atomic withdrawal) is enforced inside #15 and #19.

---

## 3. Shared shapes

Written as TypeScript for brevity; `?` means optional and `| null` means nullable.

```ts
type SessionStatus   = 'ACTIVE' | 'CONFIRMED' | 'CANCELLED'
type ParticipantRole = 'ORGANISER' | 'PARTICIPANT'
type ResponseStatus  = 'NOT_SUBMITTED' | 'SUBMITTED' | 'WITHDRAWN'
type TransportMode   = 'WALK' | 'DRIVE' | 'PUBLIC_TRANSPORT'
type LocationInputType = 'ADDRESS' | 'POSTAL_CODE'
type GeocodeStatus   = 'PENDING' | 'VALID' | 'INVALID' | 'UNAVAILABLE'
type SubmissionSource = 'MANUAL' | 'CALENDAR_ASSISTED'
type RecordStatus    = 'ACTIVE' | 'WITHDRAWN'
type IntervalType    = 'AVAILABLE' | 'BUSY'
type IntervalSource  = 'MANUAL' | 'GOOGLE_CALENDAR'
type VenueCategory   = 'SPORTS_FACILITY' | 'PARK' | 'MALL'
type TravelObjective = 'MIN_TOTAL' | 'MIN_MAX_INDIVIDUAL'
type FeasibilityStatus = 'PENDING' | 'FEASIBLE' | 'EXCLUDED' | 'DATA_UNAVAILABLE'
type ExclusionReason = 'BELOW_THRESHOLD' | 'JOURNEY_LIMIT' | 'GROUP_SIZE' | 'BOOKING_LEAD_TIME'
type RoutingStatus   = 'AVAILABLE' | 'UNAVAILABLE' | 'ERROR'
type AttendanceStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'NO_RESPONSE' | 'WITHDRAWN'
type CalendarConnectionStatus = 'CONNECTED' | 'DISCONNECTED' | 'DECLINED' | 'EXPIRED' | 'ERROR'
type ExternalServiceStatus = 'RECEIVED' | 'UNAVAILABLE' | 'ERROR'

interface VenueSummary {           // public data (§5.5)
  id: string; name: string; category: VenueCategory
  address: string; latitude: number; longitude: number
  dataSource: string               // catalogue provenance, not live availability
  lastUpdated: string | null        // ISO catalogue-sync timestamp
}

interface ConfirmedPlan {
  combinationId: string
  venue: VenueSummary
  start: string; end: string                       // ISO with offset
  attendees: { participantId: string; displayName: string }[]
  confirmedAt: string
}

interface SessionDetail {
  id: string
  name: string                                     // ⚠ not in SRS entity; see open question 7
  activityType: { id: string; name: string; category: string }
  activitySupported: boolean                       // false keeps historical Session readable but read-only
  organiserName: string
  status: SessionStatus
  myRole: ParticipantRole                          // caller's role
  myResponseStatus: ResponseStatus                 // caller's status
  startDate: string; endDate: string               // "YYYY-MM-DD" in timezone
  dailyStartTime: string; dailyEndTime: string     // "HH:mm" ⚠ proposed; see open question 9
  timezone: string
  durationMinutes: number                          // 15..480
  responseDeadline: string                         // ISO with offset
  minimumAttendees: number
  travelObjective: TravelObjective
  attendanceWeightPercent: number                  // 0,10,..,100; travel = 100 minus this
  isClosed: boolean                                // status != ACTIVE or deadline passed
  recommendationsStale: boolean                    // ⚠ not in SRS entity; see open question 15
  hasRecommendations: boolean
  confirmed: ConfirmedPlan | null
}
```

`VenueSummary.dataSource` and `lastUpdated` describe catalogue provenance only.
They do not claim that a court is currently available or bookable; clients must
direct users to ActiveSG for current closures and booking details.

---

## 4. Endpoints

### 4.1 Identity (UC-00)

#### 1. `GET /api/me`
`200`
```json
{ "id": "u-123", "displayName": "Wei Jie", "email": "weijie@example.com" }
```
`401` when signed out. The frontend calls this on load to decide whether to show `/signin`.

#### 2. `GET /api/auth/google/login?next=/signin`
A **full-page navigation**, not a fetch. The backend redirects to Google OpenID Connect with exactly `openid email profile`, a random `state`, `nonce`, and S256 PKCE challenge. It also sets a short-lived, HttpOnly, Secure, SameSite=Lax transaction cookie. The callback succeeds only when Google returns the matching state to the same browser, the transaction is unexpired, the nonce/audience/issuer match, and the email is verified.

On callback the backend creates or matches the User Account by Google subject, refuses to attach an email already owned by another subject, consumes the transaction cookie, sets the application session cookie, and redirects to `next`. It does not store Google access or refresh tokens. Google Calendar is not part of sign-in and requires a separate consent flow.
- The frontend currently always sends `next=/signin`. The sign-in page then returns the user to the page they wanted, which the frontend keeps in `sessionStorage`. This means an invitation token in a `/join/...` path never reaches the backend.
- Still validate `next`: it must be a relative in-app path. Reject anything else (open-redirect risk) and fall back to `/signin`.
- On consent declined (UC-00.AC.1): redirect to `/signin?error=declined`. Expired/mismatched transactions, identity conflicts, invalid provider responses, and provider outages all redirect to `/signin?error=unavailable`; the browser message stays generic and sensitive detail remains server-side.

#### 3. `POST /api/auth/logout`
`204`. Clears the cookie.

### 4.2 Activity catalogue

#### 4. `GET /api/activity-types`
`200`, grouped for the chip groups. In production this includes only active
types with at least one active, publicly verified supported venue. Development
mock mode preserves all active reference types:
```json
[
  { "category": "Sports", "types": [ { "id": "at-football", "name": "Football" }, { "id": "at-badminton", "name": "Badminton" } ] },
  { "category": "Social", "types": [ { "id": "at-karaoke", "name": "Karaoke" } ] }
]
```

### 4.3 Sessions (UC-01 to UC-04)

#### 5. `GET /api/sessions`
Every Session the caller is a member of, any status. The frontend groups them.
```json
[
  {
    "id": "s-1", "name": "Weekend badminton", "activityTypeName": "Badminton",
    "organiserName": "Wei Jie", "status": "ACTIVE",
    "myRole": "ORGANISER", "myResponseStatus": "SUBMITTED",
    "responseDeadline": "2026-11-02T18:00:00+08:00", "timezone": "Asia/Singapore",
    "submittedCount": 5, "participantCount": 8,
    "confirmed": null
  }
]
```
`confirmed` is `{ "venueName", "start", "end" }` when `status = CONFIRMED`.

#### 6. `POST /api/sessions` (UC-01)
Request:
```json
{
  "name": "Weekend badminton",
  "activityTypeId": "at-badminton",
  "startDate": "2026-11-07",
  "endDate": "2026-11-08",
  "dailyStartTime": "08:00",
  "dailyEndTime": "18:00",
  "timezone": "Asia/Singapore",
  "durationMinutes": 90,
  "responseDeadline": "2026-11-02T18:00:00+08:00",
  "minimumAttendees": 4
}
```
`timezone` is optional (default `Asia/Singapore`).

`201`:
```json
{ "session": { /* SessionDetail */ }, "invitationUrl": "https://app.example/join/Zk3…" }
```
Side effects: the caller becomes the Organiser **and** a Participant (`role: ORGANISER`, `NOT_SUBMITTED`; §5.5 says the Organiser responds too). An unguessable token is generated (≥ 128 bits, URL-safe). FR-C1 timeslot enumeration happens here.

`422` validation, keyed by field:
| Field | Rule |
|---|---|
| `name` | required, ≤ 80 chars |
| `activityTypeId` | an active Activity Type |
| `activityTypeId` (production) | must also have at least one active, publicly verified supported venue; otherwise `422 VALIDATION_FAILED` with `fields.activityTypeId` |
| `startDate` / `endDate` | valid dates, start ≥ today (in `timezone`), end ≥ start |
| `dailyStartTime` / `dailyEndTime` | `HH:mm`, end > start |
| `durationMinutes` | integer 15–480 (FR-A1.1) and ≤ the daily window |
| `responseDeadline` | in the future, and **earlier than `startDate` + `dailyStartTime`** in `timezone` (FR-A3.1) |
| `minimumAttendees` | integer ≥ 1 (default value is TBD-2, so the frontend always sends one) |

#### 7. `GET /api/sessions/{id}`
`200` `SessionDetail`. Used by every session screen, including the cancelled (FR-A5.1) and confirmed (FR-E5) states.

#### 8. `PATCH /api/sessions/{id}` (UC-02 and scoring controls)
Any subset of: `name`, `startDate`, `endDate`, `dailyStartTime`, `dailyEndTime`, `durationMinutes`, `responseDeadline`, `minimumAttendees`, `travelObjective`, `attendanceWeightPercent`.
- Validate the **merged** result with the same rules as #6. On error return `422` and change nothing (UC-02.EX.1).
- `attendanceWeightPercent` is rounded to the nearest 10 (FR-D9.1).
- Changing dates, daily window, duration or minimum attendees sets `recommendationsStale = true` (UC-02 step 5).
- Changing `travelObjective` or `attendanceWeightPercent` **re-ranks** the existing results without re-routing (FR-D9 output). It doesn't make them stale.
- `409 SESSION_CLOSED` unless `status = ACTIVE`.

`200` `SessionDetail`.

#### 9. `POST /api/sessions/{id}/cancel` (UC-04)
Body `{}`. `200` `SessionDetail` with `status: CANCELLED`. `409 SESSION_CLOSED` if already cancelled or confirmed (a confirmed Session is terminal, §5.5). No notifications (C4).

#### 10. `GET /api/sessions/{id}/invitation`
`200` `{ "invitationUrl": "https://app.example/join/Zk3…" }`. Organiser only. Lets the Organiser re-copy the link.

### 4.4 Invitations (UC-05)

The user must already be signed in (C5). The frontend redirects to sign-in first and returns here afterwards.

#### 11. `POST /api/invitations/resolve`
Request `{ "token": "Zk3…" }`. `200`:
```json
{
  "sessionId": "s-1", "name": "Friday karaoke", "activityTypeName": "Karaoke",
  "organiserName": "Farhan", "status": "ACTIVE",
  "startDate": "2026-11-13", "endDate": "2026-11-14", "timezone": "Asia/Singapore",
  "responseDeadline": "2026-11-10T12:00:00+08:00",
  "isClosed": false, "alreadyJoined": false, "activitySupported": true
}
```
`404 INVITATION_INVALID`. A closed Session still returns `200` with `isClosed: true` so the frontend can show its status (UC-05.AC.1). A historical activity without verified venue support returns `activitySupported: false`; it remains readable but cannot be joined or mutated.

#### 12. `POST /api/invitations/join`
Request `{ "token": "Zk3…" }`. `200` `{ "sessionId": "s-1", "participantId": "p-9" }`.
Idempotent: joining again returns the existing participant. `409 SESSION_CLOSED` if closed and not already a member. `404 INVITATION_INVALID`.

### 4.5 My response (UC-06 to UC-08)

#### 13. `GET /api/sessions/{id}/my-response`
`200`:
```json
{
  "participantId": "p-9",
  "responseStatus": "SUBMITTED",
  "record": {
    "recordStatus": "ACTIVE",
    "submissionSource": "MANUAL",
    "transportMode": "PUBLIC_TRANSPORT",
    "location": {
      "inputType": "POSTAL_CODE", "input": "640123",
      "label": "Blk 123 Jurong West Street 41, Singapore 640123",
      "geocodeStatus": "VALID"
    },
    "intervals": [
      { "start": "2026-11-07T09:00:00+08:00", "end": "2026-11-07T13:00:00+08:00", "type": "AVAILABLE", "source": "MANUAL" }
    ],
    "submittedAt": "2026-10-15T21:00:00+08:00",
    "withdrawnAt": null
  }
}
```
`record` is `null` before the first submission. **This is the only endpoint that returns a starting location, and only the caller's own.** No coordinates are returned (not needed).

#### 14. `PUT /api/sessions/{id}/my-response` (submit or edit)
Request:
```json
{
  "intervals": [ { "start": "2026-11-07T09:00:00+08:00", "end": "2026-11-07T13:00:00+08:00" } ],
  "calendarAssisted": false,
  "transportMode": "PUBLIC_TRANSPORT",
  "location": { "inputType": "POSTAL_CODE", "input": "640123", "candidateId": "loc-7f…" },
  "confirmUnavailable": false
}
```
- `intervals` are the caller's **AVAILABLE** blocks: half-open `[start, end)`, aligned to the grid slot (30 min for now, `SLOT_MINUTES`; see open question 11), each inside one day's `dailyStartTime`–`dailyEndTime` within the date range. The frontend merges adjacent cells into intervals.
- The full record is replaced (PUT semantics). It becomes the Participant's single active record (§5.5).
- `location.candidateId` comes from #16. The backend uses its cached geocode, so no second OneMap call is needed.
- `location` is **required on the first submission** but **optional on an edit**: omit it to keep the saved location. Without this, editing your times would force you to look up your address again.
- Empty `intervals` requires `confirmUnavailable: true` (UC-06.AC.1); otherwise `422 fields.intervals`.
- Sets `responseStatus = SUBMITTED`, marks results stale (UC-07 step 5), and re-evaluates attendance (FR-C2).

`200` `MyResponse` (as #13). `409 SESSION_CLOSED` after the deadline (UC-07.EX.1). `422` fields: `intervals`, `transportMode`, `location`.

#### 15. `POST /api/sessions/{id}/my-response/withdraw`
Body `{}`. `200` `MyResponse` with `responseStatus: WITHDRAWN`, `record.recordStatus: WITHDRAWN`. Must remove the record atomically from any in-progress scoring (NFR-11). `409 SESSION_CLOSED` after the deadline.

#### 16. `POST /api/locations/search` (UC-08)
POST, so the address stays out of URLs and logs. Request `{ "query": "640123" }`. `200`:
```json
{
  "status": "RECEIVED",
  "inputType": "POSTAL_CODE",
  "candidates": [
    { "candidateId": "loc-7f…", "label": "Blk 123 Jurong West Street 41, Singapore 640123", "postalCode": "640123" }
  ]
}
```
- `candidates: []` with `status: RECEIVED` means no match (FR-B3.1, UC-08.AC.1). The frontend asks the user to re-enter.
- `status: UNAVAILABLE` means OneMap is unreachable (UC-08.EX.1). The frontend shows "Location lookup is unavailable" with Retry.
- `candidateId` is opaque and short-lived (e.g. 30 min), bound to the caller.

**Mock-only dev triggers:** a query containing `offline` returns `UNAVAILABLE`; one containing `zzz` returns no candidates.

### 4.6 Response status (UC-03)

#### 17. `GET /api/sessions/{id}/responses`
`200`:
```json
{
  "participants": [
    { "participantId": "p-1", "displayName": "Wei Jie", "role": "ORGANISER", "responseStatus": "SUBMITTED", "updatedAt": "2026-10-15T21:00:00+08:00" },
    { "participantId": "p-7", "displayName": "Priya", "role": "PARTICIPANT", "responseStatus": "NOT_SUBMITTED", "updatedAt": null }
  ],
  "counts": { "NOT_SUBMITTED": 2, "SUBMITTED": 5, "WITHDRAWN": 1 },
  "refreshedAt": "2026-10-16T10:00:00+08:00"
}
```
Display names only: **no email, no location**. "Not yet" means joined but not submitted (see open question 19).

### 4.7 Recommendations (UC-09 to UC-12)

```ts
interface RankedCombination {
  combinationId: string
  rank: number                                       // 1 = best
  venue: VenueSummary
  start: string; end: string
  feasibilityStatus: 'FEASIBLE' | 'DATA_UNAVAILABLE'
  attendeeCount: number
  combinedScore: number                              // 0–100
  attendanceScore: number; travelScore: number       // 0–100 (normalisation is TBD-15)
  totalTravelMinutes: number | null                  // null if any routing failed
  averageTravelMinutes: number | null
  maxTravelMinutes: number | null
  explanation: string                                // UC-11 step 4, user-facing
  attendees: { participantId: string; displayName: string; transportMode: TransportMode;
               travelMinutes: number | null; routingStatus: RoutingStatus }[]   // FR-E2
  absentees: { participantId: string; displayName: string;
               attendanceStatus: 'UNAVAILABLE' | 'NO_RESPONSE' | 'WITHDRAWN' }[]  // FR-E3
}

interface RecommendationSet {
  sessionId: string
  generatedAt: string
  stale: boolean                                     // UC-11.AC.1
  travelObjective: TravelObjective
  attendanceWeightPercent: number
  combinations: RankedCombination[]                  // best first; top N (we suggest 10)
  excludedCounts: { BELOW_THRESHOLD?: number; JOURNEY_LIMIT?: number; GROUP_SIZE?: number; BOOKING_LEAD_TIME?: number }
}
```

#### 18. `GET /api/sessions/{id}/recommendations`
`200` `RecommendationSet`, ranked under the Session's **current** objective and weighting. `404 NOT_FOUND` if never generated (the frontend shows "Generate" instead). Any member may read (UC-11); only the Organiser can confirm.

#### 19. `POST /api/sessions/{id}/recommendations` (UC-09, UC-10)
Body `{}`. Runs candidate generation, feasibility, routing and scoring, then returns `200` `RecommendationSet` with `stale: false`. Must finish within the NFR-1 budget (≤ 5 s p95 after routing). If it can't, tell us and we'll switch to `202` plus polling.
- `409 NO_RESPONSES`, `409 NO_FEASIBLE_TIMESLOT` (UC-09.AC.1), `409 SESSION_CLOSED`.
- `503 EXTERNAL_SERVICE_UNAVAILABLE` if OneMap is entirely down (UC-09.EX.1). Partial routing failures are **not** errors: return those combinations with `DATA_UNAVAILABLE` and `travelMinutes: null` (NFR-3).
- Excluded combinations are not listed, only counted in `excludedCounts`.

#### 20. `POST /api/sessions/{id}/confirm` (UC-12)
Request `{ "combinationId": "c-…" }`. `200` `SessionDetail` with `status: CONFIRMED` and `confirmed` filled in.
- `409 RECOMMENDATIONS_STALE` if results are missing or stale; `409 COMBINATION_NOT_FEASIBLE` if the option isn't `FEASIBLE` or isn't from the current set; `409 SESSION_CLOSED` if not `ACTIVE`.
- Side effects: FR-B10 (delete non-selected holds) and FR-E6 (confirmed events). Calendar failures must **not** fail the confirmation (open question 21).
- The frontend shows the "booking is the group's responsibility" statement before calling this (UC-12 step 3).

### 4.8 Google Calendar (FR-B8, separate grant from sign-in)

#### 21. `GET /api/calendar/connection`
`200` `{ "status": "CONNECTED" }`.

#### 22. `GET /api/calendar/google/connect?next=/join/...`
A **full-page navigation**. Requests the separate Calendar grant (free/busy read plus the minimum event scope agreed in TBD-12), then redirects to `next` (relative paths only). The frontend never puts a token in `next`; it returns to an id-based path. Declined: redirect to `next?calendar=declined`; the frontend falls back to manual entry (FR-B8.1).

#### 23. `DELETE /api/calendar/connection`
`204`. Revokes the grant and deletes stored credentials.

#### 24. `POST /api/sessions/{id}/calendar-busy`
Body `{}`. `200`:
```json
{ "status": "RECEIVED", "busy": [ { "start": "2026-11-07T10:00:00+08:00", "end": "2026-11-07T11:30:00+08:00" } ] }
```
Busy blocks within the Session's range only: **start and end times, nothing else** (NFR-14). `status: UNAVAILABLE` or `ERROR` if Google fails (NFR-3). `409 CALENDAR_NOT_CONNECTED`. Busy blocks are only displayed; the user's selection is what gets submitted in #14 (`calendarAssisted: true`).

---

## 5. Open questions (from the frontend's SRS review)

Each has the frontend's current default in **bold**. Please confirm or change it.

1. **No screen for Manage/Cancel Session (UC-02/04) in §3.1.** **Edit and Cancel live on the Organiser's Response status screen.**
2. **No screen for Manage Response (UC-07).** **Reopening the invitation link shows your response with Edit and Withdraw.**
3. **The Dialog Map is stale:** it shows Signup and "enter name", from the old no-account design. **We follow SRS v2.0 (Google only).**
4. **Profile screen unspecified.** **Display name, Calendar connection and sign out.**
5. **Organiser as participant.** §5.5 says the Organiser responds too. **#6 makes the Organiser a NOT_SUBMITTED participant.**
6. **"Your sessions" groups miss cancelled and "responded, waiting" sessions.** **The frontend adds "Waiting" and "Cancelled" groups.**
7. **Session name** appears in UC-01 and the mockups but not in FR-A1 or B.3.2. **Added `name`.**
8. **Date range: dates or date-times?** The UI collects dates; B.3.2 says DateTime. **`startDate`/`endDate` plus the daily window.** DateRangeStart/End = `startDate`+`dailyStartTime` .. `endDate`+`dailyEndTime`.
9. **No daily time window.** A 24 h grid at 30 min slots is 48 rows per day, unusable at 375 px. **Proposed `dailyStartTime`/`dailyEndTime` on Session.** Needs a team decision.
10. **Timezone never captured.** **Optional on create; defaults to Asia/Singapore.**
11. **Grid slot vs TBD-13.** The frontend grid uses a single constant `SLOT_MINUTES = 30`. Durations like 45 min don't align with it. Is the candidate start step (TBD-13) also 30 min?
12. **Manual vs calendar conflicts.** **Manual selection wins; busy blocks are display-only.**
13. **Location step.** UC-08 picks from matches, hence #16. "Building name" isn't a `LocationInputType`: **classified as ADDRESS.** Should a default location persist on the User Account (TBD-6)? **Not for now.**
14. **Activity catalogue** isn't defined in the SRS. **#4 is served from the ActivityType table.**
15. **When are recommendations generated?** §4.3.1 says "once at creation"; UC-09 says on demand; TBD-14 is open. **On demand (#19), with a `recommendationsStale` flag.** Can the Organiser generate before the deadline? **Yes.**
16. **Where the weighting control lives** (§3.1 says Response status; the Dialog Map says Results). **Both; it's one PATCH.**
17. **UC-12 step 6 "booking link"** contradicts §1.4 and Venue has no URL field. **Omitted.** The "court or field" shown in §3.1 also has no field. **Omitted.**
18. **FR-E1 map pin** would need a client-side map provider, which §2.1 rules out. **Address plus an "Open in Google Maps" link** (a plain hyperlink, not an API call). A backend-proxied static map image could come later.
19. **"Invited" isn't defined** (link-based invites). **"Not yet" = joined but not submitted.**
20. **Sign-in before or after seeing the Session?** UC-05 shows Session info at step 3, before sign-in at step 4; C5 and §3.1 require sign-in first. **Sign-in first.**
21. **Calendar write failure at confirm** is unspecified (UC-12 notes). **Confirmation succeeds; the calendar error is reported separately.** Should `ConfirmedPlan` carry a per-attendee calendar status?
22. **CSRF strategy**: see §1.
