# OneMap Renewal and Official Venue Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep OneMap geocoding and routing working after token expiry, and show each reviewed venue's exact official ActiveSG or NParks page in results and confirmed plans.

**Architecture:** Make complete OneMap email/password credentials the primary token source, retain the fixed token only as a fallback mode, and retry an idempotent provider GET once after a rejected dynamic token. Project the existing activity-specific `VenueActivity.source_reference` through a strict HTTPS host allowlist into an optional `officialUrl`, then render that field in the two existing venue views without changing recommendation logic.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, httpx, pytest, React 19, TypeScript 6, Node test runner, CSS, Vite

**Spec:** `docs/superpowers/specs/2026-10-31-onemap-renewal-official-venue-links-design.md`

## Global Constraints

- Keep OneMap credentials and tokens backend-only; never log, serialize or commit them.
- Prefer a complete `email + password` pair over a configured fixed token; a partial pair must not disable a usable fixed token.
- Retry only one idempotent OneMap GET after a dynamically acquired token receives 401/403; a second rejection is provider-unavailable and must not loop.
- Expose only exact activity-specific URLs from supported `VenueActivity` rows, using HTTPS and the reviewed `activesgcircle.gov.sg` or `nparks.gov.sg` host families.
- Keep `officialUrl` optional so historical, demo and unsupported data continues to render safely.
- Preserve current scoring, ranking, venue counts, stored Combination IDs, privacy boundaries, organiser-only confirmation, and venue availability/booking disclaimers.
- Add no database migration, provider, runtime dependency or test dependency.
- Do not update assessment documents or add final-plan sharing in this change.

## Review Focus

- When a fixed token and complete email/password credentials coexist, dynamic authentication must win and the fixed token must never reach a provider request; Task 1 pins this with `test_refresh_credentials_take_precedence_over_static_token`.
- When only one refresh credential is present with a fixed token, the fixed-token mode must continue to work; Task 1 pins this with `test_partial_refresh_credentials_fall_back_to_static_token`.
- When a refreshed token is also rejected, the adapter must stop after one refresh/retry and return unavailable; Task 1 pins this with `test_route_rejected_refreshed_token_stops_after_one_retry`.
- A non-HTTPS URL, deceptive suffix such as `nparks.gov.sg.evil.example`, or unsupported status must become `officialUrl: null`; Task 2 pins these cases in `test_official_url_rejects_untrusted_or_unsupported_references`.
- Two otherwise equivalent ranked options whose projected `officialUrl` values differ must not be merged; Task 3 pins this with `keeps different official venue links separate`.

---

### Task 1: Reliable OneMap credential selection and one-shot recovery

**Files:**
- Modify: `backend/app/adapters/onemap.py`
- Test: `backend/tests/recommender/test_onemap_adapter.py`

**Interfaces:**
- Consumes: existing `OneMapAdapter(email, password, token, client, ...)`, `geocode(...)`, and `route(...)` contracts.
- Produces: `OneMapAdapter._has_refresh_credentials() -> bool` and `OneMapAdapter._request_with_token_retry(path: str, params: dict[str, str]) -> tuple[httpx.Response | None, str | None]` for authenticated idempotent GETs; the second tuple item is a safe unavailable-detail string when no response exists.
- Preserves: `GeocodeResult` and `RouteResult` status/detail mapping outside the authentication helper.

- [ ] **Step 1: Write failing credential-precedence tests**

Add `test_refresh_credentials_take_precedence_over_static_token` and `test_partial_refresh_credentials_fall_back_to_static_token`. The first must configure all three values, assert one `/getToken` POST, and assert both route GETs use `Bearer fresh`, never `Bearer fixed`. The second must parameterize missing email and missing password, assert no auth POST, and assert a geocode GET uses `Bearer fixed` and returns `VALID`.

- [ ] **Step 2: Run the precedence tests and verify RED**

Run: `cd backend && pytest tests/recommender/test_onemap_adapter.py -k 'precedence or partial_refresh' -q`

Expected: the complete-credentials case fails because `_get_token()` currently returns the fixed token first.

- [ ] **Step 3: Implement credential-mode selection**

