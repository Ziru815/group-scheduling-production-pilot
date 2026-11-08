# Google Calendar Integration Design

**Date:** 2026-10-29  
**Status:** Implemented
**Target branch:** `feature/production-pilot`

## 1. Intent

Complete the Google Calendar functionality required by SRS v2.2 without weakening the existing Google sign-in flow or the privacy boundary around calendar data. The implementation must give a participant a real, optional Calendar connection; import only busy intervals; create non-blocking tentative holds; remove unselected holds; and create the final confirmed event for attending participants.

This closes FR-B8, FR-B8.1, FR-B9, FR-B9.1, FR-B10, FR-E6, NFR-3, NFR-7, NFR-14, and the Calendar portion of NFR-15. Manual availability remains a complete fallback.

## 2. Goals

- Keep Google identity sign-in and Google Calendar consent as separate OAuth flows.
- Request only `calendar.freebusy` and `calendar.app.created` Calendar scopes.
- Support offline access through refresh tokens kept in encrypted backend storage.
- Import only start/end busy intervals from the user's primary calendar.
- Create all application-owned events in a dedicated secondary calendar owned by the user.
- Create tentative holds as transparent events so they never mark the participant busy.
- Delete non-selected tentative holds when a final plan is confirmed.
- Create or promote one opaque confirmed event containing the chosen venue and time.
- Make Calendar failures visible while allowing manual availability and plan confirmation to continue.
- Preserve the current same-origin Render deployment and PostgreSQL database.

## 3. Non-goals

- Reading event titles, descriptions, attendees, locations, or other Calendar content.
- Writing to or modifying unrelated events in the user's primary calendar.
- Supporting Outlook, Apple Calendar, or any provider other than Google Calendar.
- Sending email, push, or SMS notifications.
- Background calendar synchronization, webhooks, or periodic polling.
- Completing Google's public OAuth verification process as part of the code change.
- Changing the existing Google identity login scopes or session-cookie design.

## 4. Approaches considered

### A. Dedicated secondary calendar plus encrypted PostgreSQL credential vault — selected

Use a separate Calendar OAuth grant. The backend stores the refresh token encrypted in an additive credential-vault table and keeps only a credential reference on `CalendarConnection`. On first connection it creates a user-owned secondary calendar named **Group Scheduler**. All tentative and confirmed events are written only to that calendar.

This uses the existing Render and PostgreSQL services, satisfies the SRS reference-only credential model, and works with Google's narrow `calendar.app.created` scope.

### B. Dedicated secondary calendar plus Google Secret Manager

Store each user's refresh token in Google Secret Manager and keep its resource name in PostgreSQL. This has a stronger external-vault boundary but adds another cloud account, IAM policy, API, cost surface, and operational dependency. It is disproportionate for a one-month assessment deployment.

### C. Write directly to the primary calendar — rejected

Using broader event scopes against the primary calendar would make implementation simpler, but it would grant access beyond events created by this application and conflict with NFR-14. It is not an acceptable implementation of the approved SRS.

## 5. OAuth and authorization design

### 5.1 Separation from sign-in

The existing `/api/auth/google/login` and callback continue to request only `openid email profile`. Calendar authorization uses new endpoints and a separate short-lived transaction cookie. Calendar failure or refusal never signs the user out.

### 5.2 Authorization request

`GET /api/calendar/google/connect?next=<relative-path>` will:

1. Require the existing application session.
2. Validate `next` as a same-origin relative path. `/profile` and ID-based Session paths are allowed; invitation tokens are not accepted in the return path.
3. Generate random state and a PKCE verifier/challenge.
4. Store a signed, HTTP-only, Secure, SameSite=Lax transaction cookie containing the state, current account ID, PKCE verifier, safe return path, and a ten-minute expiry.
5. Redirect to Google's authorization endpoint with:
   - `openid` and `email`, solely to verify that Calendar consent belongs to the same Google subject as the signed-in User Account
   - `https://www.googleapis.com/auth/calendar.freebusy`
   - `https://www.googleapis.com/auth/calendar.app.created`
   - `access_type=offline`
   - `include_granted_scopes=true`
   - `prompt=consent` when connecting or reconnecting so the backend receives a refresh token.

### 5.3 Callback

`GET /api/calendar/google/callback` will:

