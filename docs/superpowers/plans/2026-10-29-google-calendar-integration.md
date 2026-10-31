# Google Calendar Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the SRS v2.2 Google Calendar flow end to end: separate consent, private busy import, transparent candidate holds, confirmed events, cleanup, visible partial failures, and idempotent retry.

**Architecture:** Keep Google sign-in unchanged and add a separate browser-bound Calendar OAuth client. Store one encrypted refresh token per user in PostgreSQL, reference it from all of that user's participant connections, and isolate Google HTTP calls behind `CalendarPort`; core scheduling commits succeed before best-effort Calendar reconciliation. The React app consumes provider-neutral connection, busy-interval, and sync-summary APIs.

**Tech Stack:** Python 3.12, FastAPI, SQLModel/SQLAlchemy, Alembic, PostgreSQL, `httpx`, `cryptography.fernet`, pytest; React 19, TypeScript, TanStack Query, MSW; Render Docker deployment.

**Spec:** `docs/superpowers/specs/2026-10-29-google-calendar-integration-design.md`

## Global Constraints

- Keep identity login scopes exactly `openid email profile`; Calendar consent is a separate transaction.
- Calendar consent requests only `openid`, `email`, `https://www.googleapis.com/auth/calendar.freebusy`, and `https://www.googleapis.com/auth/calendar.app.created`.
- Bind Calendar consent to the same Google `sub` as the signed-in account; never accept a different Google account.
- Never persist plaintext refresh/access tokens or expose them in URLs, API responses, ordinary logs, fixtures, or committed configuration.
- Query free/busy only for `primary`; never call an event-list/content-read endpoint.
- Write only to the application-created `Group Scheduler` secondary calendar.
- Tentative holds are private and transparent; confirmed events are private and opaque.
- Calendar errors never roll back manual availability, recommendations, or a confirmed plan.
- All provider writes and retries are idempotent, with deterministic Google-compatible event IDs.
- The feature is gated by `GOOGLE_CALENDAR_ENABLED`; rollback leaves the additive schema in place and manual scheduling usable.

## Review Focus

- A Calendar callback completed under a different Google account must discard the grant and leave the current connection unchanged (Task 2 tests).
- A reconnect response that omits `refresh_token` must preserve the existing encrypted token only for the same verified subject, otherwise fail safely (Task 2 tests).
- A deleted secondary calendar must be recreated once and the idempotent event operation retried without duplication (Task 4 tests).
- Confirmation with a mixture of connected, disconnected, attending, and non-attending users must delete every inappropriate hold and report exact counts (Task 6 tests).
- Retry must let an organiser reconcile the whole Session but restrict an ordinary participant to their own connection (Task 6 tests).

---

### Task 1: Encrypted user-level Calendar credential storage

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/models/domain.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/repositories/aggregates.py`
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/calendar_credentials.py`
- Create: `backend/migrations/versions/c9d4e5f6a7b8_add_calendar_credentials.py`
- Create: `backend/tests/test_calendar_credentials.py`
- Modify: `backend/tests/test_production_runtime.py`

**Interfaces:**
- Produces: `CalendarCredential` with one row per `user_account_id`, encrypted refresh token, secondary calendar ID, normalized scopes, status, and lifecycle timestamps.
- Produces: `CalendarCredentialVault.store(...) -> CalendarCredential`, `refresh_token(credential_reference: str) -> str`, `disconnect(...) -> None`, and `reference(credential_id: UUID) -> str` using `db:<uuid>` references.
- Produces: settings `google_calendar_enabled`, `google_calendar_redirect_uri`, `google_calendar_credential_key`, and `google_calendar_oauth_transaction_cookie_name`.

- [ ] **Step 1: Write failing credential-vault, model, migration, and production-config tests**

  Assert Fernet round-trip, ciphertext does not contain plaintext, malformed references/keys fail closed, one credential exists per account, `CalendarEvent.candidate_timeslot_id` permits confirmed-event bookkeeping, and production validation requires Calendar redirect/key only when the feature flag is enabled.

- [ ] **Step 2: Run the focused tests and verify they fail**

  Run: `cd backend && pytest -q tests/test_calendar_credentials.py tests/test_production_runtime.py`
  Expected: FAIL because the model, settings, vault, and migration do not exist.

- [ ] **Step 3: Implement the additive schema, vault, repository methods, and settings**

  Use `cryptography.fernet.Fernet`; normalize scopes by sorted unique values; preserve the non-secret `google_calendar_id` on disconnect; make `CalendarEvent.candidate_timeslot_id` nullable and name its uniqueness constraint explicitly for migration safety.

- [ ] **Step 4: Run the focused tests and migration smoke check**

  Run: `cd backend && pytest -q tests/test_calendar_credentials.py tests/test_production_runtime.py && alembic upgrade head`
  Expected: PASS and Alembic reaches `c9d4e5f6a7b8`.

