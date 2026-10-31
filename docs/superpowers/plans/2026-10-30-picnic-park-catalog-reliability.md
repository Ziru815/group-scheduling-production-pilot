# Picnic Park Catalogue and Production Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Picnic a complete production activity backed by twenty verified islandwide parks, while hiding unsupported Leisure activities and preserving the last-good sports and park catalogues.

**Architecture:** Add a strict data.gov.sg NParks poll-download adapter, a curated route-point allowlist, and a source-isolated atomic park synchroniser that runs only as an explicit maintenance command. Gate production activity creation and all mutable Session operations on active verified venue support, keep confirmed/read-only data available, then reuse the existing OneMap, scoring, confirmation, and Calendar pipeline unchanged.

**Tech Stack:** Python 3.13, FastAPI, SQLModel, Alembic, PostgreSQL/SQLite, httpx, pytest, React 19, TypeScript 6, Node 24 built-in test runner, Vite, OneMap, data.gov.sg/NParks, Render

**Spec:** `docs/superpowers/specs/2026-10-30-picnic-park-catalog-reliability-design.md`

## Global Constraints

- Publish exactly twenty active, `VERIFIED_PUBLIC`, `PARK` venues linked only to Picnic.
- Cover west, north, north-east, central/south, and east, with unique public meeting points inside Singapore bounds.
- Use dataset `d_77d7ec97be83d44f61b85454f844382f` and data source `DATA_GOV_SG_NPARKS_PARKS`; never infer meeting points from polygon centroids.
- Keep data.gov.sg outside all interactive web requests; park sync is a manual `--dry-run` / `--apply` operation and is not added to `scripts/start_production.sh`.
- Send optional `DATA_GOV_SG_API_KEY` only as the server-side `x-api-key` header; never return, log, or bundle it in the frontend.
- Treat the upstream snapshot and the twenty-entry allowlist as all-or-nothing; any source, validation, identity, or database failure leaves the last-good park catalogue unchanged.
- Park sync may deactivate only rows whose data source is `DATA_GOV_SG_NPARKS_PARKS`; it must never alter sport rows or sport relationships.
- A Park never receives Sports Facility minimum-group-size, optimal-group-size, or advance-booking exclusions; the Session minimum-attendee threshold and journey cap still apply.
- Production creation exposes only active Activity Types with at least one active verified `SUPPORTED` venue; development mock mode keeps its current labelled catalogue.
- Unsupported existing Sessions remain readable and cancellable, but joining, response changes, recommendation generation, and confirmation return `ACTIVITY_UNSUPPORTED`.
- Do not change scoring weights, shortlist size, deterministic ranking, OneMap routing, privacy behavior, Calendar behavior, public URL, or the `main` branch.
- Do not add a third-party parser or frontend test dependency; use the Python standard library for GeoJSON structure validation and Node 24's built-in test runner for pure frontend copy rules.

## Review Focus

- A poll response that points to HTTP, credentials, a fragment, or an unobserved host must fail before download; Task 1 pins each case and records only the exact official host observed during implementation.
- A truncated, duplicate, renamed, or out-of-Singapore upstream feature must abort before persistence; Tasks 1 and 2 test complete-snapshot and identity rejection.
- A failed or partial park apply must preserve prior parks and every sports row/link; Task 2 injects database failure and asserts rollback plus source isolation.
- A stale client must not create or mutate an unsupported Leisure Session even when the UI has hidden it; Task 4 tests web and legacy endpoints, including read/cancel exceptions.
- A Picnic recommendation must not acquire sports-only exclusions and must never substitute straight-line or zero-minute travel when OneMap is unavailable; Task 5 tests both conditions end-to-end.

---

## File Map

- `backend/app/adapters/nparks_geojson_adapter.py`: fetch, secure, bound, and parse one complete official NParks GeoJSON snapshot.
- `backend/app/data/verified_public_picnic_parks.json`: twenty reviewed source identities and safe meeting points.
- `backend/app/services/park_catalog.py`: validate curated evidence, match it to the snapshot, and atomically persist only the park source.
- `backend/scripts/sync_parks.py`: operator-facing dry-run/apply command; no startup integration.
- `backend/app/services/activity_availability.py`: one policy boundary for production activity visibility and mutable Session eligibility.
- `frontend/src/results/venueGuidance.ts`: category-specific provenance and availability wording shared by result and confirmation pages.

