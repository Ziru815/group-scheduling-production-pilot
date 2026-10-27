# Public Pilot Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy, verify, rehearse, and safely retire the public course-assessment pilot using real accounts, PostgreSQL, verified venues, and live OneMap routing.

**Architecture:** GitHub is the deployment source, Railway runs one same-origin application service and private PostgreSQL in Singapore, and pre-deploy Alembic migrations gate releases. A redacted runbook records live checks, backup/rollback, budget monitoring, and post-course shutdown.

**Tech Stack:** GitHub, Railway, PostgreSQL, Google Cloud OAuth, OneMap, FastAPI, React, Alembic

**Spec:** `docs/superpowers/specs/2026-10-27-production-pilot-design.md`

## Global Constraints

- Use a private GitHub repository and a Railway-generated HTTPS domain; no custom domain is required.
- Never paste secrets into chat, Git, documentation, screenshots, or video.
- Target first public deployment by 2026-11-06, video around 2026-11-10, and presentation around 2026-11-17.
- Keep monthly spend within S$10–30 and shut services down after grading.
- Do not record the demo until the full three-account path passes twice from clean browser state.

## Review Focus

- A migration failure must block the release instead of starting against an old schema; Task 1 verifies a deliberately failing pre-deploy command in a disposable environment.
- An application restart must not erase accounts, sessions, or venues; Task 2 adds restart persistence checks.
- OneMap outage must show unavailable travel instead of mock travel; Task 2 adds a live failure drill using an invalid temporary token/config.
- Rollback must preserve forward-migrated data; Task 3 separates image rollback from database restore and rehearses both.
- A forgotten service after grading must not keep charging; Task 3 includes an owner/date shutdown checklist.

---

### Task 1: Provision the assessment environment

**Files:**
- Modify: `docs/deployment.md`
- Create: `docs/runbooks/assessment-release.md`

**Interfaces:**
- Consumes: private GitHub repository, Railway account, Google OAuth client, OneMap credentials.
- Produces: one Railway Singapore application, one private PostgreSQL service, generated HTTPS domain, and redacted environment checklist.

- [ ] **Step 1: Confirm external account access**

Confirm GitHub connection, Railway sign-in/billing owner, Google Cloud project access, and OneMap account ownership. Record team role names, not credentials, in the runbook.

- [ ] **Step 2: Create Railway services**

Create the application from the private repository and attach PostgreSQL in Singapore. Configure all production variables using the platform secret store and generated references such as `DATABASE_URL`.

- [ ] **Step 3: Run migrations and initial venue sync**

Deploy with the pre-deploy migration, then execute `python -m scripts.sync_venues --dry-run` and `--apply` against production. Record total, rejected, unverified, verified, inserted, updated, and deactivated counts.

- [ ] **Step 4: Register the exact Google callback**

Add the Railway HTTPS origin and `/api/auth/google/callback` redirect in Google Cloud, update Railway variables, redeploy, and remove any obsolete public callbacks.

- [ ] **Step 5: Verify the migration gate**

In a disposable Railway environment, temporarily set a failing pre-deploy command and confirm the old deployment remains serving; restore the real command immediately. Record result without exposing logs containing environment values.

- [ ] **Step 6: Commit redacted provisioning notes**

Commit only service names, regions, public URLs, and pass/fail evidence with `git commit -m "docs: record assessment environment setup"`.

### Task 2: Execute live end-to-end and resilience checks

**Files:**
- Modify: `docs/runbooks/assessment-release.md`
- Modify: `SRS_TRACEABILITY.md`

**Interfaces:**
- Consumes: live Railway environment and three team Google accounts.
- Produces: two successful redacted rehearsal records mapped back to SRS requirements.

- [ ] **Step 1: Run provider smoke checks**

Verify one Singapore postal code and address through OneMap, then route walk/drive/public transport to a verified venue. Verify the public UI shows the official venue source and does not claim live court availability.

- [ ] **Step 2: Run the first three-account scenario**

On separate clean browsers/devices: organiser signs in and creates a badminton session; two participants sign in, join, and submit distinct locations/times; organiser generates results; members review; organiser confirms. Assert no participant can see another's exact location.

- [ ] **Step 3: Verify persistence across restart**

Restart/redeploy the application without resetting PostgreSQL. Assert all three accounts, the session, responses, verified venue catalogue, recommendations, and confirmation remain readable.

- [ ] **Step 4: Drill external-provider failure**

In a disposable environment, use an invalid OneMap token or blocked base URL and generate recommendations. Expected: affected travel is explicitly unavailable, no mock time appears, and the production catalogue remains intact. Restore the valid configuration.

- [ ] **Step 5: Run the second clean rehearsal**

Repeat the whole flow from new incognito sessions. Record timestamps, release commit SHA, redacted account labels, and pass/fail only.

- [ ] **Step 6: Update traceability and commit**

Map Google login, persistent SQL, authorised venue data, live route behavior, privacy, and decoupled sync evidence into `SRS_TRACEABILITY.md`; commit with `git commit -m "docs: record public pilot verification"`.

### Task 3: Freeze, back up, present, and retire safely

**Files:**
- Modify: `docs/runbooks/assessment-release.md`
- Create: `docs/runbooks/shutdown.md`

**Interfaces:**
- Consumes: verified release commit and production PostgreSQL.
- Produces: recoverable demo/presentation releases and an owner-assigned shutdown record.

- [ ] **Step 1: Freeze the video release**

Tag the verified commit `demo-video-2026-11-10`, take a Railway database backup plus encrypted local `pg_dump`, verify the dump can list tables, and record the rollback image/commit.

- [ ] **Step 2: Record the demo video**

Use the verified flow and avoid showing Railway variables, Google client settings, full private addresses, tokens, or database dashboards. Keep fallback screenshots/video from the same tagged release.

- [ ] **Step 3: Rehearse rollback**

Redeploy the previous image in a disposable environment against a copied backup. Confirm application rollback does not pretend to downgrade the database; document when a database restore would be required.

- [ ] **Step 4: Prepare presentation release**

Allow only severity-one stability fixes after the video tag. Re-run all automated checks and the full live scenario, tag `presentation-2026-11-17`, and take a fresh backup.

- [ ] **Step 5: Monitor cost and health**

Record Railway usage after first rehearsal, video recording, and final presentation. Set the available budget alert/limit and name one team member responsible for reacting before S$30.

- [ ] **Step 6: Write and execute shutdown checklist after grading**

Export only desired evidence, remove/revoke Google and OneMap secrets, suspend/delete Railway application and PostgreSQL, verify billing resources are gone, and optionally archive the private GitHub repository. Record the completion date and responsible team member.

- [ ] **Step 7: Commit the runbooks**

Run `git add docs/runbooks && git commit -m "docs: add release backup and shutdown runbooks"`.