- [ ] **Step 5: Commit**

  `git commit -m "feat: add encrypted calendar credential vault"`

### Task 2: Separate browser-bound Calendar OAuth

**Files:**
- Create: `backend/app/adapters/google_calendar_oauth.py`
- Modify: `backend/app/controllers/web_api.py`
- Modify: `backend/app/services/calendar_service.py`
- Modify: `backend/app/core/security.py`
- Create: `backend/tests/test_google_calendar_oauth.py`
- Modify: `backend/tests/test_web_integration.py`

**Interfaces:**
- Consumes: `CalendarCredentialVault` and user `provider_user_id` from Task 1.
- Produces: `GoogleCalendarOAuthClient.begin(account_id: UUID, provider_subject: str, next_path: str) -> GoogleCalendarOAuthStart` and async `complete(code, returned_state, transaction_cookie) -> GoogleCalendarGrant`.
- Produces: `GET /api/calendar/google/connect`, `GET /api/calendar/google/callback`, user-level `GET /api/calendar/connection`, and best-effort `DELETE /api/calendar/connection`.

- [ ] **Step 1: Write failing OAuth client tests**

  Assert exact scopes and offline parameters, PKCE/state/account binding, safe `/profile` and Session return paths, rejection of invitation-token/open redirects, decline handling, missing/expired/reused cookie handling, missing scopes, wrong Google subject, token secrecy, and preservation of an existing refresh token when Google omits it on same-subject reconnect.

- [ ] **Step 2: Run OAuth tests and verify they fail**

  Run: `cd backend && pytest -q tests/test_google_calendar_oauth.py`
  Expected: FAIL because Calendar OAuth is unimplemented.

- [ ] **Step 3: Implement the Calendar OAuth client and web endpoints**

  Sign a separate ten-minute HttpOnly/Secure/SameSite=Lax transaction cookie, validate the ID token with the existing verifier pattern, upsert the user credential, propagate `db:<uuid>` to every existing participant connection, clear the transaction cookie on every callback outcome, and keep sign-in untouched.

- [ ] **Step 4: Add integration tests for connect, decline, callback, status, reconnect, profile return, propagation, and disconnect**

  Stub only the OAuth boundary; assert no token appears in responses and a provider failure leaves manual scheduling available.

- [ ] **Step 5: Run OAuth and web integration tests**

  Run: `cd backend && pytest -q tests/test_google_calendar_oauth.py tests/test_web_integration.py`
  Expected: PASS.

- [ ] **Step 6: Commit**

  `git commit -m "feat: add separate Google Calendar consent flow"`

### Task 3: Google token refresh and privacy-safe free/busy import

**Files:**
- Modify: `backend/app/adapters/ports.py`
- Replace: `backend/app/adapters/google_calendar_adapter.py`
- Modify: `backend/app/services/calendar_service.py`
- Modify: `backend/app/controllers/web_api.py`
- Create: `backend/tests/test_google_calendar_adapter.py`
- Modify: `backend/tests/test_web_integration.py`

**Interfaces:**
- Consumes: credential references and encrypted refresh-token lookup from Task 1.
- Produces: `CalendarBusyInterval(start: datetime, end: datetime)` and `CalendarPort.free_busy(credential_reference, start, end, timezone) -> tuple[CalendarBusyInterval, ...]`.
- Produces: `POST /api/sessions/{session_id}/calendar-busy -> {status, busy}`.

- [ ] **Step 1: Write failing adapter tests for refresh and free/busy**

  Cover token success/cache safety margin, timeout, 429, 5xx, `invalid_grant`, clipping and merging overlaps, ignoring non-time provider fields, querying only calendar `primary`, and absence of event-list requests.

- [ ] **Step 2: Run adapter tests and verify they fail**

  Run: `cd backend && pytest -q tests/test_google_calendar_adapter.py`
  Expected: FAIL because the adapter still raises unconfigured errors.

- [ ] **Step 3: Implement access-token refresh and free/busy parsing**

  Use `httpx.AsyncClient`, sanitized provider exceptions, an in-memory token cache keyed by credential ID, and a callback that marks credentials/connections `EXPIRED` on `invalid_grant` without logging response bodies.

- [ ] **Step 4: Implement the async busy-import endpoint and fallback semantics**

  Resolve the current participant connection, compute Session bounds in its timezone, return `RECEIVED` on success, `UNAVAILABLE` with an empty list for transient Google errors, and 409 for missing/expired authorization.

- [ ] **Step 5: Run adapter, Calendar, and privacy tests**

  Run: `cd backend && pytest -q tests/test_google_calendar_adapter.py tests/test_calendar_and_privacy.py tests/test_web_integration.py`
  Expected: PASS.

