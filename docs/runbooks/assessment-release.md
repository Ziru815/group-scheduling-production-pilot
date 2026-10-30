# Assessment release runbook

This is the redacted operational record for the public course-assessment pilot.
Record role labels and pass/fail results only. Never paste secrets, cookies,
OAuth codes, database URLs, emails, or participant locations here.

## Release targets

- First public deployment: no later than 2026-11-06
- Demo video: around 2026-11-10
- Presentation: around 2026-11-17
- Hosting budget: S$10–30 total per month
- Proposed private repository: `group-scheduling-production-pilot`
- Proposed Railway project: `group-scheduling`
- Railway region: Singapore (`asia-southeast1-eqsg3a`)

## External access checkpoint — 2026-10-28

| Dependency | Current evidence | Status | Required next action |
| --- | --- | --- | --- |
| GitHub | ChatGPT GitHub plugin installed and enabled; low-risk actions allowed. No repository remote, `gh` CLI, or repository-write tool is available in this Codex session. | Blocked | Repository owner creates a private repository and supplies its clone URL, or reconnects a GitHub tool that exposes repository creation/push. |
| Railway | No CLI login or project is present locally. | Blocked | Billing owner creates/signs into Railway and selects Trial or Hobby; do not choose Pro for this pilot. |
| Google Cloud | Team members have Google accounts, but no OAuth project/client has been confirmed. | Blocked | Google Cloud owner creates a Web application OAuth client and keeps it in Testing with three team test users. |
| OneMap | No token or account credentials are configured locally. | Blocked | Provider owner obtains a OneMap token or account credentials and enters them only in Railway secrets. |

Role assignments:

- Release owner: `TBD`
- Railway billing owner: `TBD`
- Google Cloud OAuth owner: `TBD`
- OneMap credential owner: `TBD`
- Shutdown owner: `TBD`

## Local release evidence

- [x] Production runtime rejects SQLite, demo auth, mock providers, insecure cookies, and missing provider settings.
- [x] Alembic owns production schema changes; automatic table creation is disabled.
- [x] Pre-deploy seeds only six idempotent activity types and never demo users or demo venues.
- [x] Official SportSG rows are fetched before any database write and schema/pagination failures stop the sync.
- [x] Production recommendations require active `VERIFIED_PUBLIC` venues.
- [x] The UI shows catalogue provenance and warns that it is not live court availability.
- [x] Google sign-in uses browser-bound state, nonce, PKCE, verified email, and secure application sessions.
- [ ] Root Docker image build — Docker is unavailable on this Mac; GitHub CI must supply this evidence.
- [ ] PostgreSQL migration round trip — requires a disposable PostgreSQL service.

Most recent automated verification:

| Check | Result | Date |
| --- | --- | --- |
| Backend test suite | `PASS — 208 tests` | 2026-10-30 |
| Frontend lint | `PASS` | 2026-10-30 |
| Frontend production build | `PASS` | 2026-10-30 |
| Railway IaC typecheck | `PASS` | 2026-10-28 |
| Live data.gov.sg dry run | `PASS` | 2026-10-30 |

## Provisioning checklist

### 1. Private GitHub repository

- [ ] Create a private repository; do not initialise it with a README or licence.
- [ ] Add the repository as `origin` and push `feature/production-pilot`.
- [ ] Confirm GitHub Actions passes, including the Docker build.
- [ ] Protect the selected release branch from accidental force-push.

Record only:

- Owner/organisation: `TBD`
- Private repository URL: `TBD`
- CI run URL: `TBD`
- CI result: `NOT RUN`

### 2. Railway project and cost controls

- [ ] Use Trial first if available; otherwise use Hobby (not Pro).
- [ ] Create `group-scheduling` with application service `app` and PostgreSQL service `postgres`.
- [ ] Apply `.railway/railway.ts` only after reviewing `railway config plan`.
- [ ] Generate one Railway HTTPS domain; no custom domain.
- [ ] In Workspace Usage, set a compute warning around US$8 and a hard limit at or below US$15. The Hobby base fee is currently US$5 and includes the first US$5 of usage.
- [ ] Name the billing owner and check usage after each rehearsal.

Record only:

- Railway project/service names: `TBD`
- Public HTTPS origin: `TBD`
- Region shown in dashboard: `TBD`
- Billing plan and owner role: `TBD`
- Warning/hard limit configured: `NOT RUN`

### 3. Production variables

Enter values in Railway's secret store, never in this file:

- `APP_SESSION_SECRET`
- `FRONTEND_BASE_URL`
- `ALLOWED_ORIGINS`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `ONEMAP_TOKEN`, or `ONEMAP_EMAIL` and `ONEMAP_PASSWORD`

The IaC configuration supplies the fixed safety values and the private
PostgreSQL `DATABASE_URL` reference.