### Task 1: Build the strict NParks poll-download adapter

**Files:**
- Create: `backend/app/adapters/nparks_geojson_adapter.py`
- Create: `backend/tests/test_nparks_geojson_adapter.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: `NPARKS_PARKS_DATASET_ID`, `ParkSourceFeature(source_code: str, source_name: str, geometry_type: str, coordinates: object)`, and `DataGovSgParkAdapter.load_parks() -> list[ParkSourceFeature]`.
- Produces: optional `Settings.data_gov_sg_api_key: str | None`.
- Raises: the existing `CatalogueSourceError` for every upstream, security, size, schema, identity, or coordinate failure.

- [ ] **Step 1: Write failing adapter contract tests**

Add tests named `test_load_parks_polls_then_downloads_complete_geojson`, `test_load_parks_sends_optional_api_key_only_to_poll`, `test_load_parks_retries_429_and_5xx_then_succeeds`, and `test_load_parks_rejects_timeout_and_malformed_json`. The success fixture must contain one Polygon and one MultiPolygon and assert the exact `L_CODE`/`NAME` identities.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd backend && python -m pytest tests/test_nparks_geojson_adapter.py -q`

Expected: collection/import failure because `nparks_geojson_adapter` does not exist.

- [ ] **Step 3: Observe and lock the official download host**

Call the official poll endpoint once for dataset `d_77d7ec97be83d44f61b85454f844382f`. Record the exact returned HTTPS hostname in `OFFICIAL_DOWNLOAD_HOSTS`; permit `.data.gov.sg` only for the fixed poll endpoint and do not use a catch-all wildcard for download hosts.

- [ ] **Step 4: Add failing adversarial and completeness tests**

Test rejection of HTTP, username/password, fragment, unobserved host, non-JSON content type, declared or streamed body above 25 MiB, non-FeatureCollection JSON, missing `L_CODE`/`NAME`, blank identity, duplicate `L_CODE`, unsupported geometry, malformed coordinate arrays, coordinates outside `1.1..1.5` latitude or `103.6..104.1` longitude, and an empty snapshot.

- [ ] **Step 5: Implement the minimal bounded adapter and configuration**

Implement `DataGovSgParkAdapter` with a 20-second timeout, two retries for transport errors/429/5xx, bounded streamed download, optional `x-api-key` on the poll request only, URL validation before the download, and complete validation before returning any feature. Do not calculate or expose centroids.

- [ ] **Step 6: Run adapter tests and commit**

Run: `cd backend && python -m pytest tests/test_nparks_geojson_adapter.py tests/test_data_gov_sg_adapter.py -q`

Expected: all adapter tests pass and no test output contains the API key.

```bash
git add backend/app/adapters/nparks_geojson_adapter.py backend/app/core/config.py backend/.env.example backend/tests/test_nparks_geojson_adapter.py
git commit -m "feat: add strict NParks catalogue adapter"
```

### Task 2: Curate and atomically persist twenty Picnic parks

**Files:**
- Create: `backend/app/data/verified_public_picnic_parks.json`
- Create: `backend/app/services/park_catalog.py`
- Create: `backend/tests/test_park_catalog.py`
- Create: `backend/migrations/versions/d0e5f6a7b8c9_add_venue_meeting_point.py`
- Modify: `backend/app/models/domain.py`
- Modify: `backend/app/services/web_contract_service.py`

**Interfaces:**
- Consumes: `ParkSourceFeature` from Task 1.
- Produces: `CuratedPicnicPark`, `NormalizedPark`, `ParkSyncResult(inserted: int, updated: int, deactivated: int, verified: int)`, `load_verified_picnic_parks() -> dict[str, CuratedPicnicPark]`, `normalize_verified_parks(features, allowlist) -> list[NormalizedPark]`, and `ParkCatalogSyncService.sync(db, parks, *, synced_at) -> ParkSyncResult`.
- Produces: nullable `Venue.meeting_point: str | None`; existing sport/demo rows remain valid without backfill.
- Produces: browser venue projection fields `meetingPoint` and source label `NParks via data.gov.sg`.

- [ ] **Step 1: Add the nullable meeting-point migration and failing model test**

