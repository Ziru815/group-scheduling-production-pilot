# Group Scheduling Production Pilot Design

**Date:** 2026-10-27  
**Target demo video:** approximately 2026-11-10  
**Target presentation:** approximately 2026-11-17  
**Status:** Proposed for team approval  
**Source of truth:** SRS v2.2 and the current integrated prototype

## 1. Outcome and scope

Turn the current local demo into a short-lived but genuine public pilot that the project team and lecturer can use from separate devices and Google accounts. The pilot must preserve the core workflow already implemented: sign in, create or join a group, save personal inputs privately, generate recommendations, vote, and confirm a plan.

This release is not intended to become a permanently operated commercial service. It should nevertheless behave like a normal web product during the course assessment period: persistent users and data, real authentication, real Singapore venue records, live routing, HTTPS, controlled secrets, and a recoverable database.

### Included

- Google OpenID Connect login for every organiser and participant.
- Durable PostgreSQL storage and schema migrations.
- Real Singapore venue ingestion from an authorised government dataset.
- OneMap geocoding and routing for recommendation travel times.
- Public HTTPS deployment in Singapore.
- Production safety controls, deployment checks, backup, rollback, and an assessment runbook.

### Explicit non-goals for this deadline

- Live Google Calendar integration. Login and Calendar consent are separate concerns; Calendar can remain a documented boundary.
- Court booking, payments, real-time slot availability, email/SMS notifications, or a custom domain.
- Exhaustive coverage of every Singapore sports venue.
- Long-term high availability, autoscaling, or post-course operations.

## 2. Evidence from the existing system

The current project is a viable base rather than a throwaway mock:

- React/TypeScript/Vite frontend and FastAPI/SQLModel backend are already integrated.
- The backend already has Google OAuth routes, account persistence, and a signed application session cookie.
- A OneMap adapter already supports search and walk, drive, and public-transport routing.
- Recommendation and privacy boundaries already exist around persistent SQL models.
- PostgreSQL and Alembic are already represented in the repository.

The production gaps are specific:

- `DataGovSgAdapter` deliberately stops because the approved dataset and field mapping have not been implemented.
- The current seed catalogue is demo data and includes approximate or questionable venue/activity mappings.
- Venue recommendation always reads the database, so switching off mock providers alone does not create a real venue catalogue.
- Docker Compose currently enables debug authentication and mock providers.
- The OAuth flow needs stronger browser binding and replay protection before public deployment.
- The ZIP contains no Git history or installed runtime dependencies, so the earlier reported test results cannot yet be independently reproduced on this machine.

## 3. Options considered

### Delivery strategy

1. **Finish locally, deploy near the deadline.** Cheapest initially, but leaves OAuth redirect, HTTPS, database, and cloud-only failures until the riskiest week.
2. **Local development plus early public staging. Chosen.** Build and test locally, but publish a thin working version early and improve it continuously. This exposes deployment issues while there is still recovery time.
3. **Cloud-first development.** Closer to production at all times, but adds cost, slow feedback, and operational overhead for a three-week student project.

### Hosting architecture

1. **Separate frontend and backend services.** Conventional, but requires two deployments, CORS configuration, cross-site cookie decisions, and more resource usage.
2. **One application container plus managed PostgreSQL. Chosen.** A multi-stage build compiles React and FastAPI serves the static application and `/api` from the same HTTPS origin. This minimizes cost and removes most CORS/cookie failure modes.
3. **Full Google Cloud stack.** Technically suitable, but account setup, IAM, billing, and service choices are unnecessary complexity for this deadline.

### Venue data strategy

1. **Keep mock venue JSON.** Rejected because it does not meet the product intent or SRS live-data direction.
2. **Import every row from data.gov.sg.** Rejected because the source contains private residences, blank names, and records that are not necessarily public or bookable.
3. **Import real records, activate a verified public subset. Chosen.** Preserve source provenance, group and normalize government records, then expose only records that meet explicit verification rules. This is real data without pretending every dataset row is a usable venue.

## 4. Proposed architecture

```text
Browser
  | HTTPS, same origin
  v
Railway application service (Singapore)
  |- FastAPI /api
  |- built React SPA
  |- OAuth callback
  |- venue sync command
  |
  +---- private DATABASE_URL ----> Railway PostgreSQL
  |
  +---- HTTPS ----> Google OpenID Connect
  +---- HTTPS ----> data.gov.sg DataStore API
  +---- HTTPS ----> OneMap Search and Routing APIs
```

### Environment model