- [ ] All required variable names exist.
- [ ] No populated `.env` file or credential export is committed.
- [ ] `/health` and `/ready` return HTTP 200 on the generated domain.

### 4. Initial migration and venue catalogue

- [ ] Pre-deploy `alembic upgrade head` succeeds.
- [ ] `python -m scripts.seed_reference_data` reports no demo data.
- [ ] Run `python -m scripts.sync_venues --dry-run` and review counts.
- [ ] Run `python -m scripts.sync_venues --apply` once against production.
- [ ] Re-run `--apply`; inserted count must be zero and venue count must not grow.
- [ ] Confirm exactly 58 current allowlist entries are `VERIFIED_PUBLIC`.
- [ ] Confirm Badminton, Basketball, and Football each expose exactly twenty
  verified venues.

| Measurement | Dry run | First apply | Second apply |
| --- | ---: | ---: | ---: |
| Source rows | 16,595 | n/a | n/a |
| Recognized rows | 2,571 | n/a | n/a |
| Rejected rows | 14,024 | n/a | n/a |
| Normalized venues | 1,581 | n/a | n/a |
| Verified venues | 58 | 58 | 58 |
| Unverified venues | 1,523 | 1,523 | 1,523 |
| Inserted / updated / deactivated | n/a | 0 / 1,581 / 0 | 0 / 1,581 / 0 |

Islandwide badminton rollout evidence (redacted):

| Check | Result | Timestamp |
| --- | --- | --- |
| Release commit | `e769527863d8851a07a73aca849008b125a87ffa` | 2026-10-30 22:15 +08 |
| Render deployed the release commit | `PASS` | 2026-10-30 22:15 +08 |
| Public `/ready` returned HTTP 200 | `PASS` | 2026-10-30 22:15 +08 |
| Two production catalogue applies were idempotent | `PASS` | 2026-10-30 22:15 +08 |
| West/east recommendation sets differed and surfaced new nearby venues | `PASS` | 2026-10-30 22:15 +08 |

### 5. Google callback

- [ ] Add the exact Railway origin as an authorised JavaScript origin.
- [ ] Add `<origin>/api/auth/google/callback` as the exact redirect URI.
- [ ] Keep the OAuth app in Testing and add three team test users.
- [ ] Update Railway values and redeploy.
- [ ] Remove obsolete public callback URLs.

Use `docs/runbooks/google-login-smoke-test.md`; record only pass/fail account
labels such as `organiser`, `participant-a`, and `participant-b`.

### 6. Migration gate drill

Use a disposable Railway environment, never production data:

- [ ] Deploy a known-good version and record its health response.
- [ ] Temporarily change the pre-deploy command to a command that exits non-zero.
- [ ] Confirm the new deployment is rejected and the old version remains healthy.
- [ ] Restore the real pre-deploy commands immediately.

Result: `NOT RUN`

## Live rehearsal record

Do not record until all provider checks pass. Complete this table twice from
clean browser state.

| Check | Rehearsal 1 | Rehearsal 2 |
| --- | --- | --- |
| Release commit SHA and timestamp | `TBD` | `TBD` |
| Three Google identities remain distinct | `NOT RUN` | `NOT RUN` |
| Organiser creates badminton session | `NOT RUN` | `NOT RUN` |
| Two participants join and submit different inputs | `NOT RUN` | `NOT RUN` |
| No participant sees another exact location | `NOT RUN` | `NOT RUN` |
| Verified venues and provenance visible | `NOT RUN` | `NOT RUN` |
| Walk/drive/public-transport routes handled | `NOT RUN` | `NOT RUN` |
| Confirmation survives app restart | `NOT RUN` | `NOT RUN` |
| Invalid OneMap configuration shows unavailable, never mock data | `NOT RUN` | `NOT RUN` |

## Release freeze

- Video tag `demo-video-2026-11-10`: `NOT CREATED`
- Presentation tag `presentation-2026-11-17`: `NOT CREATED`
- Latest Railway backup: `NOT CREATED`
- Encrypted local `pg_dump` verified: `NOT CREATED`
- Previous deploy/commit recorded for application rollback: `TBD`

Only severity-one stability fixes are allowed between the video and
presentation tags. A code rollback does not automatically downgrade the
database; restore PostgreSQL only from a verified backup when a reviewed
recovery plan requires it.

## Authoritative operating references

- [Railway CLI](https://docs.railway.com/cli)
- [Railway Infrastructure as Code](https://docs.railway.com/infrastructure-as-code/reference)
- [Railway pre-deploy commands](https://docs.railway.com/deployments/pre-deploy-command)
- [Railway cost controls](https://docs.railway.com/pricing/cost-control)
- [Railway pricing plans](https://docs.railway.com/pricing/plans)