Add `_has_refresh_credentials() -> bool`. Change `_get_token()` so a complete pair reuses/fetches the cached dynamic token under the existing lock; only an incomplete pair may return `_static_token`. Keep the current expiry parsing and refresh margin.

- [ ] **Step 4: Run the precedence tests and verify GREEN**

Run: `cd backend && pytest tests/recommender/test_onemap_adapter.py -k 'precedence or partial_refresh' -q`

Expected: all selected tests pass.

- [ ] **Step 5: Replace the old next-call recovery test with failing one-call recovery tests**

Replace `test_rejected_token_is_dropped_for_next_call` with:

- `test_route_rejected_dynamic_token_refreshes_and_retries_once`: `t1` receives 401, `t2` receives a valid route, the same `route()` call returns `AVAILABLE`, and counters equal two token POSTs plus two route GETs.
- `test_geocode_rejected_dynamic_token_refreshes_and_retries_once`: the same sequence returns `VALID` for `geocode()` and preserves its search parameters.
- `test_route_rejected_refreshed_token_stops_after_one_retry`: both GETs receive 401, the result is `UNAVAILABLE`, and counters prove exactly two token POSTs plus two route GETs.
- `test_static_token_rejection_is_not_refreshed`: fixed-token-only mode makes one GET, no auth POST, and returns `UNAVAILABLE`.
- `test_concurrent_token_requests_share_one_refresh`: run multiple `_get_token()` calls with `asyncio.gather`, assert every caller receives the same dynamic token, and assert exactly one auth POST.

- [ ] **Step 6: Run the recovery tests and verify RED**

Run: `cd backend && pytest tests/recommender/test_onemap_adapter.py -k 'rejected or concurrent_token' -q`

Expected: the dynamic-token success cases fail because the adapter currently waits for the next call instead of retrying.

- [ ] **Step 7: Implement `_request_with_token_retry`**

Implement `_request_with_token_retry(path: str, params: dict[str, str]) -> tuple[httpx.Response | None, str | None]` with this exact boundary: obtain the selected token, perform one GET, and when that response is 401/403 in refresh-credential mode invalidate only that rejected token under `_token_lock`, obtain a fresh token, and perform one final GET. Return `(response, None)` when a provider response exists; otherwise return `(None, "no OneMap token")` or `(None, type(exc).__name__)`. Never retry static-token mode, non-auth failures, or a second 401/403. If another task has already replaced the rejected cached token while this task waits for the lock, reuse the replacement instead of clearing it again.

Update `geocode()` and `route()` to use this helper while retaining their existing result parsing and status classification. Set their unavailable detail to `"no OneMap token"`, the HTTP exception class, or `"OneMap rejected the token"` as appropriate; do not disclose tokens or credentials.

- [ ] **Step 8: Run the adapter suite and verify GREEN**

Run: `cd backend && pytest tests/recommender/test_onemap_adapter.py -q`

Expected: all OneMap adapter tests pass, including expiry reuse, credential precedence, static fallback, geocoding, routing, and bounded recovery.

- [ ] **Step 9: Commit the OneMap reliability change**

```bash
git add backend/app/adapters/onemap.py backend/tests/recommender/test_onemap_adapter.py
git commit -m "fix: renew rejected OneMap credentials"
```

### Task 2: Activity-specific official venue URL contract

**Files:**
- Modify: `backend/app/services/web_contract_service.py`
- Test: `backend/tests/test_web_integration.py`
- Test: `backend/tests/test_picnic_web_integration.py`

**Interfaces:**
- Consumes: `VenueActivity.source_reference`, its `SupportStatus`, the venue ID, and the session's activity type ID.
- Produces: `_official_url(db: Session, venue: Venue, activity_type_id: UUID) -> str | None`.
- Changes: `_venue(db: Session, venue: Venue, activity_type_id: UUID) -> dict` now includes `"officialUrl": str | None`.

- [ ] **Step 1: Seed exact reviewed URLs in the integration fixtures**

In the sports fixture, set the verified Bishan `VenueActivity.source_reference` to an exact `https://www.activesgcircle.gov.sg/...` URL and leave the demo venue without one. In the Picnic fixture, assign exact `https://www.nparks.gov.sg/...` URLs to the supported park rows.