1. Require and consume the Calendar transaction cookie.
2. Reject missing, expired, reused, or mismatched state and account identity.
3. Handle `access_denied` by redirecting to `next?calendar=declined` without changing manual availability.
4. Exchange the authorization code on the backend using the exact registered redirect URI and PKCE verifier.
5. Validate the returned Google ID token and require its subject to match the Google subject already bound to the signed-in User Account. A user cannot attach a different Google account's calendar; switching accounts requires signing in as that account.
6. Verify that both required Calendar scopes were granted.
7. Encrypt and upsert the refresh token in the credential vault.
8. Reuse the previously created secondary calendar when accessible, otherwise create `Group Scheduler` with the Session timezone defaulting to `Asia/Singapore`.
9. Mark all existing `Participant` records for that user as connected to the same credential reference.
10. Clear the transaction cookie and redirect to the safe return path.

The application never puts Google tokens in URLs, frontend state, API responses, ordinary logs, or `CalendarConnection`.

## 6. Credential-vault and persistence design

Add an additive `calendar_credentials` table:

- `credential_id` UUID primary key.
- `user_account_id` UUID unique foreign key.
- `encrypted_refresh_token` encrypted text, nullable after disconnect or revocation.
- `google_calendar_id` ID of the application-created secondary calendar.
- `granted_scopes` normalized space-delimited string.
- `status` (`CONNECTED`, `EXPIRED`, `DISCONNECTED`, `ERROR`).
- `created_at`, `updated_at`, and optional `revoked_at` timestamps.

`CalendarConnection.credential_reference` stores `db:<credential_id>` only. One user-level credential can be referenced by that user's Participant records across multiple Sessions.

Encryption uses Fernet authenticated encryption with a new Render secret, `GOOGLE_CALENDAR_CREDENTIAL_KEY`. Plaintext refresh tokens exist only in process memory during exchange or refresh. Access tokens are not persisted; they are refreshed on demand and may be cached in memory only until shortly before expiry.

Disconnect first makes a best-effort attempt to delete every outstanding tentative hold owned by the application, then attempts Google token revocation, clears the encrypted refresh token, marks every connection for that user `DISCONNECTED`, and preserves the non-secret secondary-calendar ID for reuse. Previously confirmed events remain in the user's calendar. Hold-cleanup failure is recorded but never prevents revocation; a leftover hold is transparent and therefore cannot block the user's time.

## 7. Google Calendar adapter

Implement the existing `CalendarPort` behind a real `GoogleCalendarAdapter` using `httpx` and documented Google endpoints.

### 7.1 Token refresh

- Decrypt the refresh token from the credential reference.
- Exchange it at `https://oauth2.googleapis.com/token` using the existing Google client ID and secret.
- Cache the access token in memory until its expiry safety margin.
- On `invalid_grant`, mark the credential and connections `EXPIRED`; the UI offers reconnect.
- Never log request authorization headers or token response bodies.

### 7.2 Free/busy import

Call `POST https://www.googleapis.com/calendar/v3/freeBusy` for calendar ID `primary`, bounded to the Session's first and last possible activity instants and using the Session timezone. Parse only the returned busy start and end values, clip them to the Session range, merge overlapping intervals, and return them to the frontend.

No event list endpoint is called. No titles, descriptions, attendees, or locations are read or stored. Imported busy intervals are displayed in the availability grid but are not persisted independently; only the participant's submitted availability and `CALENDAR_ASSISTED` source are stored.

### 7.3 Event upsert and deletion

All application events are written to the stored secondary-calendar ID.

- Tentative hold: private, `status=tentative`, `transparency=transparent`, no attendees, and private extended properties identifying the Session, candidate timeslot, and event type.
- Confirmed event: private, `status=confirmed`, `transparency=opaque`, summary `Group activity: <activity>`, location set to the confirmed public Venue address, and private extended properties identifying the Session and confirmed Combination.
- Event creation is idempotent. The backend uses a deterministic Google-compatible event ID derived from the connection, Session, timeslot, and event type. A repeated request updates the same event rather than creating a duplicate.
- Deletion acts only on provider IDs previously stored in `CalendarEvent` rows belonging to the same credential reference.

Tentative holds cannot appear in imported busy data because they are transparent and live in the application-created secondary calendar while free/busy import queries only `primary`. This directly enforces FR-B9.1 without reading event content.

## 8. Application flow

### 8.1 Connection status

`GET /api/calendar/connection` reports user-level status from `calendar_credentials`, with `DISCONNECTED` as the default. It no longer depends on whether the current page identifies one particular Session.