- [ ] **Step 6: Commit**

  `git commit -m "feat: import private Google Calendar busy intervals"`

### Task 4: Dedicated secondary calendar and idempotent event operations

**Files:**
- Modify: `backend/app/adapters/ports.py`
- Modify: `backend/app/adapters/google_calendar_adapter.py`
- Modify: `backend/app/services/calendar_service.py`
- Modify: `backend/tests/test_google_calendar_adapter.py`
- Create: `backend/tests/test_calendar_sync_service.py`

**Interfaces:**
- Produces: `CalendarEventInput` with title, start/end, timezone, transparency, optional location, and private metadata.
- Produces: `CalendarPort.ensure_app_calendar(...) -> str`, `upsert_event(credential_reference, idempotency_key, event: CalendarEventInput) -> str`, `delete_event(...) -> None`, and `revoke(...) -> None`.
- Produces: deterministic Google event IDs and service methods that reject deletion unless an owned `CalendarEvent` row supplies the provider ID.

- [ ] **Step 1: Write failing event-operation tests**

  Assert `Group Scheduler` creation, transparent tentative and opaque confirmed payloads, private visibility/metadata, deterministic IDs, 404 delete idempotency, owned-row deletion guard, and one-time calendar recreation/retry after a missing-calendar response.

- [ ] **Step 2: Run focused tests and verify they fail**

  Run: `cd backend && pytest -q tests/test_google_calendar_adapter.py tests/test_calendar_sync_service.py`
  Expected: FAIL because event operations and app-calendar creation are absent.

- [ ] **Step 3: Implement app-calendar creation, event upsert/delete, deterministic IDs, and revocation**

  Persist/reuse `google_calendar_id`, write only to that ID, and treat an already-deleted provider event as success.

- [ ] **Step 4: Run focused tests**

  Run: `cd backend && pytest -q tests/test_google_calendar_adapter.py tests/test_calendar_sync_service.py`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `git commit -m "feat: manage app-owned Google Calendar events"`

### Task 5: Reconcile transparent tentative holds after recommendation generation

**Files:**
- Modify: `backend/app/services/integrated_recommendation_service.py`
- Modify: `backend/app/services/calendar_service.py`
- Modify: `backend/app/repositories/aggregates.py`
- Modify: `backend/tests/test_calendar_sync_service.py`
- Modify: `backend/tests/test_candidate_and_scoring.py`

**Interfaces:**
- Consumes: event operations from Task 4.
- Produces: async `CalendarSyncService.reconcile_holds(db, session_id, candidate_timeslot_ids) -> CalendarSyncSummary` called only after recommendation persistence commits.

- [ ] **Step 1: Write failing hold-reconciliation tests**

  Assert one transparent hold per connected participant/candidate, idempotent reruns, deletion of obsolete holds, no holds for disconnected users, isolated per-event failures recorded as sanitized `ERROR`, and successful recommendations even when every Google call fails.

- [ ] **Step 2: Run focused tests and verify they fail**

  Run: `cd backend && pytest -q tests/test_calendar_sync_service.py tests/test_candidate_and_scoring.py`
  Expected: FAIL because only placeholder database rows are written.

- [ ] **Step 3: Replace placeholder hold rows with post-commit provider reconciliation**

  Keep recommendation ranking provider-neutral; commit the core result first, then upsert/delete Calendar events and commit only their statuses in a separate transaction boundary.

- [ ] **Step 4: Run focused tests**

  Run: `cd backend && pytest -q tests/test_calendar_sync_service.py tests/test_candidate_and_scoring.py`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `git commit -m "feat: reconcile tentative calendar holds"`

### Task 6: Confirmed-event synchronization, cleanup, summary, and retry

**Files:**
- Modify: `backend/app/services/web_contract_service.py`
- Modify: `backend/app/services/calendar_service.py`
- Modify: `backend/app/controllers/web_api.py`
- Modify: `backend/app/repositories/aggregates.py`
- Modify: `backend/tests/test_calendar_sync_service.py`
- Modify: `backend/tests/test_web_integration.py`

**Interfaces:**
- Produces: `CalendarSyncSummary(succeeded: int, failed: int, not_connected: int, can_retry: bool)` serialized as camelCase.
- Produces: async `CalendarSyncService.sync_confirmed(db, user, session_id, own_only=False) -> CalendarSyncSummary` and `POST /api/sessions/{session_id}/calendar-sync`.

- [ ] **Step 1: Write failing confirmation/retry tests**

  Cover attendees versus non-attendees, selected promotion/upsert, deletion of every inappropriate hold, partial provider failure after successful core confirmation, exact summary counts, idempotent retry, organiser-all scope, participant-own scope, and rejection before Session confirmation.