Write a migration test that upgrades a pre-change database, keeps an existing sports venue, and stores/reads a Park meeting point. Add `meeting_point` as a nullable `VARCHAR(180)`; downgrade removes only that column.

- [ ] **Step 2: Research and record exactly twenty reviewed parks**

Populate the JSON entries with `source_code`, exact `source_name`, `canonical_name`, `meeting_point`, `address`, route `latitude`/`longitude`, official NParks `verification_url`, `verified_on: 2026-10-30`, and one of `west`, `north`, `north-east`, `central-south`, or `east`. Verify each source identity against the current official snapshot and each route point against the official evidence; nature reserves and polygon centroids are prohibited.

- [ ] **Step 3: Write failing allowlist and normalization tests**

Assert exactly 20 unique source codes and route points, all five regions, HTTPS official NParks evidence, Singapore coordinate bounds, nonblank meeting-point/address fields, exact source-name match, and failure when any curated identity is missing, renamed, duplicated, or outside bounds.

- [ ] **Step 4: Write failing atomic persistence tests**

Test insert, update, idempotent reapply, park-only deactivation, Picnic-only `SUPPORTED` links, null sports constraints, active-recommendation invalidation, rollback on the tenth write, preservation of the last-good park rows, and byte-for-byte preservation of sports rows and relationships.

- [ ] **Step 5: Implement validation, normalization, and source-isolated sync**

Use `source_code` as the source key under `DATA_GOV_SG_NPARKS_PARKS`; write `category=PARK`, `verification_status=VERIFIED_PUBLIC`, the curated route point/address/meeting point, and only the Picnic relationship. Load and validate the full snapshot and allowlist before entering the database transaction; commit once after all writes and invalidations succeed. Extend `_venue(venue)` to return `meetingPoint` and translate this source to `NParks via data.gov.sg` without changing existing Sports/Demo labels.

- [ ] **Step 6: Run migration/catalogue tests and commit**

Run: `cd backend && python -m pytest tests/test_park_catalog.py tests/test_venue_catalog.py tests/test_render_deployment.py -q`

Expected: all tests pass; sports catalogue counts and behavior are unchanged.

```bash
git add backend/app/data/verified_public_picnic_parks.json backend/app/services/park_catalog.py backend/app/models/domain.py backend/app/services/web_contract_service.py backend/migrations/versions/d0e5f6a7b8c9_add_venue_meeting_point.py backend/tests/test_park_catalog.py
git commit -m "feat: persist verified Picnic parks atomically"
```

### Task 3: Add the safe operator sync command

**Files:**
- Create: `backend/scripts/sync_parks.py`
- Create: `backend/tests/test_sync_parks.py`
- Test: `backend/tests/test_render_deployment.py`

**Interfaces:**
- Consumes: `DataGovSgParkAdapter.load_parks()`, `load_verified_picnic_parks()`, `normalize_verified_parks(...)`, and `ParkCatalogSyncService.sync(...)`.
- Produces: `normalization_counts(source_features, normalized_parks) -> dict[str, int]` and CLI modes `--dry-run` / `--apply`.

- [ ] **Step 1: Write failing command tests**

Assert `--dry-run` performs no database write and prints only aggregate `source_features`, `curated_parks`, `rejected_features`, and `matched_parks`; `--apply` requires `DATABASE_URL`, commits exactly twenty, is idempotent, and never prints tokens, participant data, addresses, or coordinates.

- [ ] **Step 2: Implement the minimal command**

Fetch and validate first, then load/match the allowlist, print counts, and return for dry-run. For apply, open the configured engine and call the atomic service once. Do not edit `scripts/start_production.sh` or `render.yaml` to invoke this command automatically.

- [ ] **Step 3: Test the command and deployment guard**

Run: `cd backend && python -m pytest tests/test_sync_parks.py tests/test_render_deployment.py -q`