- [ ] **Step 2: Write failing projection tests for sports, Picnic and confirmation**

Extend the existing end-to-end assertions so:

- the verified sports recommendation returns the exact ActiveSG URL;
- the demo sports recommendation returns `officialUrl: null`;
- a Picnic recommendation returns the exact NParks URL;
- after the existing confirmation flow, `confirmed.venue.officialUrl` equals the same exact URL as the selected recommendation.

- [ ] **Step 3: Add a failing rejection test for unsafe references**

Add `test_official_url_rejects_untrusted_or_unsupported_references` using rows for `http://www.nparks.gov.sg/...`, `https://nparks.gov.sg.evil.example/...`, an unrelated HTTPS host, a park pointing to ActiveSG, a sports facility pointing to NParks, and a valid URL whose `support_status` is not `SUPPORTED`. Assert every projection returns `officialUrl: null`. Include one accepted subdomain case for each correctly matched category/host family.

- [ ] **Step 4: Run the contract tests and verify RED**

Run: `cd backend && pytest tests/test_web_integration.py tests/test_picnic_web_integration.py -k 'round_trip or picnic or official_url' -q`

Expected: FAIL because the API projection does not include `officialUrl`.

- [ ] **Step 5: Implement strict official URL projection**

Import `VenueActivity`, `SupportStatus`, and `urlsplit`. Implement `_official_url(db, venue, activity_type_id)` to fetch only the matching supported row, parse `source_reference`, require scheme `https`, reject userinfo/ports and empty hosts, and require `SPORTS_FACILITY` venues to use an exact host or dot-delimited subdomain of `activesgcircle.gov.sg` while `PARK` venues use `nparks.gov.sg`. Return the original exact URL when valid; otherwise return `None`.

Change `_venue` to accept `db` and `activity_type_id`, add `officialUrl`, and update both `_combination_projection` and `confirmed_plan` call sites with their session activity ID. Do not fall back to category homepages or venue-name searches.

- [ ] **Step 6: Run the contract tests and verify GREEN**

Run: `cd backend && pytest tests/test_web_integration.py tests/test_picnic_web_integration.py -q`

Expected: all selected integration tests pass and recommendations/confirmation carry the same reviewed exact URL.

- [ ] **Step 7: Commit the backend contract**

```bash
git add backend/app/services/web_contract_service.py backend/tests/test_web_integration.py backend/tests/test_picnic_web_integration.py
git commit -m "feat: expose reviewed official venue links"
```

### Task 3: Official links in grouped results and confirmed plans

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/results/groupRecommendations.ts`
- Modify: `frontend/src/results/venueGuidance.ts`
- Modify: `frontend/src/results/RankedOptionCard.tsx`
- Modify: `frontend/src/results/RankedOptionCard.css`
- Modify: `frontend/src/pages/ConfirmedPage.tsx`
- Modify: `frontend/src/pages/ConfirmedPage.css`
- Test: `frontend/tests/groupRecommendations.test.ts`
- Test: `frontend/tests/venueGuidance.test.ts`

**Interfaces:**
- Consumes: backend `VenueSummary.officialUrl` from Task 2.
- Produces: `VenueSummary.officialUrl: string | null` and `venueOfficialLinkLabel(category: VenueCategory) -> string`.
- Copy: parks use `View official park information`; all other supported venue categories use `View official venue information`.

- [ ] **Step 1: Write failing grouping and label tests**

Add `officialUrl` to the `option()` fixture. Add `keeps different official venue links separate`, passing two otherwise identical options with different URLs and asserting two groups. Add label assertions for `PARK`, `SPORTS_FACILITY`, and the generic category.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd frontend && node --experimental-strip-types --test tests/groupRecommendations.test.ts tests/venueGuidance.test.ts`

Expected: FAIL because the type, grouping field and label helper do not exist.

- [ ] **Step 3: Extend the frontend contract and grouping signature**

Add `officialUrl: string | null` to `VenueSummary`. Include `option.venue.officialUrl` in `groupingKey()` so projected venue metadata cannot be silently merged. Implement `venueOfficialLinkLabel(category)` with the approved exact copy.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `cd frontend && node --experimental-strip-types --test tests/groupRecommendations.test.ts tests/venueGuidance.test.ts`