The Profile connection button therefore works. Session availability pages use the same status.

### 8.2 Import busy intervals

`POST /api/sessions/{session_id}/calendar-busy`:

1. Requires Session membership.
2. Resolves or creates that Participant's `CalendarConnection` from the user's connected credential.
3. Computes the Session import bounds.
4. Calls the adapter's free/busy method.
5. Returns `{status: "RECEIVED", busy: [...]}` on success.

Provider failure returns `{status: "UNAVAILABLE", busy: []}` and records a sanitized server-side error. Missing, expired, or disconnected authorization returns `409 CALENDAR_NOT_CONNECTED`; the frontend retains manual entry and offers reconnect.

### 8.3 Tentative holds

After each successful recommendation generation, the backend reconciles holds for every connected participant:

- Upsert one transparent hold for every candidate timeslot still under consideration.
- Retain/update matching holds from an earlier generation.
- Delete holds for timeslots no longer under consideration.
- Persist provider IDs and per-event status in `CalendarEvent`.

External Calendar calls are isolated per participant/event. Recommendation generation and ranking still succeed when Google is unavailable; failed rows are stored as `ERROR` with a sanitized `last_error`.

### 8.4 Final confirmation

When the organiser confirms a Combination:

- The database transaction confirms the Session and selected Combination first.
- For every attending participant with a connected calendar, upsert or promote the selected timeslot's event to the opaque confirmed event.
- For an attending participant, delete every non-selected tentative hold for that Session.
- For a non-attending participant, delete every tentative hold for that Session, including the selected timeslot.
- Mark successful rows `ACTIVE` or `DELETED`; mark provider failures `ERROR`.
- Return a non-blocking `calendarSync` summary (`succeeded`, `failed`, `notConnected`) so the UI can state that the plan is confirmed even when Calendar sync is incomplete.

Calendar failure never rolls back or hides the confirmed plan, satisfying NFR-3.

### 8.5 Retry after confirmation

`POST /api/sessions/{session_id}/calendar-sync` provides an explicit, idempotent retry after a Session is confirmed. The organiser may retry all failed or pending Calendar operations for the Session; an ordinary participant may retry only their own. The endpoint performs the same reconcile operation described above and returns the updated `calendarSync` summary. The final-plan UI shows **Retry calendar sync** only when the signed-in user can retry at least one failed operation.

Reconnecting a Calendar does not silently replay every historical Session. After reconnect, the affected final-plan page presents the explicit retry action so the user understands what will be written.

## 9. Frontend behavior

- Keep the current optional Calendar card and availability import control.
- Make the Profile connection flow valid instead of requiring a Session path.
- Restore unsaved availability selections after OAuth redirect using the existing draft mechanism.
- Show explicit states: connected, disconnected, declined, expired/reconnect, and provider unavailable.
- Render imported busy intervals distinctly and leave manual selection editable; manual choice remains authoritative.
- After final confirmation, show the calendar-sync summary without presenting a failed Calendar write as a failed Session confirmation.
- Show an explicit retry action for failed post-confirmation writes, scoped to the organiser's whole Session or the participant's own event.
- Never display Google tokens, raw provider messages, or unrelated event details.

## 10. Failure and recovery behavior

- OAuth refusal: return to manual availability with a neutral declined message.
- Different Google subject selected for Calendar consent: reject the binding, discard the returned token material, and ask the user to choose the same Google account used to sign in.
- Missing required scopes: mark `ERROR`, discard unusable token material, and offer reconnect.
- Refresh token revoked/expired: mark `EXPIRED`, return `CALENDAR_NOT_CONNECTED`, and offer reconnect.
- Google timeout, 429, or 5xx: return or record `UNAVAILABLE`; do not fail the core request.
- Secondary calendar deleted by the user: recreate it once and retry the idempotent operation.
- Event already deleted: treat delete as successful and mark the local event `DELETED`.
- Duplicate/retried requests: deterministic IDs and database uniqueness prevent duplicate events.

No background worker is introduced. Retry occurs through the next idempotent import or recommendation generation, or through the explicit post-confirmation Calendar-sync endpoint.

## 11. Configuration and deployment

New configuration:

- `GOOGLE_CALENDAR_ENABLED`
- `GOOGLE_CALENDAR_REDIRECT_URI`
- `GOOGLE_CALENDAR_CREDENTIAL_KEY`
- `GOOGLE_CALENDAR_OAUTH_TRANSACTION_COOKIE_NAME` (defaulted safely)