Expected: all pass, including an assertion that the production start command contains no park-sync invocation.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/sync_parks.py backend/tests/test_sync_parks.py backend/tests/test_render_deployment.py
git commit -m "feat: add controlled park catalogue sync"
```

### Task 4: Gate production activities and unsupported Session mutations

**Files:**
- Create: `backend/app/services/activity_availability.py`
- Create: `backend/tests/test_activity_availability.py`
- Modify: `backend/app/repositories/aggregates.py`
- Modify: `backend/app/services/application_services.py`
- Modify: `backend/app/services/web_contract_service.py`
- Modify: `backend/app/services/integrated_recommendation_service.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/controllers/web_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_production_runtime.py`
- Modify: `frontend/docs/api-contract.md`

**Interfaces:**
- Produces: `VenueRepository.has_verified_support(activity_type_id: UUID) -> bool`, `supported_activity_categories(db, *, require_verified: bool) -> list[dict]`, `require_creatable_activity(db, activity_type_id, *, require_verified) -> ActivityType`, and `require_mutable_activity(db, session, *, require_verified) -> None`.
- Produces: `ActivityUnavailableError(field_name: str | None)`; `field_name="activityTypeId"` renders 422 field validation, while `None` renders 409 `ACTIVITY_UNSUPPORTED`.
- Produces: API error code `ACTIVITY_UNSUPPORTED`; create-time validation uses `VALIDATION_FAILED` with field `activityTypeId`.
- Produces: `SessionDetail.activitySupported: bool` and `InvitationPreview.activitySupported: bool`.

- [ ] **Step 1: Write failing production catalogue tests**

Assert production returns Badminton/Basketball/Football and Picnic only when each has active verified support; Board Games/Bowling and an inactive activity are absent. Assert development mock mode preserves its existing catalogue.

- [ ] **Step 2: Write failing stale-client and existing-Session tests**

For both `/api` and `/api/v1`, assert unsupported creation returns 422 with `VALIDATION_FAILED` and `fields.activityTypeId`; existing unsupported sessions can be listed/read/cancelled and confirmed historical plans remain readable, while join, Session settings update, save/edit/withdraw response, recommendation generation, confirmation, and Calendar retry return 409 `ACTIVITY_UNSUPPORTED`.

- [ ] **Step 3: Implement the central availability policy**

Use an indexed `EXISTS` query over active `Venue`, `VenueActivity.support_status=SUPPORTED`, and `VERIFIED_PUBLIC` status. Apply the policy at service boundaries so both routers are protected; do not depend on frontend filtering.

- [ ] **Step 4: Extend projections and error contracts**

Return `activitySupported` in Session detail and invitation preview, map unsupported mutation errors explicitly in `main._error_code`, and document the fields/error in the API contract. Keep cancel and all GET projections outside the mutation block.

- [ ] **Step 5: Run focused tests and commit**

Run: `cd backend && python -m pytest tests/test_activity_availability.py tests/test_production_runtime.py tests/test_session_and_availability.py tests/test_web_integration.py -q`

Expected: all pass; legacy and browser routes enforce the same policy.

```bash
git add backend/app/services/activity_availability.py backend/app/repositories/aggregates.py backend/app/services/application_services.py backend/app/services/web_contract_service.py backend/app/services/integrated_recommendation_service.py backend/app/controllers/router.py backend/app/controllers/web_api.py backend/app/main.py backend/tests/test_activity_availability.py backend/tests/test_production_runtime.py frontend/docs/api-contract.md
git commit -m "feat: gate activities by verified venue support"
```

### Task 5: Prove the complete Picnic recommendation path

**Files:**
- Create: `backend/tests/test_picnic_web_integration.py`
- Modify: `backend/app/services/application_services.py`
- Modify: `backend/app/services/calendar_sync_service.py`
- Modify: `backend/tests/recommender/test_feasibility_and_scoring.py`
- Modify: `backend/tests/recommender/test_engine.py`
- Modify: `backend/tests/test_calendar_and_privacy.py`

**Interfaces:**
- Consumes: verified `PARK` venues from Task 2 and activity policy from Task 4.
- Produces: no new public interface; both recommendation entry points enforce the same category-aware feasibility rules.

- [ ] **Step 1: Add failing Park feasibility regressions**

Create a Park with deliberately impossible sport group-size and booking-lead values and assert it remains feasible when attendance and travel pass. Assert the same values still exclude a Sports Facility.

- [ ] **Step 2: Align the legacy recommendation path**

Change only the legacy `RecommendationService` pre-routing checks so group-size and booking-lead exclusions run when `venue.category == SPORTS_FACILITY`; do not change the integrated engine's already-correct rule.

- [ ] **Step 3: Add the three-origin Picnic end-to-end test**

Create a Picnic Session, join three users with distinct Singapore origins, submit overlapping availability, route through deterministic OneMap fixtures, generate multiple Park combinations, assert rank stability and no address/coordinate leakage, confirm one, and assert the Calendar event location is `meeting point, address` without any participant location.

- [ ] **Step 4: Add explicit provider-failure coverage**

Make OneMap unavailable and assert the result uses the existing routing-unavailable/near-match behavior, contains no zero-minute or straight-line substitute, and cannot confirm a `DATA_UNAVAILABLE` combination.

- [ ] **Step 5: Run recommendation/integration tests and commit**

Run: `cd backend && python -m pytest tests/recommender tests/test_picnic_web_integration.py tests/test_calendar_and_privacy.py -q`

Expected: all pass with deterministic ranks across repeated runs.

```bash
git add backend/app/services/application_services.py backend/app/services/calendar_sync_service.py backend/tests/recommender/test_feasibility_and_scoring.py backend/tests/recommender/test_engine.py backend/tests/test_picnic_web_integration.py backend/tests/test_calendar_and_privacy.py
git commit -m "test: prove the Picnic recommendation journey"
```

### Task 6: Make Park provenance and read-only states clear in the frontend

**Files:**
- Create: `frontend/src/results/venueGuidance.ts`
- Create: `frontend/tests/venueGuidance.test.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/results/RankedOptionCard.tsx`
- Modify: `frontend/src/pages/ConfirmedPage.tsx`
- Modify: `frontend/src/pages/JoinPage.tsx`
- Modify: `frontend/src/pages/AvailabilityPage.tsx`
- Modify: `frontend/src/pages/ResultsPage.tsx`
- Modify: `frontend/src/mocks/handlers.ts`
- Modify: `frontend/src/mocks/db.ts`

**Interfaces:**
- Consumes: `SessionDetail.activitySupported`, `InvitationPreview.activitySupported`, `VenueSummary.category`, `VenueSummary.meetingPoint`, `dataSource`, and `lastUpdated`.
- Produces: `venueAvailabilityGuidance(category: VenueCategory) -> string` and `venueCategoryLabel(category: VenueCategory) -> string`.

- [ ] **Step 1: Add failing pure-copy tests with Node's built-in runner**

Add `npm test` as `node --experimental-strip-types --test tests/*.test.ts`. Assert Park guidance mentions public access/reservation/availability are not guaranteed and NParks closures/rules; Sports guidance retains ActiveSG booking language; neither claims a booking or live availability.

- [ ] **Step 2: Extend API types and mock projections**

Add `meetingPoint: string | null`, `activitySupported: boolean`, and `ACTIVITY_UNSUPPORTED`. Keep mock mode supported and update mock fixture/projection shapes without removing its labelled demo activities.

- [ ] **Step 3: Render Park identity and provenance**

Show Park, its meeting point, address, existing map link, `NParks via data.gov.sg`, update date, and Park guidance on ranked and confirmed views. Continue showing the category-specific Sports wording for sports venues.

- [ ] **Step 4: Render unsupported Sessions as read-only**

Invitation shows an explicit unavailable message instead of Join; Availability shows stored response but no save/withdraw controls; Results shows existing results/confirmation but no generate/adjust/confirm controls. Organiser cancellation remains reachable from the existing Session flow.

- [ ] **Step 5: Verify responsive states and commit**

Run: `cd frontend && npm test && npm run lint && npm run build`

Expected: copy tests pass, oxlint exits zero, TypeScript compiles, and the production Vite build succeeds. Manually inspect 375px width for loading, empty, unsupported, Park result, and confirmed Park states; no horizontal overflow or hidden primary message.

```bash
git add frontend/package.json frontend/src/api/types.ts frontend/src/results/venueGuidance.ts frontend/tests/venueGuidance.test.ts frontend/src/results/RankedOptionCard.tsx frontend/src/pages/ConfirmedPage.tsx frontend/src/pages/JoinPage.tsx frontend/src/pages/AvailabilityPage.tsx frontend/src/pages/ResultsPage.tsx frontend/src/mocks/handlers.ts frontend/src/mocks/db.ts
git commit -m "feat: present verified Picnic parks clearly"
```

### Task 7: Document operations, evidence, and SRS traceability

**Files:**
- Modify: `docs/venue-verification.md`
- Modify: `docs/runbooks/assessment-release.md`
- Modify: `docs/deployment.md`
- Modify: `SRS_TRACEABILITY.md`

**Interfaces:**
- Consumes: Tasks 1-6 behavior and commands.
- Produces: an operator runbook for dry-run/apply/rollback and an auditable twenty-park evidence register.

- [ ] **Step 1: Record the twenty park identities and evidence**

Document region, official source code/name, canonical name, meeting point/address, official NParks URL, verification date, and the limitation that access/reservation/availability is not guaranteed. Do not publish credentials.

- [ ] **Step 2: Add the Render Shell runbook**

Document deploy-first behavior, then `cd /app/backend && python -m scripts.sync_parks --dry-run`, expected `matched_parks=20`, followed by `--apply`, idempotent repeat, health checks, and a controlled park-source withdrawal procedure. Explicitly state that a failed sync does not restart or take down the web service.

- [ ] **Step 3: Update traceability**

Map Picnic evidence to FR-C3..C5, FR-D1..D10, NFR-3, NFR-8, NFR-15, NFR-16, and NFR-17; reference the new adapter, catalog, integration, failure, and frontend tests.

- [ ] **Step 4: Verify documentation consistency and commit**

Run: `rg -n "sync_parks|DATA_GOV_SG_NPARKS_PARKS|NParks via data.gov.sg|ACTIVITY_UNSUPPORTED" docs SRS_TRACEABILITY.md frontend/docs/api-contract.md`

Expected: every operational command and public label appears consistently; no secret value appears.

```bash
git add docs/venue-verification.md docs/runbooks/assessment-release.md docs/deployment.md SRS_TRACEABILITY.md
git commit -m "docs: add Picnic park operations and traceability"
```

### Task 8: Verify, review, deploy, synchronise, and smoke-test production

**Files:**
- Read: all files changed from `origin/feature/production-pilot` to `HEAD`
- Modify only if verification or review reveals a Critical/Important defect.

**Interfaces:**
- Consumes: reviewed commits from Tasks 1-7 and the existing Render service/database/OneMap configuration.
- Produces: the same public URL with Picnic enabled only after a successful atomic park apply; Basketball, Football, and Badminton remain available; Leisure stays hidden.

- [ ] **Step 1: Run complete local verification**

Run: `cd backend && python -m pytest -q`

Expected: complete backend suite passes.

Run: `cd frontend && npm test && npm run lint && npm run build`

Expected: all frontend checks pass.

Run: `git diff --check origin/feature/production-pilot...HEAD`

Expected: no output and exit zero.

- [ ] **Step 2: Obtain a fresh whole-branch review**

Review the approved spec, every Global Constraint, every Review Focus test, the migration, source isolation, secret handling, privacy, legacy-route parity, and recovery behavior.

Expected: no Critical or Important findings; fix any such finding in one evidence-backed pass and rerun Step 1.

- [ ] **Step 3: Fast-forward the existing deployment branch**

Push the reviewed commits to `feature/production-pilot` without force-pushing and without modifying `main`. Wait for Render to run the migration and report `/ready` HTTP 200; confirm Picnic is still absent before park apply.

- [ ] **Step 4: Dry-run and apply through Render Dashboard Shell**

Run `python -m scripts.sync_parks --dry-run`, verify `matched_parks=20`, then run `python -m scripts.sync_parks --apply` twice. The first apply activates exactly twenty verified Picnic parks; the second is idempotent. Stop without applying if any count or identity check differs.

- [ ] **Step 5: Complete the production smoke test**

Verify the production activity catalogue shows Outdoors → Picnic and hides Leisure. Create a Picnic Session, join at least two Google users from distinct Singapore postals, submit overlapping availability, generate multiple Park recommendations, inspect Park/meeting-point/provenance/disclaimer/map link, confirm one, verify Calendar projection, and verify shared confirmation without exposing participant addresses.

- [ ] **Step 6: Record release evidence**

Record the deployed commit, migration result, dry-run/apply counts, `/ready` result, and smoke-test outcome in `docs/runbooks/assessment-release.md`; commit and push only the evidence update if it changes the repository.
