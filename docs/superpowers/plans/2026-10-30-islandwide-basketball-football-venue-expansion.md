# Islandwide Basketball and Football Venue Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the production Basketball and Football catalogues from one to twenty verified venues each while preserving the existing website, shortlist behavior, and deployment branch.

**Architecture:** Add thirty-eight activity-scoped entries to the existing verified venue allowlist; do not change application code. Reuse the current data.gov.sg normalization, ActiveSG evidence policy, OneMap address enrichment, verified-only repository query, and nearest-ten shortlist, then synchronize the production database after the unchanged Render service deploys the GitHub commit.

**Tech Stack:** Python 3.13, FastAPI/SQLModel, pytest, data.gov.sg Sport Facilities, ActiveSG facility pages, OneMap, Render PostgreSQL, Git/GitHub

**Spec:** `docs/superpowers/specs/2026-10-30-islandwide-basketball-football-venue-expansion-design.md`

## Global Constraints

- Basketball and Football must each expose exactly twenty verified venues after sync.
- Badminton remains at twenty verified venues; Bowling, Picnic, and Board Games remain unchanged.
- The allowlist must contain exactly 58 unique source identities after the change.
- Every new entry must be present in the current data.gov.sg snapshot and the matching official ActiveSG activity catalogue.
- Every new entry must declare exactly one activity in `verified_activities` and use an official activity-specific evidence URL.
- Do not change the default shortlist size of ten, scoring, OneMap routing, frontend behavior, public URL, Render service, Google integration, or `main` branch.
- Do not claim live availability or guaranteed booking.
- Configuration-only work may use the existing loader/catalogue suite and live dry-run as its verification contract; do not create a brittle exact-list unit test.

## Review Focus

- A data.gov.sg rename or postal-code change must reduce the dry-run verified count rather than match a wrong facility; Task 1 requires exactly 58 source-key matches.
- An ActiveSG page with a current long-term closure must block its venue; Task 1 checks every selected page immediately before editing.
- A multi-sport raw record must expose only its selected verified activity; Task 1 runs the existing activity-scope regression test.
- The same source identity must not appear twice for different evidence URLs; Task 1 verifies 58 unique source keys.
- Increasing the catalogue must not increase routing fan-out above ten; Task 2 runs the full backend suite and preserves the existing shortlist setting.

---

### Task 1: Add the activity-scoped verified venue evidence

**Files:**
- Modify: `backend/app/data/verified_public_sports_venues.json`
- Modify: `docs/venue-verification.md`
- Modify: `docs/runbooks/assessment-release.md`

**Interfaces:**
- Consumes: `venue_source_key(name: str, postal_code: str) -> str`, `load_verified_venue_allowlist()`, the current data.gov.sg normalizer, and the existing activity-scoped sync behavior.
- Produces: 58 unique `VerifiedVenueEvidence` records with twenty supported links for each of Badminton, Basketball, and Football.

- [ ] **Step 1: Revalidate the selected records against both official sources**

Fetch the current data.gov.sg dataset and the thirty-eight ActiveSG evidence URLs. Assert every source name/postal pair has the planned activity, every URL returns HTTP 200, no page announces a current long-term closure, and the ActiveSG Basketball or Football catalogue lists the same postal code.

Expected: 19 Basketball and 19 Football additions pass; any failure blocks that entry and requires a geographically equivalent replacement that satisfies the spec.

- [ ] **Step 2: Add deterministic activity-scoped entries**

Compute every `source_key` with `venue_source_key(source_name, postal_code)`. Add the exact source name, postal code, display name, official URL, `verified_on: 2026-10-30`, and the one planned `verified_activities` value to `backend/app/data/verified_public_sports_venues.json`.

- [ ] **Step 3: Update the verification register and release counts**

Document all added records and the resulting per-activity counts in `docs/venue-verification.md`. Update `docs/runbooks/assessment-release.md` from 20 verified / 1,561 unverified to 58 verified / 1,523 unverified, conditional on the current upstream total remaining 1,581.

- [ ] **Step 4: Verify configuration and live normalization**

Run: `cd backend && python -m pytest tests/test_venue_catalog.py -q`

Expected: all catalogue tests pass.

Run: `cd backend && python -m scripts.sync_venues --dry-run`

Expected: `verified_venues=58`, `unverified_venues=1523`, and no source-key mismatch. Upstream totals may change, but all 58 selected identities must match.

- [ ] **Step 5: Commit**

```bash
git add backend/app/data/verified_public_sports_venues.json docs/venue-verification.md docs/runbooks/assessment-release.md docs/superpowers/specs/2026-10-30-islandwide-basketball-football-venue-expansion-design.md docs/superpowers/plans/2026-10-30-islandwide-basketball-football-venue-expansion.md
git commit -m "feat: expand basketball and football venues islandwide"
```

### Task 2: Verify and review the release candidate

**Files:**
- Read: all files changed from `origin/feature/production-pilot` to `HEAD`
- Modify only if a Critical or Important review finding requires it.

**Interfaces:**
- Consumes: Task 1's 58-entry verified allowlist.
- Produces: a green, independently reviewed commit ready for the existing GitHub deployment branch.

- [ ] **Step 1: Run complete local verification**

Run: `cd backend && python -m pytest -q`

Expected: the complete backend suite passes.

Run: `cd frontend && npm run lint && npm run build`

Expected: lint exits zero and Vite production build succeeds.

Run: `git diff --check origin/feature/production-pilot...HEAD`

Expected: no output and exit zero.

- [ ] **Step 2: Obtain a fresh whole-branch review**

Review the spec, the exact thirty-eight additions, source-key correctness, activity scope, evidence URLs, unchanged shortlist behavior, and every Review Focus item.

Expected: no Critical or Important findings. Fix any such finding in one evidence-backed pass and rerun Step 1.

### Task 3: Deploy through the existing branch and synchronize production

**Files:**
- Modify: `docs/runbooks/assessment-release.md` only if final upstream counts differ from the recorded conditional counts.

**Interfaces:**
- Consumes: Task 2's reviewed commit and the existing Render service `group-scheduling-app`.
- Produces: a fast-forwarded GitHub `feature/production-pilot` branch, the same public Render URL, an idempotently synchronized production venue catalogue, and live geographic smoke evidence.

- [ ] **Step 1: Fast-forward the existing deployment branch**

Push the reviewed commit to `feature/production-pilot` without force-pushing and without modifying `main`.

Expected: GitHub records the new commit and Render starts an automatic deployment from it.

- [ ] **Step 2: Wait for the unchanged Render service to become healthy**

Confirm the live deployment uses the pushed GitHub commit and `https://group-scheduling-app.onrender.com/ready` returns HTTP 200.

- [ ] **Step 3: Apply the venue sync twice**

Run `python -m scripts.sync_venues --apply` twice in the production service environment.

Expected: both runs report 58 verified venues; the second run is idempotent with no duplicate insertions or unexpected deactivations.

- [ ] **Step 4: Smoke-test geographic variation**

Create or use Basketball and Football sessions with west-side and east-side Singapore participant postals. Confirm each activity produces verified candidates near both regions and the two regions receive different local candidate sets.

- [ ] **Step 5: Record and commit final release evidence if counts changed**

If the live upstream total differs from 1,581, update only the observed counts in the release runbook, rerun `git diff --check`, and commit the evidence correction before the final push.