- [ ] **Step 2: Run focused tests and verify they fail**

  Run: `cd backend && pytest -q tests/test_calendar_sync_service.py tests/test_web_integration.py`
  Expected: FAIL because confirmation currently writes placeholder rows and has no retry endpoint.

- [ ] **Step 3: Commit the Session confirmation first, then reconcile calendars**

  Remove `_sync_confirmed_calendar_events`; make the controller async, call provider sync after the core commit, and attach the non-blocking summary to the returned confirmed plan/session projection.

- [ ] **Step 4: Implement scoped, idempotent post-confirmation retry and sync-summary projection**

  The organiser retries all pending/error operations; a participant reconciles only their connection. `canRetry` is true only when the caller may retry at least one failed operation.

- [ ] **Step 5: Run focused tests**

  Run: `cd backend && pytest -q tests/test_calendar_sync_service.py tests/test_web_integration.py`
  Expected: PASS.

- [ ] **Step 6: Commit**

  `git commit -m "feat: sync confirmed plans to Google Calendar"`

### Task 7: Frontend connection recovery and Calendar sync feedback

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/hooks/calendar.ts`
- Modify: `frontend/src/api/queryKeys.ts`
- Modify: `frontend/src/pages/AvailabilityPage.tsx`
- Modify: `frontend/src/components/CalendarImport.tsx`
- Modify: `frontend/src/pages/ConfirmedPage.tsx`
- Modify: `frontend/src/pages/ConfirmedPage.css`
- Modify: `frontend/src/mocks/db.ts`
- Modify: `frontend/src/mocks/handlers.ts`

**Interfaces:**
- Consumes: connection status, busy import, confirmed-plan `calendarSync`, and retry endpoint from Tasks 2, 3, and 6.
- Produces: `useRetryCalendarSync(sessionId)` and explicit declined, expired/reconnect, unavailable, partial-failure, and retry UI states.

- [ ] **Step 1: Extend TypeScript contracts and MSW fixtures with Calendar sync summaries/retry**

  Keep mocks idempotent and model organiser-all versus participant-own retry without exposing provider details.

- [ ] **Step 2: Implement query invalidation, OAuth-return notices, and retry hook**

  Preserve the existing availability draft before redirect; parse `calendar=declined|unavailable|wrong-account|missing-scopes` into neutral user copy while manual selection remains editable.

- [ ] **Step 3: Render confirmed-plan sync status and scoped retry action**

  Always lead with the confirmed-plan success; show counts and **Retry calendar sync** only when `canRetry` is true.

- [ ] **Step 4: Run frontend checks**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: both commands exit 0.

- [ ] **Step 5: Commit**

  `git commit -m "feat: show calendar connection and sync recovery states"`

### Task 8: Deployment configuration, runbook, and release verification

**Files:**
- Modify: `render.yaml`
- Modify: `backend/tests/test_render_deployment.py`
- Modify: `README.md`
- Create: `docs/google-calendar-deployment.md`
- Modify: `docs/superpowers/specs/2026-10-29-google-calendar-integration-design.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a repeatable disabled-first Render rollout, Google Cloud callback/scope/test-user instructions, seven-day Testing warning, smoke test, rollback, and no-secret configuration surface.

- [ ] **Step 1: Write failing Render blueprint assertions**

  Require `GOOGLE_CALENDAR_ENABLED=false`, synced `GOOGLE_CALENDAR_REDIRECT_URI`, generated/synced `GOOGLE_CALENDAR_CREDENTIAL_KEY`, and the separate Calendar OAuth cookie name without committed secret values.

- [ ] **Step 2: Run deployment tests and verify they fail**

  Run: `cd backend && pytest -q tests/test_render_deployment.py`
  Expected: FAIL because the Calendar environment variables are absent.

- [ ] **Step 3: Update Render configuration and deployment documentation**

  Document enabling the Calendar API, exact callback URI, exact scopes, test users, Fernet key generation, migration-before-flag order, seven-day Testing-token expiry, live two-user acceptance, disable rollback, and post-assessment cleanup.

- [ ] **Step 4: Mark the approved design status and run all backend tests**

  Run: `cd backend && pytest -q`
  Expected: all tests pass.

- [ ] **Step 5: Run frontend and repository verification**

  Run: `cd frontend && npm run lint && npm run build`
  Run: `git diff --check && git status --short`
  Expected: lint/build pass, no whitespace errors, and only intentional files remain.

- [ ] **Step 6: Commit documentation and deployment configuration**

  `git commit -m "docs: add Google Calendar deployment runbook"`

- [ ] **Step 7: Request whole-branch code review, fix findings, rerun verification, and push**

  Run the `superpowers:requesting-code-review` and `superpowers:verification-before-completion` skills, reconcile the branch with `origin/feature/production-pilot` without dropping either side's commits, then push `feature/production-pilot` to `origin`.