- **Local development:** Vite and FastAPI may run separately. SQLite, mock providers, and explicit debug personas may be used only in this environment.
- **Public assessment environment:** one Railway application service and one Railway PostgreSQL service in Singapore, using a Railway-generated HTTPS domain. No custom domain is required.
- Production configuration must set `DEBUG_AUTH_ENABLED=false`, `USE_MOCK_PROVIDERS=false`, secure cookies on, and automatic table creation off.
- Secrets are Railway environment variables and never enter source control, screenshots, logs, or the demo video.

### Repository and change safety

Before implementation, place the project in a private Git repository and make the imported ZIP the baseline commit. All schema and deployment work should occur on a feature branch so the current demo remains recoverable. The repository currently has no `.git` directory, so this is a prerequisite rather than a completed step.

## 5. Google login design

Use the existing server-side OpenID Connect authorization-code flow and harden it for a public browser:

1. User selects “Continue with Google.”
2. Backend creates a short-lived, one-time authorization transaction containing a random state, nonce, PKCE verifier/challenge, and safe post-login return path.
3. The transaction is bound to the initiating browser with a short-lived secure cookie or server-side record.
4. Google redirects only to the exact registered public callback URL.
5. Backend rejects missing, expired, reused, or mismatched state; exchanges the code using PKCE; validates issuer, audience, expiry, nonce, Google subject, and `email_verified`.
6. Backend upserts the account by `(provider, provider_subject)`, updates non-sensitive profile fields, and handles an existing same-email account explicitly rather than silently merging identities.
7. Backend issues the existing short-lived application session cookie with `HttpOnly`, `Secure`, and `SameSite=Lax`, then redirects to the validated relative path.

Only `openid email profile` scopes are requested. No Google Calendar scope or refresh token is required for this release. Debug persona endpoints must be unavailable in the public environment even if someone guesses their URLs.

## 6. Real venue catalogue design

### Authoritative source

Use the Sport Singapore **Sport Facilities** dataset on data.gov.sg, resource ID `d_2cfb0867cdeb2b7303068995699dc33b`. Its useful fields are venue name, postal code, latitude, longitude, and sports facility. The source is suitable for location and activity evidence, but not by itself for bookability or operating details.

### Ingestion pipeline

Implement a separate, idempotent sync command rather than fetching the whole catalogue during a user request:

1. Page through the official DataStore API with timeouts, retry limits, and schema validation.
2. Normalize whitespace, postal codes, coordinates, venue names, and activity labels.
3. Group repeated facility rows into a stable venue record and map only recognised facility labels to supported application activities.
4. Enrich display addresses from the postal code through OneMap search when an address is missing.
5. Match a public-venue allowlist or an equally explicit verification rule. Store all useful source records if needed for audit, but only `active + verified_public` venues may enter recommendations.
6. Upsert by a stable source key. Record source name, source key, source sync time, and verification status.
7. Mark vanished or invalid records inactive instead of deleting them, so confirmed historical sessions remain readable.

### Data model additions

The venue model should gain equivalent fields for:

- stable external source key and source name;
- source-updated or last-synced timestamp;
- active flag;
- verification status, at minimum `unverified` and `verified_public`;
- optional postal code and source metadata required for audit.

Add a unique index for the source identity. Do not invent capacity, booking windows, prices, or opening hours when the official source does not provide them; keep them nullable and show “not provided.”

### Runtime behavior

- Recommendation queries use only active, verified venues supporting the chosen activity.
- Travel scores use live OneMap route results. If routing is unavailable, the affected combination is reported as unavailable; the system must not substitute fake travel times while appearing live.
- A failed catalogue refresh leaves the last known-good verified catalogue in place and returns a failed sync status.
- The UI should show a concise data-source/last-updated note so assessors can distinguish real records from mock data.

## 7. Database and migration design

- Railway PostgreSQL is the durable system of record; the application connects over Railway's private network using `DATABASE_URL`.
- Alembic is the only production schema-change mechanism. A deployment pre-step runs `alembic upgrade head`; a failed migration blocks the release.
- Set `AUTO_CREATE_TABLES=false` publicly so startup cannot silently drift the schema.
- Existing user, group, input, recommendation, ballot, and confirmation data remains persistent across application restarts.
- Take one manual logical backup after the final rehearsal and another before the presentation. Enable the available scheduled database backup for the assessment window.
- Venue syncs are non-destructive and transactional where practical.

## 8. Privacy, security, and error handling

- Exact participant home/location inputs remain owner-only. Group responses and logs must not expose another user's precise address.
- Logs may contain request IDs, provider status, and stable internal IDs, but not OAuth codes/tokens, cookies, full addresses, or raw provider payloads.
- Google client secret, application signing secret, database URL, and OneMap credentials are deployment secrets.
- Startup should fail clearly when mandatory public-environment secrets are absent.
- `/health` proves the process is running; a readiness check also confirms database connectivity without leaking credentials.
- External provider failures return a useful user message and observable server error, but never silently switch the public site back to mocks.
- OAuth errors return the user to sign-in with a safe generic message while detailed, redacted diagnostics remain server-side.

