# Islandwide Badminton Venue Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the production badminton catalogue from eight to twenty officially verified venues distributed across Singapore and roll the data into Render and GitHub.

**Architecture:** Keep the existing data.gov.sg ingestion, OneMap enrichment, `VERIFIED_PUBLIC` trust boundary, and nearest-ten centroid shortlist unchanged. Add twelve curated allowlist records, document the revised school-hall verification rule, then run the existing sync transaction against production after the deployment is live.

**Tech Stack:** Python 3.13, FastAPI/SQLModel, pytest, data.gov.sg Sport Facilities, ActiveSG facility pages, OneMap, Render PostgreSQL, Git/GitHub

**Spec:** `docs/superpowers/specs/2026-10-30-islandwide-badminton-venue-expansion-design.md`

## Global Constraints

- Only Badminton changes in this phase; Football, Basketball, Bowling, Picnic, and Board Games remain unchanged.
- The verified catalogue must contain exactly twenty entries after the change.
- The default shortlist remains ten; do not change scoring, routing, or frontend behaviour.
- Every added source identity must exist in the current data.gov.sg snapshot with a six-digit postal code, Singapore coordinates, and `Badminton Court` support.
- Every added school hall must have an official ActiveSG badminton facility page with a public badminton booking entry.
- Runtime scraping is forbidden; official-page verification is release-time curation only.
- The UI and documentation must not claim live availability or guaranteed booking.
- The approved design explicitly treats this as a data/configuration change: do not add an artificial exact-list unit test. Existing catalogue tests plus live dry-run/apply evidence are the verification contract.

## Review Focus

- A data.gov.sg venue rename or postal-code change must reduce the live verified count instead of silently verifying the wrong record; Task 1's dry run checks for exactly twenty matches.
- A school page that mentions badminton but has no public booking entry must not enter the allowlist; Task 1 rechecks booking evidence before editing data.
- Duplicate source keys or postal-code mismatches must fail the existing allowlist loader tests; Task 1 runs the complete catalogue test module.
- OneMap address enrichment failure must preserve the honest `<venue>, Singapore <postal>` fallback; Task 2 runs the full backend suite containing that behavior.
- Production sync must be idempotent and must not deactivate or duplicate the other 1,561 normalized venues; Task 3 runs two consecutive production applies and records both results.

---

### Task 1: Expand the verified badminton catalogue

**Files:**
- Modify: `backend/app/data/verified_public_sports_venues.json`
- Modify: `docs/venue-verification.md`
- Modify: `docs/runbooks/assessment-release.md`

**Interfaces:**
- Consumes: `venue_source_key(name: str, postal_code: str) -> str`, `load_verified_venue_allowlist()`, and the existing data.gov.sg normalizer.
- Produces: twenty valid `VerifiedVenueEvidence` entries consumed unchanged by `VenueCatalogSyncService.sync()`.

- [ ] **Step 1: Revalidate all twelve proposed records against the live official sources**

Run a read-only script using `DataGovSgAdapter` and the twelve URLs in the design. For every candidate, assert the dataset source name/postal pair exists with `Badminton`, the ActiveSG URL returns HTTP 200, and the page contains both badminton and a public booking entry.

Expected: twelve unambiguous matches; any failure blocks that record rather than weakening the rule.

- [ ] **Step 2: Add the twelve deterministic allowlist entries**

Use `venue_source_key(source_name, postal_code)` to calculate each `source_key`. Add the entries to `backend/app/data/verified_public_sports_venues.json` with the exact source/display names, postal codes, official URLs, and `verified_on: 2026-10-30` from the approved design.

- [ ] **Step 3: Update verification and release documentation**

Extend `docs/venue-verification.md` to list all twenty venues and replace the blanket school exclusion with the approved rule: only official ActiveSG badminton facility pages with public booking evidence qualify. Update `docs/runbooks/assessment-release.md` expected counts from eight verified / 1,573 unverified to twenty verified / 1,561 unverified.

