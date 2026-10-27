# Real Venue Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the production demo catalogue with a durable, idempotently synced set of verified public Singapore sports venues sourced from data.gov.sg and enriched/routed through OneMap.

**Architecture:** The data.gov.sg adapter fetches and validates raw rows; a pure normalizer groups rows into source venues; a versioned allowlist admits only manually verified public venues; and a sync service performs transactional upserts without deleting historical references. Recommendation queries require verified active venues whenever mock providers are disabled.

**Tech Stack:** FastAPI, SQLModel, Alembic, httpx, PostgreSQL, data.gov.sg DataStore API, OneMap, pytest, React/TypeScript

**Spec:** `docs/superpowers/specs/2026-10-27-production-pilot-design.md`

## Global Constraints

- Official resource ID is `d_2cfb0867cdeb2b7303068995699dc33b`.
- Only `active + verified_public` venues may be recommended in non-mock mode.
- Dataset values do not prove bookability; do not invent capacity, price, hours, booking lead time, or availability.
- Failed syncs preserve the last known-good catalogue and never silently fall back to mock records.
- Historical venues referenced by sessions/combinations are deactivated, never deleted.

## Review Focus

- Blank venue names and `-` postal codes must never become active venues; Task 1 adds `test_normalizer_rejects_blank_identity_fields`.
- Duplicate rows/case variants must collapse to one stable source venue; Task 1 adds `test_normalizer_groups_name_postal_case_variants`.
- A truncated or schema-changed API response must fail without partial replacement; Task 1 and Task 3 test schema rejection and transaction rollback.
- A formerly verified record missing from a later sync must become inactive but remain queryable by ID; Task 3 adds `test_sync_deactivates_missing_without_deleting`.
- OneMap Search now requires authentication, and a missing/rejected token must return unavailable rather than an unauthenticated request; Task 1 updates adapter tests. Mock/legacy rows are separately pinned by Task 3's `test_repository_requires_verified_active_venue_in_live_mode`.

---

### Task 1: Fetch and normalize official facility rows

**Files:**
- Replace: `backend/app/adapters/data_gov_sg_adapter.py`
- Modify: `backend/app/adapters/onemap.py`
- Create: `backend/app/services/venue_catalog.py`
- Create: `backend/tests/test_data_gov_sg_adapter.py`
- Create: `backend/tests/test_venue_catalog.py`
- Modify: `backend/tests/recommender/test_onemap_adapter.py`
- Modify: `backend/app/core/config.py`

**Interfaces:**
- Consumes: `https://data.gov.sg/api/action/datastore_search` and the fixed resource ID.
- Produces: `SourceFacilityRow`, `NormalizedVenue`, `DataGovSgAdapter.load_facilities() -> Awaitable[list[SourceFacilityRow]]`, and `normalize_facilities(rows: Iterable[SourceFacilityRow]) -> list[NormalizedVenue]`.

- [ ] **Step 1: Write failing adapter tests**

Add tests for multiple pages, `_links.next`, `success=false`, HTTP timeout/429/5xx, malformed JSON, missing required columns, invalid numeric coordinates, and duplicate page detection. Mock all HTTP with `httpx.MockTransport`.

- [ ] **Step 2: Run adapter tests and verify failure**

Run `backend/.venv/bin/python -m pytest backend/tests/test_data_gov_sg_adapter.py -v`. Expected: FAIL because the adapter is a stub.

- [ ] **Step 3: Implement typed pagination**

Set `data_gov_sg_base_url` default to `https://data.gov.sg`; request pages of 1,000 with a 20-second timeout and bounded retry for 429/5xx. Require `VenueName`, `PostalCode`, `Latitude`, `Longitude`, `SportsFacility`, and `_id`; return typed rows or raise a specific catalogue-source error before database work begins.

- [ ] **Step 4: Write failing normalization tests**

Add `test_normalizer_rejects_blank_identity_fields`, `test_normalizer_groups_name_postal_case_variants`, `test_normalizer_collects_recognized_activities`, `test_normalizer_ignores_unknown_facilities`, and `test_source_key_is_stable_across_row_order`. Assert `Badminton Court -> Badminton` and nullable unsupported metadata.

- [ ] **Step 5: Implement pure normalization**

Normalize Unicode/whitespace/case for matching, retain a human display name, require six-digit postal code and Singapore-range coordinates, map only explicit facility labels, and derive `source_key` from normalized venue name plus postal code. Do not use `_id` as venue identity because each facility has its own row.

- [ ] **Step 6: Authenticate OneMap search**

Add failing tests `test_geocode_uses_bearer_token` and `test_geocode_without_credentials_is_unavailable`, then make `OneMapAdapter.geocode` obtain/cache a token and send `Authorization: Bearer <token>` just like routing. A 401/403 clears a non-static cached token and returns `UNAVAILABLE`; never retry with an unauthenticated search.

- [ ] **Step 7: Verify and commit**

Run both new test modules plus `backend/tests/recommender/test_onemap_adapter.py`. Expected: PASS. Commit with `git commit -m "feat: fetch and normalize SportSG venue data"`.

### Task 2: Add provenance and verification to the venue model

**Files:**
- Modify: `backend/app/models/domain.py:118-139`
- Modify: `backend/app/models/enums.py`
- Create: `backend/migrations/versions/b8f3c1d2e4a6_add_venue_catalog_provenance.py`
- Create: `backend/app/data/verified_public_sports_venues.json`
- Create: `docs/venue-verification.md`
- Modify: `backend/tests/test_venue_catalog.py`

**Interfaces:**
- Consumes: normalized source keys from Task 1.
- Produces: `VenueVerificationStatus` with `DEMO`, `UNVERIFIED`, and `VERIFIED_PUBLIC`; venue fields `postal_code`, `source_key`, `last_synced_at`, `is_active`, and `verification_status`.