## 9. Build and deployment design

Add a root multi-stage Docker build:

1. Node stage installs locked frontend dependencies and builds the React assets.
2. Python stage installs locked backend dependencies, copies the backend and built frontend, and runs the production ASGI server.
3. FastAPI mounts assets and provides an SPA fallback only after API and documentation routes, so missing `/api` endpoints cannot accidentally return HTML.

Railway builds from the private GitHub repository, exposes one generated HTTPS domain, and runs database migrations before each release. A previous application image remains available for redeployment. Database rollback uses backups or explicit backward migrations; the process must never assume that reverting application code automatically reverts data.

NTU hosting can still be asked about through the course staff, but it is not on the critical path because no general student self-service hosting entitlement has been established. If NTU provides an equivalent HTTPS container/PostgreSQL platform quickly, the same containerized design can move there.

## 10. Verification and acceptance criteria

### Automated checks

- Existing backend suite, frontend lint, type check, and production build run from a clean checkout.
- OAuth tests cover success, mismatched/expired/reused state, nonce mismatch, unverified email, provider failure, account upsert, and debug-auth denial in production.
- Venue adapter tests cover pagination, schema changes, activity mapping, deduplication, invalid coordinates, nullable fields, allowlist decisions, idempotent upsert, stale deactivation, and failure preserving last-good data.
- Repository/integration tests run against PostgreSQL, not only SQLite.
- Privacy tests prove that a participant cannot read another participant's exact location.

### Live smoke tests

- Three team members sign in with three real Google accounts on separate browsers/devices.
- One creates a group; others join; all save locations/preferences; the organiser generates recommendations; all vote; the organiser confirms the result.
- At least one known Singapore address geocodes through OneMap and at least one route is produced live.
- Displayed recommended venues are verified records imported from the official dataset and survive an app restart/redeployment.
- Logout and expired-session behavior work, and debug personas are unreachable publicly.

### Release gate

The demo video should not be recorded until the complete multi-user path passes twice from a clean browser state. The presentation release is frozen except for severity-one fixes after the final rehearsal.

## 11. Schedule

- **2026-10-27 to 2026-10-30:** approve design, establish Git baseline, reproduce tests, create deployment skeleton and credentials checklist.
- **2026-10-31 to 2026-11-04:** harden Google login, implement venue ingestion/migration, and add automated tests.
- **By 2026-11-06:** first public Railway deployment with PostgreSQL, exact OAuth redirect, and at least a small verified real venue catalogue.
- **2026-11-07 to 2026-11-09:** three-account end-to-end rehearsals, data review, backup, and video recording.
- **Approximately 2026-11-10:** demo video deadline.
- **2026-11-11 to 2026-11-16:** stability-only fixes, final backup, presentation rehearsal, and fallback screenshots/video.
- **Approximately 2026-11-17:** presentation.

## 12. Cost and shutdown

The intended deployment is one low-usage Railway application plus one small PostgreSQL service, monitored against the agreed **S$10–30 per month** ceiling. Railway usage is metered, so the team must enable cost alerts/limits where available and inspect usage after the first full rehearsal rather than assume a fixed bill.

After grading, export any required evidence, take a final database dump only if the team wants to retain it, revoke/delete Google OAuth secrets, remove OneMap credentials, and suspend or delete Railway services so charges stop.

## 13. Approval decisions

Implementation may start when the team accepts these four decisions:

1. Use Railway Singapore with one same-origin application container and one PostgreSQL service.
2. Treat Google login as required now and defer Google Calendar integration.
3. Import the official Sport Facilities dataset but recommend only an explicitly verified public subset.
4. Use an early public staging milestone by 2026-11-06, rather than waiting until local work is “finished.”

## 14. Primary external references

- data.gov.sg Sport Facilities dataset: <https://data.gov.sg/datasets?resultId=d_2cfb0867cdeb2b7303068995699dc33b&sort=updatedAt>
- OneMap API documentation: <https://www.onemap.gov.sg/apidocs/>
- Google OpenID Connect: <https://developers.google.com/identity/openid-connect/openid-connect>
- Railway regions: <https://docs.railway.com/deployments/regions>
- Railway PostgreSQL: <https://docs.railway.com/databases/postgresql>
- Railway pre-deploy commands: <https://docs.railway.com/deployments/pre-deploy-command>
- Railway domains and HTTPS: <https://docs.railway.com/networking/domains/working-with-domains>