- [ ] **Step 4: Verify the loader and live normalization**

Run: `cd backend && .venv/bin/pytest tests/test_venue_catalog.py -q`

Expected: all catalogue tests pass.

Run: `cd backend && .venv/bin/python -m scripts.sync_venues --dry-run`

Expected: `source_rows=16595 recognized_rows=2571 rejected_rows=14024 normalized_venues=1581 verified_venues=20 unverified_venues=1561` (source totals may change upstream, but `verified_venues=20` is mandatory).

- [ ] **Step 5: Commit**

```bash
git add backend/app/data/verified_public_sports_venues.json docs/venue-verification.md docs/runbooks/assessment-release.md
git commit -m "feat: expand verified badminton venues islandwide"
```

### Task 2: Verify the release candidate and obtain independent review

**Files:**
- Read: all files changed since `origin/feature/production-pilot`
- Modify only if required by an Important or Critical review finding.

**Interfaces:**
- Consumes: Task 1's twenty-entry catalogue.
- Produces: a green, independently reviewed commit range ready for the shared deployment branch.

- [ ] **Step 1: Run complete local verification**

Run: `cd backend && .venv/bin/pytest -q`

Expected: all backend tests pass.

Run: `cd frontend && npm run lint && npm run build`

Expected: lint exits zero and Vite production build succeeds.

Run: `git diff --check origin/feature/production-pilot...HEAD`

Expected: no output and exit zero.

- [ ] **Step 2: Request a fresh whole-branch review**

Build the review package from `origin/feature/production-pilot` to `HEAD`. Ask the reviewer to check the spec, the exact twelve records, source-key correctness, official-evidence policy, unchanged shortlist behavior, and every Review Focus item.

Expected: no Critical or Important findings. Fix any such finding in one test-backed pass and rerun Step 1.

### Task 3: Push, synchronize production, and record evidence

**Files:**
- Modify: `docs/runbooks/assessment-release.md`

**Interfaces:**
- Consumes: Task 2's reviewed commit and the existing Render service `group-scheduling-app`.
- Produces: GitHub `feature/production-pilot` at the reviewed commit, a Render deployment using the twenty-entry catalogue, an idempotently synchronized PostgreSQL catalogue, and redacted release evidence.

- [ ] **Step 1: Push the reviewed commit to the deployment branch**

Run: `git push origin HEAD:feature/production-pilot`

Expected: fast-forward update accepted. Never force-push.

- [ ] **Step 2: Wait for the Render deployment to become live**

Verify the deployment is built from the pushed GitHub commit and that `/ready` returns HTTP 200 before touching production data.

- [ ] **Step 3: Apply the venue sync twice from the paid Render service shell**

Run in the Render shell: `cd backend && python -m scripts.sync_venues --apply` if the shell starts at repository root, otherwise run `python -m scripts.sync_venues --apply` from the backend working directory used by the container.

Expected first apply: `verified=20`, with existing source-backed rows updated rather than duplicated.

Run the same command a second time.

Expected second apply: `inserted=0`, `deactivated=0`, `verified=20`, and the venue count does not grow.

- [ ] **Step 4: Smoke-test geographic variation**

Use the live application with a west-side postal code near NTU and an east-side postal code near Tampines. Generate badminton recommendations and confirm the nearest-ten venue sets differ and include newly added nearby verified venues. Do not record participant addresses, emails, cookies, or tokens.

- [ ] **Step 5: Record redacted production evidence and commit**

Update only counts, PASS/FAIL, release commit, and timestamps in `docs/runbooks/assessment-release.md`; do not paste secrets or private inputs.

Run: `git diff --check && cd backend && .venv/bin/pytest -q`

Expected: no whitespace errors and all backend tests pass.

```bash
git add docs/runbooks/assessment-release.md
git commit -m "docs: record islandwide venue rollout"
git push origin HEAD:feature/production-pilot
```

Expected: second fast-forward push accepted; Render may perform a documentation-only redeploy.