Deployment steps:

1. Enable Google Calendar API in the existing Google Cloud project.
2. Add the Calendar callback URI to the existing web OAuth client.
3. Add the two Calendar scopes to the consent configuration.
4. Add team accounts as test users while the app is in Testing.
5. Add the encryption key and callback URI to Render without exposing values in source or logs.
6. Run the additive database migration before enabling the feature flag.
7. Deploy disabled, run database/configuration checks, then enable and perform the live smoke test.

Google OAuth Testing authorizations, including refresh tokens for Calendar scopes, expire after seven days. For the assessment period, the team must either reauthorize test accounts within seven days of each rehearsal/presentation or publish the OAuth app to Production and accept the unverified-app warning until verification is completed. This is an operational constraint, not a code workaround.

Rollback sets `GOOGLE_CALENDAR_ENABLED=false`; manual availability and the existing sign-in flow continue working. The additive migration remains harmless.

## 12. Test strategy

### Unit tests

- Calendar OAuth URL has exact identity and Calendar scopes, PKCE, state, offline access, and safe redirect handling.
- Callback rejects missing, expired, mismatched, reused, and wrong-account transactions.
- Callback rejects a valid Calendar grant made by a Google subject different from the signed-in User Account.
- Credential encryption round-trips and plaintext never appears in stored columns or representations.
- Token refresh handles success, expiry, `invalid_grant`, timeout, 429, and 5xx.
- Free/busy parsing clips and merges intervals and ignores all non-time fields.
- Event payloads use the correct transparency, visibility, time zone, deterministic ID, and private metadata.
- Adapter never deletes an event not represented by an owned `CalendarEvent` row.

### Integration tests

- Connect, callback, status, disconnect, decline, and reconnect flows.
- Profile connection works without a Session ID.
- Busy import returns real-shaped intervals and manual fallback remains usable.
- Recommendation generation reconciles holds idempotently.
- Confirmation promotes/creates the selected event and deletes non-selected holds.
- Provider failures do not fail recommendation generation or confirmation.
- Disconnect cleans up outstanding holds best-effort and revokes access even when cleanup fails.
- Non-attendees retain no tentative hold after confirmation.
- Post-confirmation retry is idempotent and enforces organiser-versus-participant scope.
- Multiple Participant rows for one User Account share one credential reference.
- API responses and logs contain no refresh/access tokens.

### Frontend checks

- Connection state copy and reconnect paths.
- Draft restoration after redirect.
- Busy-grid rendering and manual override.
- Confirmation success with partial Calendar failure.
- Mobile layout at 375 px.

### Live acceptance test

Using two approved Google test users:

1. Connect calendars and verify the dedicated secondary calendar appears.
2. Add a known busy event to a primary calendar and verify only its interval is imported.
3. Generate recommendations and verify transparent tentative holds exist and do not block free/busy.
4. Confirm a plan and verify the selected event is opaque with the Venue/time while other holds are removed.
5. Revoke one user's grant and verify the application degrades to reconnect/manual entry without breaking the Session.

## 13. Acceptance criteria mapped to the SRS

- **FR-B8 / NFR-7:** a connected test user completes the OAuth flow and imports real busy intervals end to end.
- **FR-B8.1:** a user who declines or loses authorization completes manual availability normally.
- **FR-B9:** connected participants receive one hold per candidate timeslot still under consideration.
- **FR-B9.1:** holds are transparent and never reappear as imported busy intervals.
- **FR-B10:** all non-selected holds are removed after confirmation.
- **FR-E6:** each attending connected participant receives one confirmed Venue/time event.
- **NFR-3:** Calendar outage does not fail availability, recommendations, or confirmation and is visibly reported.
- **NFR-14:** the only Calendar scopes are `calendar.freebusy` and `calendar.app.created`; `openid email` is used only to bind the grant to the existing signed-in Google subject, and no event-content read endpoint is called.
- **NFR-15:** controllers and scoring remain provider-neutral behind `CalendarPort`.

## 14. Builder decisions left open

The implementer may choose internal class names, migration revision IDs, exact sanitized log wording, and whether the in-memory access-token cache is a small dedicated class or part of the adapter. These choices must not change the interfaces, security properties, failure behavior, or acceptance criteria above.