Expected: all selected tests pass.

- [ ] **Step 5: Render the official link in both venue views**

In expanded `RankedOptionCard`, render the exact `officialUrl` near the existing Google Maps link only when non-null. In `ConfirmedPage`'s **Where** section, render the same optional link. Both links must use `target="_blank"`, `rel="noopener noreferrer"`, and `venueOfficialLinkLabel(...)`; keep Google Maps and the existing availability/booking language unchanged.

- [ ] **Step 6: Add minimal responsive styling**

Style the two links using existing link colors and focus-visible conventions. Allow the result-card actions to wrap on narrow screens, and keep touch targets readable without changing the card or confirmation layout.

- [ ] **Step 7: Verify the complete frontend**

Run: `cd frontend && npm test && npm run lint && npm run build`

Expected: all unit tests pass, lint exits 0, TypeScript accepts every `VenueSummary` fixture, and Vite produces `dist/`.

- [ ] **Step 8: Commit the frontend feature**

```bash
git add frontend/src/api/types.ts frontend/src/results/groupRecommendations.ts frontend/src/results/venueGuidance.ts frontend/src/results/RankedOptionCard.tsx frontend/src/results/RankedOptionCard.css frontend/src/pages/ConfirmedPage.tsx frontend/src/pages/ConfirmedPage.css frontend/tests/groupRecommendations.test.ts frontend/tests/venueGuidance.test.ts
git commit -m "feat: link recommendations to official venue pages"
```

### Task 4: Whole-branch verification and production acceptance

**Files:**
- No product or assessment-document changes; this task verifies and releases Tasks 1–3.

**Interfaces:**
- Consumes: the complete OneMap and official-link implementation.
- Produces: reviewed commits on the existing Render source branch and observable production acceptance evidence.

- [ ] **Step 1: Run the full local verification suite**

Run: `cd backend && pytest -q`

Run: `cd frontend && npm test && npm run lint && npm run build`

Expected: every backend and frontend test passes; lint exits 0; the production build succeeds.

- [ ] **Step 2: Audit the diff for scope and secrets**

Run: `git diff origin/feature/production-pilot...HEAD --check`

Run: `git diff --stat origin/feature/production-pilot...HEAD`

Run: `git grep -n -E 'ONEMAP_(TOKEN|EMAIL|PASSWORD)=|eyJ[a-zA-Z0-9_-]+\.' -- ':!docs/superpowers/specs/*' ':!docs/superpowers/plans/*'`

Expected: no whitespace errors, no unrelated assessment/sharing work, and no committed OneMap credential or JWT value. Treat any suspicious match as a stop condition and inspect it before proceeding.

- [ ] **Step 3: Request whole-branch code review**

Use `superpowers:requesting-code-review` against `origin/feature/production-pilot...HEAD`. Resolve every correctness, privacy, security or regression finding and rerun Step 1 before continuing.

- [ ] **Step 4: Finish and integrate the branch**

Use `superpowers:finishing-a-development-branch`. After the user-approved integration choice, push the reviewed commits to `origin/feature/production-pilot`, the existing Render source branch. Do not expose Render or OneMap secrets during the push or deployment check.

- [ ] **Step 5: Verify the Render deployment**

Wait for Render to mark the deployment sourced from the new GitHub commit **Live**. Verify `https://group-scheduling-app.onrender.com/health` and `/ready` return 200 before testing signed-in flows.

- [ ] **Step 6: Verify OneMap recovery behavior in production without forcing an outage**

From the signed-in availability flow, search a known Singapore postal code such as `579827` and assert OneMap returns a selectable candidate. Confirm the deployed logs contain no credential value and no repeated token-refresh loop. Do not deliberately corrupt or delete production secrets.

- [ ] **Step 7: Verify exact official links in the live UI**

Use an existing accessible Picnic session and a sports session, or create controlled test sessions if needed. In expanded results, confirm the Picnic link opens that park's exact NParks page and the sports link opens that facility's exact ActiveSG page. For an already-confirmed test plan, confirm the **Where** section shows the same official URL. Verify both screens still state that booking/live availability is not guaranteed, still provide Google Maps, still group equivalent times, and still prevent a non-organiser from confirming.