- [ ] **Step 1: Write failing model and allowlist tests**

Assert source identity is unique, legacy/demo rows migrate to `DEMO`, real rows default to `UNVERIFIED`, and every allowlist entry has source key, canonical display name, official verification URL, and `verified_on` date.

- [ ] **Step 2: Run tests and verify failure**

Run `backend/.venv/bin/python -m pytest backend/tests/test_venue_catalog.py -k 'model or allowlist or verification' -v`. Expected: FAIL because fields/status/file do not exist.

- [ ] **Step 3: Implement model and migration**

Add nullable source fields first, backfill existing rows as `DEMO`, then add the unique `(data_source, source_key)` constraint for non-null keys. Keep group-size/lead-time fields nullable. Downgrade removes only the new columns/constraint and does not delete venues.

- [ ] **Step 4: Curate the initial badminton allowlist**

Verify at least eight geographically distributed public sport centres/halls from the dataset against official ActiveSG/agency pages. Store only exact source identities and evidence URLs; include Bishan, Clementi, Delta, Heartbeat @ Bedok, Hougang, Pasir Ris, Sengkang, and Toa Payoh when their current source name/postal pairs match. Do not include schools, condominiums, police/SCDF sites, or unnamed postal-only rows.

- [ ] **Step 5: Verify migration round trip**

Run Alembic upgrade against a populated temporary PostgreSQL database, assert legacy venue IDs remain, run downgrade/upgrade, and assert the unique source identity is enforced. SQLite unit tests are insufficient for this step.

- [ ] **Step 6: Commit**

Run full backend tests and commit with `git commit -m "feat: add verified venue provenance"`.

### Task 3: Implement transactional catalogue sync and live-only repository filtering

**Files:**
- Modify: `backend/app/services/venue_catalog.py`
- Modify: `backend/app/repositories/aggregates.py:53-58`
- Modify: `backend/app/services/integrated_recommendation_service.py:164`
- Modify: `backend/app/services/application_services.py:171-176`
- Create: `backend/scripts/sync_venues.py`
- Modify: `backend/tests/test_venue_catalog.py`
- Modify: `backend/tests/test_web_integration.py`

**Interfaces:**
- Consumes: `NormalizedVenue`, verification allowlist, activity rows, and optional OneMap address matches.
- Produces: `VenueCatalogSyncService.sync(db: Session, venues: Sequence[NormalizedVenue], synced_at: datetime) -> VenueSyncResult`; `VenueRepository.supported_for_activity(activity_type_id: UUID, require_verified: bool) -> list[Venue]`.

- [ ] **Step 1: Write failing sync tests**

Add tests for insert, idempotent second run, changed name/coordinates, allowlisted versus unverified records, OneMap address enrichment, missing activity row, and `test_sync_deactivates_missing_without_deleting`. Assert one commit occurs only after the complete batch.

- [ ] **Step 2: Add failure-preservation tests**

Add tests proving provider/schema errors make zero database changes and an exception during upsert rolls back all partial changes while previous verified venues remain active.

- [ ] **Step 3: Implement transactional upsert**

Upsert by `(data_source="DATA_GOV_SG_SPORT_FACILITIES", source_key)`, replace source-backed activity links, apply allowlist status, set `last_synced_at`, and deactivate previously sourced records absent from a successful complete sync. Enrich addresses by postal code through OneMap, with `"<venue>, Singapore <postal>"` as an honest fallback label.

- [ ] **Step 4: Implement the CLI entry point**

`python -m scripts.sync_venues --dry-run` fetches/normalizes and prints counts without writes; `--apply` requires a database URL and executes one transaction. Output counts only—no private user data or credentials.

- [ ] **Step 5: Filter production recommendation queries**

Pass `require_verified=not settings.use_mock_providers` from both recommendation services. When true, filter `Venue.is_active is True` and `Venue.verification_status == VERIFIED_PUBLIC`; when false, preserve current demo behavior.

- [ ] **Step 6: Verify and commit**

Run venue tests, web integration tests, then the full backend suite. Expected: PASS. Commit with `git commit -m "feat: sync verified public venue catalogue"`.

### Task 4: Expose venue provenance without overstating availability

**Files:**
- Modify: `backend/app/services/web_contract_service.py:481-489`
- Modify: `frontend/src/api/types.ts:162-170`
- Modify: `frontend/src/results/RankedOptionCard.tsx:97-106`
- Modify: `frontend/src/results/RankedOptionCard.css`
- Modify: `frontend/docs/api-contract.md`
- Modify: `backend/tests/test_web_integration.py`

**Interfaces:**
- Consumes: venue provenance fields from Task 2.
- Produces: `VenueSummary.dataSource`, `VenueSummary.lastUpdated`, and a visible source note on recommendation cards.

- [ ] **Step 1: Write failing API projection test**

Assert a live verified venue returns `dataSource: "Sport Singapore via data.gov.sg"` and an ISO `lastUpdated`, while no booking/availability claim is added.

- [ ] **Step 2: Implement backend projection and contract**

Add public provenance fields to `_venue` and document that they describe catalogue origin, not live court availability.

- [ ] **Step 3: Implement frontend source note**

Extend `VenueSummary` and render `Venue data: Sport Singapore via data.gov.sg · updated <date>` in expanded result cards. Keep the map link and address; do not add “available” or “book now” language.

- [ ] **Step 4: Verify full stack**

Run backend tests, frontend lint, and frontend production build. Expected: PASS.

- [ ] **Step 5: Commit**

Run `git add backend frontend && git commit -m "feat: show venue data provenance"`.

